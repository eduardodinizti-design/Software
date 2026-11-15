"""Batch correctness, full-tree closure and byte-for-byte policy semantics."""
from contextlib import ExitStack,closing
from dataclasses import replace
import copy
import gzip
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
import subprocess
from unittest.mock import patch

from strategy.action_tree import Action,apply_action
from strategy.batch_jobs import (atomic_json,canonical_flop,catalogue_flops,make_plan,checked_plan,
                                open_queue,queue_lock,cleanup_attempt,publish_index,run_queue,storage_capacity,folder_bytes)
from strategy.policy_disk import PolicyWriter,DiskPolicy,stored_node,decoded_node
from strategy.policy_store import CompiledPolicy
from strategy.policy_library import PolicyLibrary,LibraryHistory
from strategy.range_catalog import ComboRange
from strategy.native_stream import compact_stream,query_probe
from strategy.state_contract import BettingState,DecisionState,StrategyError
from strategy.strategy_decision import choose
from test_hu_operational import make_test_policy,reading,HERO,RIVER


HERE=Path(__file__).parent
FLOP_GAME=HERE/'docs/software-hu-engine-20261115/game-flop-btn-bb.json'
TURN_POLICY=HERE/'docs/software-hu-engine-20261115/policy-turn-conditional-fixed.json.gz'


def disk_copy(policy,path,*,omit=None,native_matrix=False):
    writer=PolicyWriter(path,policy.context,policy.root,policy.ranges,policy.menu)
    try:
        for key,node in policy.nodes.items():
            if key==omit:continue
            state=BettingState.from_dict(node['state']);actions=policy.actions(state)
            if native_matrix:
                probs={k:[r['frequencies'][a.id] for a in actions] for k,r in node['combos'].items()}
                writer.add(state,actions,node['combos'],native_probabilities=probs)
            else:writer.add(state,actions,node['combos'])
        return writer.finish(policy.quality,evaluation=policy.data.get('evaluation'))
    finally:writer.close()


class BatchPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.boards=catalogue_flops(100)

    def test_hundred_suit_distinct_boards_and_seven_groups(self):
        p=make_plan(FLOP_GAME,boards=self.boards)
        self.assertEqual(len(p['boards']),100)
        self.assertEqual(len({canonical_flop(b) for b in p['boards']}),100)
        groups=[p['boards'][i:i+16] for i in range(0,100,16)]
        self.assertEqual(list(map(len,groups)),[16]*6+[4])
        self.assertEqual(p['workers'],1)

    def test_batch_size_has_no_environment_cap_of_sixteen(self):
        self.assertEqual(make_plan(FLOP_GAME,boards=self.boards,batch_size=100)['batch_size'],100)

    def test_thread_budget_is_explicit_and_does_not_change_the_game(self):
        p=make_plan(FLOP_GAME,boards=self.boards,threads=4)
        self.assertEqual(p['settings']['threads'],4)
        self.assertEqual(p['game'],json.loads(FLOP_GAME.read_text()))
        with self.assertRaisesRegex(StrategyError,'THREAD_BUDGET'):
            make_plan(FLOP_GAME,boards=self.boards,threads=0)

    def test_flop_suit_permutations_are_not_counted_as_new_studies(self):
        self.assertEqual(canonical_flop(['As','7d','2c']),canonical_flop(['Ah','7s','2d']))
        with self.assertRaisesRegex(StrategyError,'DUPLICATE_SUIT'):
            make_plan(FLOP_GAME,boards=['As 7d 2c','Ah 7s 2d'])

    def test_untouched_source_ranges_and_sizes_are_preserved(self):
        original=json.loads(FLOP_GAME.read_text());p=make_plan(FLOP_GAME,boards=self.boards)
        self.assertEqual(p['game'],original)

    def test_changed_plan_cannot_resume_old_checkpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'plan.json';p=make_plan(FLOP_GAME,boards=self.boards)
            atomic_json(path,p);self.assertEqual(checked_plan(path),p)
            p['settings']['iterations']=11;atomic_json(path,p)
            with self.assertRaisesRegex(StrategyError,'HASH_MISMATCH'):checked_plan(path)

    def test_existing_user_folder_is_not_claimed_as_temporary_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'user-work.txt').write_text('preserve')
            with self.assertRaisesRegex(StrategyError,'MUST_BE_NEW'):
                open_queue(root,make_plan(FLOP_GAME,boards=self.boards),'irrelevant','irrelevant')
            self.assertEqual((root/'user-work.txt').read_text(),'preserve')

    def test_cleanup_cannot_escape_managed_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'temporary').mkdir();other=root/'user-data';other.mkdir()
            (other/'keep.txt').write_text('keep')
            with self.assertRaisesRegex(StrategyError,'NOT_A_MANAGED'):
                cleanup_attempt(root,other,'plan')
            self.assertTrue((other/'keep.txt').is_file())

    def test_cleanup_requires_the_matching_plan_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);attempt=root/'temporary'/'a';attempt.mkdir(parents=True)
            (attempt/'keep').write_text('keep')
            with self.assertRaisesRegex(StrategyError,'MARKER'):
                cleanup_attempt(root,attempt,'plan')
            atomic_json(attempt/'owned-by-batch.json',dict(plan_sha256='other'))
            with self.assertRaisesRegex(StrategyError,'MARKER'):cleanup_attempt(root,attempt,'plan')
            atomic_json(attempt/'owned-by-batch.json',dict(plan_sha256='plan'))
            cleanup_attempt(root,attempt,'plan');self.assertFalse(attempt.exists())


class DiskPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.turn=CompiledPolicy.load(TURN_POLICY)

    def test_full_turn_river_policy_is_query_equivalent_and_lazily_cached(self):
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as resources:
            path=Path(tmp)/'policy.sqlite';result=disk_copy(self.turn,path,native_matrix=True)
            disk=DiskPolicy(path,cache_nodes=2);resources.callback(disk.close)
            self.assertEqual(result['coverage']['nodes_by_street'],{'RIVER':1632,'TURN':10})
            for key,node in self.turn.nodes.items():
                decoded=disk.nodes[key]
                self.assertEqual(node['state'],decoded['state']);self.assertEqual(node['actions'],decoded['actions'])
                for combo,row in node['combos'].items():
                    self.assertEqual(row['frequencies'],decoded['combos'][combo]['frequencies'])
                    self.assertEqual(row.get('action_ev_bb'),decoded['combos'][combo].get('action_ev_bb'))
            self.assertLessEqual(len(disk._cache),2)
            proof=query_probe(path);self.assertEqual(set(proof['probes']),{'turn','river'})

    def test_incomplete_river_cannot_be_marked_complete(self):
        missing=next(k for k,n in self.turn.nodes.items() if len(n['state']['board'])==5)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'incomplete.sqlite'
            with self.assertRaisesRegex(StrategyError,'INCOMPLETE_STREETS'):
                disk_copy(self.turn,path,omit=missing)
            with self.assertRaises(Exception):DiskPolicy(path)

    def test_flop_only_export_cannot_pass_full_street_validation(self):
        source=CompiledPolicy.load(HERE/'docs/software-hu-engine-20261115/policy-flop-btn-bb-fixed.json.gz')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(StrategyError,'INCOMPLETE_STREETS'):
                disk_copy(source,Path(tmp)/'flop.sqlite')

    def test_probabilities_are_not_silently_rounded_to_float32(self):
        source=make_test_policy();state=source.root;actions=source.actions(state)
        rows=source.nodes[state.key()]['combos'];raw={k:[r['frequencies'][a.id] for a in actions] for k,r in rows.items()}
        encoded=stored_node(state,actions,rows,raw)
        decoded=decoded_node(encoded,source.ranges)
        for key in rows:self.assertEqual(decoded['combos'][key]['frequencies'],rows[key]['frequencies'])

    def test_matrix_disagreeing_with_validated_frequencies_is_rejected(self):
        source=make_test_policy();s=source.root;actions=source.actions(s);rows=source.nodes[s.key()]['combos']
        with tempfile.TemporaryDirectory() as tmp:
            w=PolicyWriter(Path(tmp)/'bad.sqlite',source.context,s,source.ranges,source.menu)
            try:
                raw={k:[1.]+[0.]*(len(actions)-1) for k in rows}
                with self.assertRaisesRegex(StrategyError,'DISAGREES'):
                    w.add(s,actions,rows,native_probabilities=raw)
            finally:w.close()

    def test_node_tampering_is_detected_before_advice(self):
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as resources:
            path=Path(tmp)/'p.sqlite';disk_copy(self.turn,path)
            with closing(sqlite3.connect(path)) as db,db:
                db.execute('UPDATE nodes SET payload=? WHERE key=?',(b'corrupt',self.turn.root.key()))
            disk=DiskPolicy(path);resources.callback(disk.close)
            with self.assertRaises(Exception):disk.nodes[self.turn.root.key()]

    def test_existing_artifact_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'keep.sqlite';path.write_bytes(b'keep')
            with self.assertRaisesRegex(StrategyError,'ALREADY_EXISTS'):
                PolicyWriter(path,self.turn.context,self.turn.root,self.turn.ranges,self.turn.menu)
            self.assertEqual(path.read_bytes(),b'keep')


