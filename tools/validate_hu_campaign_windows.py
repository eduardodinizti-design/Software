"""Download a real policy and exercise JSON, suit routing and confirmed history."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_download import install_catalog
from strategy.batch_jobs import atomic_json
from strategy.campaign_download import load_family
from strategy.policy_json import query
from strategy.policy_library import PolicyLibrary
from strategy.state_contract import StrategyError
from verify_hu_next16_download import verify_delivery


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--family',required=True,choices=('btn32','sb40','sb40-next16','sb40-34'))
    p.add_argument('--ordinal',required=True,type=int);p.add_argument('--catalog-asset',required=True)
    p.add_argument('--output',required=True);args=p.parse_args(argv)
    if platform.system()!='Windows':raise StrategyError('NATIVE_WINDOWS_REQUIRED')
    root=Path(args.output)
    if root.exists():raise StrategyError('WINDOWS_VALIDATION_OUTPUT_MUST_BE_NEW')
    root.mkdir(parents=True);catalog,asset=load_family(args.family,args.catalog_asset,new_only=True)
    receipt=install_catalog(root/'download',catalog,asset,ordinals=[args.ordinal])
    result=verify_delivery(root/'download/download-receipt.json',root/'windows-proof.json',
        ordinal=args.ordinal,require_windows=True,verify_hand=True)
    proof=receipt['policies'][0];policy=PolicyLibrary(receipt['library']).open(proof['board'])
    try:
        for street,probe in proof['lookup_validation']['probes'].items():
            request=dict(context=asdict(policy.context),state=policy.get_node(probe['node_id'])['state'],
                hero_cards=probe['hero_cards'],table_id='json-transfer-validation',hand_id='json-'+street)
            atomic_json(root/('request-'+street+'.json'),request)
            response=query(receipt['library'],json.loads((root/('request-'+street+'.json')).read_text()))
            if response['decision']['candidates']!=probe['candidates']:raise StrategyError('JSON_TRANSCRIPTION_CHANGED_FREQUENCIES_OR_SIZES')
            atomic_json(root/('response-'+street+'.json'),response)
        result.update(family=args.family,json_roundtrip_streets=['flop','turn','river'],
            complete_model_parameters=policy.data,all_json_responses_exactly_match_stored_policy=True)
        if args.family in ('sb40-next16','sb40-34'):
            from strategy.root_policy_review import review_root_policy
            result['root_policy_review']=review_root_policy(policy)
        atomic_json(root/'windows-proof.json',result)
    finally:policy.close()
    print(json.dumps(dict(status='PASS',family=args.family,ordinal=args.ordinal,
        json_streets=3,confirmed_hand=result['confirmed_hand']['event_counts'])));return 0


if __name__=='__main__':raise SystemExit(main())
