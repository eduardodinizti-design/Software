"""Full native flop/turn/river export, compacted one street chunk at a time."""
from dataclasses import asdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time

from strategy.action_tree import apply_action
from strategy.policy_disk import PolicyWriter,DiskPolicy
from strategy.range_catalog import combo_key
from strategy.state_contract import DecisionState,StrategyError,reveal
from strategy.strategy_decision import choose
from strategy.texassolver_backend import input_commands,native_action,file_hash,SOURCE_COMMIT


def compact_stream(stream_path,output,context,root,ranges,menu,settings,provenance,metrics,*,max_line_mb=64,progress=None):
    writer=PolicyWriter(output,context,root,ranges,menu)
    chunk_count,root_count=0,0
    native_combos={}
    for range_ in ranges:
        for key,_ in range_.weights:
            native_combos[key]=key;native_combos[key[2:]+key[:2]]=key
    scale=settings['units_per_bb']

    def state_at(path):
        if not path or path[0]!='begin':raise StrategyError('NATIVE_STREAM_BAD_PATH')
        s=root
        for text in path[1:]:
            s=reveal(s,text.split(':',1)[1]) if text.startswith('Chance:') else apply_action(s,native_action(text,s,scale))
        return s

    def visit(value,state):
        if not value or state.terminal or not writer.possible(state.board):return
        if 'stream_ref' in value:
            if state_at(value['stream_ref']).key()!=state.key():raise StrategyError('NATIVE_STREAM_REFERENCE_STATE_CHANGED')
            return  # full closure is verified against the disk nodes at finalization
        kind=value.get('node_type')
        if kind=='chance_node':
            if not state.needs_cards:raise StrategyError('NATIVE_CHANCE_STATE_MISMATCH')
            for card,child in (value.get('dealcards') or {}).items():
                if card not in state.board and writer.possible(state.board+(card,)):
                    visit(child,reveal(state,card))
            return
        if kind!='action_node' or state.needs_cards:raise StrategyError('NATIVE_NODE_TYPE_MISMATCH')
        actor={0:1-root.oop,1:root.oop}.get(value.get('player'))
        if actor!=state.actor:raise StrategyError('NATIVE_ACTOR_ORDER_MISMATCH')
        labels=value['actions'];actions=tuple(native_action(a,state,scale) for a in labels)
        if not menu.include_all_in and any(a.kind=='all_in' for a in actions):raise StrategyError('NATIVE_AUTO_JAM_OUTSIDE_REQUESTED_MENU')
        block=value.get('strategy')
        if not block or block.get('actions')!=labels:raise StrategyError('NATIVE_STREAM_STRATEGY_MISSING')
        native_probabilities={}
        for hand,frequencies in block['strategy'].items():
            key=native_combos.get(hand)
            if key is None:raise StrategyError('NATIVE_COMBO_OUTSIDE_PRIORS')
            if key in native_probabilities:raise StrategyError('DUPLICATE_NATIVE_COMBO')
            native_probabilities[key]=frequencies
        writer.add_native(state,actions,native_probabilities)
        children=value.get('childrens') or {}
        for text,action in zip(labels,actions):
            if text in children:visit(children[text],apply_action(state,action))
    try:
        with gzip.open(stream_path,'rb') as stream:
            while True:
                line=stream.readline(max_line_mb*1024**2+1)
                if not line:break
                if len(line)>max_line_mb*1024**2:raise StrategyError('NATIVE_STREAM_CHUNK_TOO_LARGE')
                chunk=json.loads(line)
                if chunk.get('schema')!='software.native-street.v1':raise StrategyError('NATIVE_STREAM_SCHEMA_MISMATCH')
                if root_count:raise StrategyError('NATIVE_STREAM_DATA_AFTER_ROOT')
                if chunk.get('root'):
                    root_count+=1
                    if chunk['path']!=['begin']:raise StrategyError('NATIVE_STREAM_BAD_ROOT')
                visit(chunk['node'],state_at(chunk['path']));chunk_count+=1
                if progress and chunk_count%256==0:progress('COMPACTING',dict(chunks=chunk_count,public_nodes=writer.count))
        if root_count!=1:raise StrategyError('NATIVE_STREAM_TRUNCATED_NO_ROOT')
        last=metrics[-1] if metrics else None
        quality=dict(method='texassolver_discounted_cfr',settings=settings,provenance=provenance,
            iterations=last['iteration']+1 if last else None,
            global_gap_bb=2*root.pot_bb*last['exploitibility']/100 if last else None,
            gap_scope='native_full_tree_declared_menu_and_ranges',
            converged=bool(last and last['exploitibility']<=settings['target_exploitability_pct_pot']),
            native_metric_independently_verified=False,action_ev_available=False,
            export_depth_in_streets=6-len(root.board),stream_chunks=chunk_count,
            windows_validated=False,actual_sizes='native_rounding_to_one_unit_then_legality_checked')
        if progress:progress('VERIFYING_COMPLETE_TREE',dict(public_nodes=writer.count))
        return writer.finish(quality)
    finally:writer.close()