class StreamCounterexamples(unittest.TestCase):
    def test_stream_without_final_root_is_not_a_complete_policy(self):
        p=make_test_policy()
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'native.gz'
            with gzip.open(source,'wt') as f:f.write('')
            with self.assertRaisesRegex(StrategyError,'TRUNCATED_NO_ROOT'):
                compact_stream(source,Path(tmp)/'out.sqlite',p.context,p.root,p.ranges,p.menu,{'units_per_bb':1000,'target_exploitability_pct_pot':.5},{},[])

    def test_stream_record_from_another_schema_is_rejected(self):
        p=make_test_policy()
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'native.gz'
            with gzip.open(source,'wt') as f:f.write(json.dumps(dict(schema='summary-only'))+'\n')
            with self.assertRaisesRegex(StrategyError,'SCHEMA_MISMATCH'):
                compact_stream(source,Path(tmp)/'out.sqlite',p.context,p.root,p.ranges,p.menu,{'units_per_bb':1000,'target_exploitability_pct_pot':.5},{},[])


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.resources=ExitStack();self.addCleanup(self.resources.close)
        self.folder=Path(self.resources.enter_context(tempfile.TemporaryDirectory()))
        self.policy=CompiledPolicy.load(TURN_POLICY)
        path=self.folder/'turn.sqlite';self.result=disk_copy(self.policy,path,native_matrix=True)
        from strategy.texassolver_backend import file_hash
        index=dict(schema='software.hu-policy-library.v1',entries=[dict(board=list(self.policy.root.board[:3]),path=path.name,
                   file_sha256=file_hash(path),policy_sha256=self.result['policy_sha256'])])
        self.index=self.folder/'library.json';atomic_json(self.index,index)

    def test_lookup_routes_to_the_exact_board_and_rejects_an_unknown_board(self):
        bank=PolicyLibrary(self.index);policy=bank.open(self.policy.root.board)
        self.resources.callback(policy.close)
        self.assertEqual(policy.fingerprint,self.result['policy_sha256'])
        with self.assertRaisesRegex(StrategyError,'NOT_YET_IN_VALIDATED'):
            bank.open(['Ac','8d','4s'])

    def test_library_rejects_duplicate_boards_instead_of_picking_a_random_model(self):
        index=json.loads(self.index.read_text());index['entries']*=2;atomic_json(self.index,index)
        with self.assertRaisesRegex(StrategyError,'AMBIGUOUS'):PolicyLibrary(self.index)

    def test_changed_policy_file_cannot_pass_the_archived_checksum(self):
        (self.folder/'turn.sqlite').write_bytes(b'corrupt')
        with self.assertRaisesRegex(StrategyError,'FILE_CHANGED'):PolicyLibrary(self.index).open(self.policy.root.board)

    def test_startup_preparation_avoids_hashing_a_large_file_again_at_decision_time(self):
        bank=PolicyLibrary(self.index);bank.prepare()
        with patch('strategy.policy_library.file_hash',side_effect=AssertionError('unexpected full file read during decision')):
            policy=bank.open(self.policy.root.board);self.resources.callback(policy.close)
            self.assertEqual(policy.fingerprint,self.result['policy_sha256'])

    def test_capacity_counts_retained_policies_separately_from_reusable_working_space(self):
        size=(self.folder/'turn.sqlite').stat().st_size
        usage=shutil._ntuple_diskusage(100*1024**3,0,40*1024**3)
        with patch('strategy.batch_jobs.shutil.disk_usage',return_value=usage):
            result=storage_capacity(self.folder/'turn.sqlite',self.folder,count=100,work_disk_mb=8192,safety_factor=1)
        self.assertEqual(result['estimated_required_bytes'],100*size+(8192+512)*1024**2)
        self.assertEqual(result['estimated_additional_flops_fitting'],(usage.free-(8192+512)*1024**2)//size)

    def test_runtime_generates_advice_and_resets_at_the_next_hand(self):
        history=LibraryHistory(PolicyLibrary(self.index),None,profile_settings={'require_preflop_witness':False})
        self.resources.callback(history.close)
        state=apply_action(self.policy.root,Action('check'))
        for i in range(2):
            result,b=reading(state,hero=('Ah','Qh'))
            out=history.observe(result,table_id='t',buttons=b,sample_id=str(i))
        self.assertEqual(out['status'],'CONFIRMED',out)
        advice=history.observer.advise(table_key='t',hand_key='h1',table_state=result['table_state'],
            hero_cards=result['hero_cards'],board=state.board,mode='chip_ev',stage='mid')
        self.assertEqual(advice['status'],'ADVICE',advice)
        result,b=reading(state,hero=('Ah','Qh'),hand='next-hand')
        out=history.observe(result,table_id='t',buttons=b,sample_id='next')
        self.assertEqual(out['status'],'PENDING');self.assertNotIn('strategy_state',result['table_state'])


class QueueFailureTests(unittest.TestCase):
    def test_disk_monitor_tolerates_a_sqlite_journal_deleted_before_stat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);journal=root/'policy.sqlite-journal';journal.write_bytes(b'transient')
            (root/'policy.sqlite').write_bytes(b'persist')
            original=Path.stat;reads=[0]
            def race(path,*args,**kwargs):
                if path==journal and kwargs.get('follow_symlinks',True):
                    reads[0]+=1
                    if reads[0]==2:journal.unlink()
                return original(path,*args,**kwargs)
            with patch.object(Path,'stat',race):self.assertEqual(folder_bytes(root),7)
            self.assertFalse(journal.exists())

    def test_disk_monitor_does_not_hide_permission_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/'policy.sqlite';target.write_bytes(b'persist');original=Path.stat
            def denied(path,*args,**kwargs):
                if path==target:raise PermissionError('control-denied')
                return original(path,*args,**kwargs)
            with patch.object(Path,'stat',denied),self.assertRaises(PermissionError):folder_bytes(root)

    def make_environment(self,tmp):
        root=Path(tmp);binary=root/'binary';binary.write_bytes(b'control-plane-only')
        resources=root/'resources';(resources/'compairer').mkdir(parents=True)
        (resources/'compairer/card5_dic_sorted.txt').write_bytes(b'control-plane-only')
        plan=make_plan(FLOP_GAME,boards=['As 7d 2c','Kd 8h 3c'])
        path=root/'plan.json';atomic_json(path,plan)
        return path,root/'bank',binary,resources

    def test_failed_job_preserves_evidence_and_continues_to_the_next(self):
        failed=type('Process',(),{'pid':os.getpid(),'returncode':1,'poll':lambda s:1})
        with tempfile.TemporaryDirectory() as tmp,patch('strategy.batch_jobs.subprocess.Popen',side_effect=lambda *a,**k:failed()) as launch:
            plan,out,binary,resources=self.make_environment(tmp)
            result=run_queue(plan,out,binary,resources)
            self.assertEqual(result,{'FAILED':2});self.assertEqual(launch.call_count,2)
            self.assertEqual(len(list((out/'temporary').iterdir())),2)
            self.assertEqual(json.loads((out/'library.json').read_text())['complete_flops'],0)

    def test_max_cases_limits_failed_attempts_too(self):
        failed=type('Process',(),{'pid':os.getpid(),'returncode':1,'poll':lambda s:1})
        with tempfile.TemporaryDirectory() as tmp,patch('strategy.batch_jobs.subprocess.Popen',side_effect=lambda *a,**k:failed()) as launch:
            plan,out,binary,resources=self.make_environment(tmp)
            result=run_queue(plan,out,binary,resources,max_cases=1)
            self.assertEqual(result,{'FAILED':1,'PENDING':1});self.assertEqual(launch.call_count,1)

    def test_one_driver_at_a_time(self):
        if os.name=='nt':self.skipTest('Windows byte-lock contract is checked natively')
        with tempfile.TemporaryDirectory() as tmp:
            with queue_lock(Path(tmp)):
                with self.assertRaisesRegex(StrategyError,'ALREADY_RUNNING'):
                    with queue_lock(Path(tmp)):pass


