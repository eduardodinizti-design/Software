"""JSON decisions and optional complete JSONL export with bounded node memory.

The bot's normal format is library.json plus indexed SQLite policies. JSONL is
an interoperability export, not a second in-memory copy of a multi-GB tree.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from strategy.batch_jobs import atomic_json
from strategy.policy_library import PolicyLibrary
from strategy.state_contract import BettingState,DecisionState,GameContext,StrategyError
from strategy.strategy_decision import choose
from strategy.texassolver_backend import file_hash


def query(library_path,request):
    library=PolicyLibrary(library_path);state=BettingState.from_dict(request['state'])
    policy=library.open(state.board)
    try:
        if GameContext(**request['context'])!=policy.context:raise StrategyError('JSON_REQUEST_CONTEXT_DIFFERS_FROM_POLICY')
        result=choose(policy,DecisionState(policy.context,state,tuple(request['hero_cards']),
            str(request['table_id']),str(request['hand_id'])))
        if result['status']!='ADVICE':raise StrategyError('JSON_REQUEST_HAS_NO_STORED_ADVICE:'+str(result))
        return dict(schema='software.hu-json-decision.v1',request=request,decision=result,
            policy_sha256=policy.fingerprint,execution_requested=False,input_devices_used=False,
            pppoker_windows_validated=False)
    finally:policy.close()


def export_complete(policy,output):
    output=Path(output);partial=output.with_name(output.name+'.partial')
    if output.exists() or partial.exists():raise StrategyError('JSON_EXPORT_DESTINATION_MUST_BE_NEW')
    output.parent.mkdir(parents=True,exist_ok=True)
    count=0;streets=Counter();sha=hashlib.sha256()
    def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    try:
        with partial.open('xb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',compresslevel=1,mtime=0) as out:
            header=dict(type='header',schema='software.hu-full-policy-jsonl.v1',
                source_policy_sha256=policy.fingerprint,metadata=policy.data,
                expected_public_nodes=len(policy.nodes),frequencies='EXACT_NORMALIZED_LOOKUP_VALUES')
            line=encoded(header);out.write(line);sha.update(line)
            for key in policy.nodes:
                node=policy.get_node(key);record=encoded(dict(type='node',key=key,node=node))
                out.write(record);sha.update(record);count+=1;streets[BettingState.from_dict(node['state']).street]+=1
            out.write(encoded(dict(type='footer',public_nodes=count,nodes_by_street=dict(streets),payload_sha256=sha.hexdigest())))
        if count!=len(policy.nodes):raise StrategyError('JSON_EXPORT_DID_NOT_INCLUDE_ALL_PUBLIC_NODES')
        partial.replace(output)
    except BaseException:
        partial.unlink(missing_ok=True);raise
    return dict(status='PASS',schema='software.hu-full-policy-json-export.v1',file=output.name,
        bytes=output.stat().st_size,sha256=file_hash(output),source_policy_sha256=policy.fingerprint,
        public_nodes=count,nodes_by_street=dict(streets),all_private_combo_frequencies_included=True,
        all_configured_actions_and_sizes_included=True,source_policy_modified=False)


def verify_export(path,policy):
    sha=hashlib.sha256();count=0;streets=Counter();seen_footer=False;seen_header=False
    expected=iter(policy.nodes)
    with gzip.open(path,'rb') as source:
        for raw in source:
            value=json.loads(raw)
            if count==0 and value.get('type')=='header':
                if seen_header:raise StrategyError('JSON_EXPORT_DUPLICATE_HEADER')
                if value['source_policy_sha256']!=policy.fingerprint or value['metadata']!=policy.data:
                    raise StrategyError('JSON_EXPORT_HEADER_CHANGED')
                seen_header=True;sha.update(raw);continue
            if not seen_header:raise StrategyError('JSON_EXPORT_MISSING_HEADER')
            if value.get('type')=='footer':
                if (next(expected,None) is not None or count!=len(policy.nodes) or value['public_nodes']!=count or value['nodes_by_street']!=dict(streets)
                        or value['payload_sha256']!=sha.hexdigest()):raise StrategyError('JSON_EXPORT_INCOMPLETE_OR_CHANGED')
                if source.read(1):raise StrategyError('JSON_EXPORT_HAS_DATA_AFTER_FOOTER')
                seen_footer=True;break
            if (value.get('type')!='node' or value['key']!=next(expected,None)
                    or value['node']!=policy.get_node(value['key'])):
                raise StrategyError('JSON_EXPORT_NODE_FREQUENCIES_OR_SIZES_CHANGED')
            count+=1;streets[BettingState.from_dict(value['node']['state']).street]+=1;sha.update(raw)
    if not seen_footer:raise StrategyError('JSON_EXPORT_MISSING_COMPLETION_FOOTER')
    return dict(status='PASS',public_nodes=count,exactly_matches_stored_policy=True)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('query','export'))
    p.add_argument('--library',required=True);p.add_argument('--output',required=True)
    p.add_argument('--request');p.add_argument('--flop',nargs=3);args=p.parse_args(argv)
    if Path(args.output).exists():p.error('Use a new output path')
    if args.command=='query':
        if not args.request:p.error('query requires --request JSON')
        result=query(args.library,json.loads(Path(args.request).read_text()));atomic_json(args.output,result)
    else:
        if not args.flop:p.error('export requires --flop')
        policy=PolicyLibrary(args.library).open(args.flop)
        try:result=export_complete(policy,args.output);result['roundtrip_validation']=verify_export(args.output,policy)
        finally:policy.close()
        atomic_json(str(args.output)+'.manifest.json',result)
    print(json.dumps(dict(status='PASS',output=args.output,command=args.command)));return 0


if __name__=='__main__':raise SystemExit(main())