def query_probe(path):
    """Use the same decision function as the bot, on an actual stored node."""
    policy=DiskPolicy(path,cache_nodes=2)
    try:
        probes={}
        for street in ('flop','turn','river'):
            row=policy.db.execute('SELECT key FROM nodes WHERE lower(street)=? LIMIT 1',(street,)).fetchone()
            if row is None:continue
            node=policy.get_node(row[0]);state=policy.root.from_dict(node['state'])
            # choose() is a hero-turn API. Probe actor-0 decisions, rather than
            # pretend an actor-1 private hand belongs to the hero.
            if state.actor!=0:
                rows=policy.db.execute('SELECT key FROM nodes WHERE lower(street)=?',(street,))
                for (key,) in rows:
                    candidate=policy.get_node(key)
                    if candidate['state']['actor']==0:node=candidate;state=state.from_dict(node['state']);break
                else:raise StrategyError('POLICY_NO_HERO_QUERY_PROBE_ON_'+street.upper())
            hand=next(iter(node['combos']))
            d=DecisionState(policy.context,state,(hand[:2],hand[2:]),'batch-validation','probe-'+street)
            advice=choose(policy,d)
            if advice['status']!='ADVICE':raise StrategyError('POLICY_QUERY_PROBE_FAILED')
            probes[street]=dict(node_id=advice['node_id'],hero_cards=list(d.hero_cards),
                action=advice['recommended'],sizing=advice['sizing'],candidates=advice['candidates'])
        return dict(policy_sha256=policy.fingerprint,probes=probes,
                    scope='structural/lookup validation, not proof of GTO convergence or Windows input')
    finally:policy.close()


def solve_stream(binary,resources,job_dir,output,context,root,ranges,menu,*,iterations=501,threads=2,
                 accuracy_pct=.5,memory_mb=8192,timeout_seconds=3600,reuse_export=False,progress=None):
    binary,resources,job=Path(binary).resolve(),Path(resources).resolve(),Path(job_dir).resolve()
    build=json.loads(binary.with_name(binary.name+'.manifest.json').read_text())
    if (not build.get('supports_street_stream') or build.get('binary_sha256')!=file_hash(binary)
            or build.get('hu_chance_denominator_cards')!=4):raise StrategyError('CORRECT_HU_STREAM_BINARY_REQUIRED')
    if job.exists() and not reuse_export:raise StrategyError('NATIVE_JOB_DIR_MUST_BE_NEW_TO_PRESERVE_PREVIOUS_RUNS')
    commands,settings=input_commands(context,root,ranges,menu,iterations=iterations,threads=threads,
        accuracy_pct=accuracy_pct,dump_rounds=6-len(root.board),native_raise_limit=max(1,menu.max_raises))
    commands=commands.replace('dump_result strategy.json','dump_result_stream strategy.jsonl.gz')
    settings.update(memory_budget_mb=memory_mb,memory_limit_enforced=False,export_format='street_jsonl_gzip')
    if reuse_export:
        if not (job/'strategy.jsonl.gz').is_file() or (job/'input.txt').read_text()!=commands:
            raise StrategyError('EXISTING_NATIVE_EXPORT_DOES_NOT_MATCH_THIS_JOB')
    else:
        job.mkdir(parents=True);(job/'input.txt').write_text(commands)
    provenance=dict(repository='https://github.com/bupticybee/TexasSolver',tested_source_commit=SOURCE_COMMIT,
        binary_sha256=file_hash(binary),command_sha256=hashlib.sha256(commands.encode()).hexdigest(),
        evaluator_dictionary_sha256=file_hash(resources/'compairer/card5_dic_sorted.txt'),
        stream_generated_sha256=build.get('stream_generated_sha256'),license=build.get('license'))
    started=time.monotonic()
    if progress:progress('SOLVING',dict(iterations=settings['iterations']))
    if not reuse_export:
      with (job/'solver.log').open('w') as log:
        process=subprocess.Popen([str(binary),'-i',str(job/'input.txt'),'-r',str(resources)],cwd=job,stdout=log,stderr=subprocess.STDOUT)
        try:
            try:
                import resource
                resource.prlimit(process.pid,resource.RLIMIT_AS,(memory_mb*1024**2,)*2)
                settings['memory_limit_enforced']=True
            except ImportError:pass
            result=process.wait(timeout=timeout_seconds)
        except BaseException:
            process.kill();process.wait();raise
      if result!=0 or not (job/'strategy.jsonl.gz').exists():raise StrategyError('NATIVE_STREAM_SOLVE_FAILED_SEE_LOG')
    provenance['reused_export']=bool(reuse_export)
    metrics=[json.loads(line) for line in (job/'tmp_log.txt').read_text().splitlines() if line.strip()]
    if progress:progress('COMPACTING',{})
    result=compact_stream(job/'strategy.jsonl.gz',output,context,root,ranges,menu,settings,provenance,metrics,progress=progress)
    if progress:progress('VERIFYING_BOT_LOOKUP',{})
    result['lookup_validation']=query_probe(output)
    result['elapsed_seconds']=time.monotonic()-started
    return result