@unittest.skipUnless(os.environ.get('HU_STREAM_TEST_BINARY') and os.environ.get('HU_STREAM_TEST_RESOURCES'),
                     'Optional separately built native backend required')
class NativeEndToEndTests(unittest.TestCase):
    def test_stream_matches_nested_export_of_the_same_solve_including_suit_isomorphism(self):
        from strategy.hu_engine import load_game
        from strategy.texassolver_backend import input_commands,import_strategy
        root_source=json.loads(FLOP_GAME.read_text())
        root_source['root']['board']=['As','7s','2s'];root_source['root']['stacks']=[1,1]
        root_source['ranges']=[ComboRange.from_classes({'QQ':1},'native-parity-only').to_dict(),
                               ComboRange.from_classes({'JJ':1},'native-parity-only').to_dict()]
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as resources:
            root=Path(tmp);atomic_json(root/'game.json',root_source)
            context,state,ranges,menu=load_game(root/'game.json')
            commands,settings=input_commands(context,state,ranges,menu,iterations=11,dump_rounds=3,native_raise_limit=2)
            self.assertTrue(settings['suit_isomorphism'])
            commands=commands.replace('dump_result strategy.json','dump_result_stream stream.gz\ndump_result strategy.json')
            (root/'input.txt').write_text(commands)
            with (root/'log.txt').open('w') as log:
                subprocess.run([os.environ['HU_STREAM_TEST_BINARY'],'-i',str(root/'input.txt'),'-r',os.environ['HU_STREAM_TEST_RESOURCES']],
                               cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
            metrics=[json.loads(s) for s in (root/'tmp_log.txt').read_text().splitlines() if s.strip()]
            nested=CompiledPolicy(import_strategy(json.loads((root/'strategy.json').read_text()),context,state,ranges,menu,settings,{},metrics))
            report=compact_stream(root/'stream.gz',root/'policy.sqlite',context,state,ranges,menu,settings,{},metrics)
            disk=DiskPolicy(root/'policy.sqlite');resources.callback(disk.close)
            self.assertEqual(len(disk.nodes),len(nested.nodes))
            self.assertEqual(set(report['coverage']['nodes_by_street']),{'FLOP','TURN','RIVER'})
            for key,node in nested.nodes.items():
                other=disk.nodes[key];self.assertEqual(BettingState.from_dict(node['state']),BettingState.from_dict(other['state']))
                self.assertEqual(node['actions'],other['actions'])
                for combo,row in node['combos'].items():self.assertEqual(row['frequencies'],other['combos'][combo]['frequencies'])

    def test_two_real_workers_advance_batches_cleanup_and_resume_without_recalculation(self):
        source=json.loads(FLOP_GAME.read_text());source['root']['stacks']=[1,1]
        source['ranges']=[ComboRange.from_classes({'QQ':1},'native-integration-only').to_dict(),
                          ComboRange.from_classes({'JJ':1},'native-integration-only').to_dict()]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);atomic_json(root/'game.json',source)
            plan=make_plan(root/'game.json',boards=['As 7d 2c','Kd 8h 3c'],batch_size=1,iterations=11,memory_mb=2048)
            atomic_json(root/'plan.json',plan)
            result=run_queue(root/'plan.json',root/'bank',os.environ['HU_STREAM_TEST_BINARY'],os.environ['HU_STREAM_TEST_RESOURCES'])
            self.assertEqual(result,{'COMPLETE':2});self.assertEqual(list((root/'bank/temporary').iterdir()),[])
            index=json.loads((root/'bank/library.json').read_text());self.assertEqual(len(index['entries']),2)
            for entry in index['entries']:
                proof=query_probe(root/'bank'/entry['path']);self.assertEqual(set(proof['probes']),{'flop','turn','river'})
                report=json.loads((root/'bank/reports'/(entry['case_id']+'.json')).read_text())
                kept={Path(item['path']).name for item in report['diagnostics']}
                self.assertIn('native-input.txt',kept);self.assertIn('native-tmp_log.txt',kept)
                for item in report['diagnostics']:
                    self.assertTrue((root/'bank'/item['path']).is_file())
            with patch('strategy.batch_jobs.subprocess.Popen',side_effect=AssertionError('already calculated')):
                resumed=run_queue(root/'plan.json',root/'bank',os.environ['HU_STREAM_TEST_BINARY'],os.environ['HU_STREAM_TEST_RESOURCES'])
            self.assertEqual(resumed,{'COMPLETE':2})
            # Crash after a validated file was promoted but before checkpoint/index
            # publication. Resume must verify it and clean only its owned attempt.
            cid=index['entries'][0]['case_id'];attempt=root/'bank/temporary'/'interrupted-publication';attempt.mkdir()
            atomic_json(attempt/'owned-by-batch.json',dict(plan_sha256=plan['plan_sha256']))
            with closing(sqlite3.connect(root/'bank/progress.sqlite3')) as db,db:
                db.execute("UPDATE jobs SET state='VALIDATED',attempt=? WHERE id=?",(str(attempt),cid))
            (root/'bank/library.json').unlink()
            with patch('strategy.batch_jobs.subprocess.Popen',side_effect=AssertionError('validated job must not retrain')):
                self.assertEqual(run_queue(root/'plan.json',root/'bank',os.environ['HU_STREAM_TEST_BINARY'],os.environ['HU_STREAM_TEST_RESOURCES']),{'COMPLETE':2})
            self.assertFalse(attempt.exists());self.assertTrue((root/'bank/library.json').is_file())

if __name__=='__main__':unittest.main()
