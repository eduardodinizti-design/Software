"""Bundle small Windows evidence; the complete immutable bank stays separate."""
import argparse
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_jobs import atomic_json


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True)
    p.add_argument('--run-id',required=True,type=int);p.add_argument('--run-url',required=True)
    args=p.parse_args(argv);root=Path(args.root);delivery=root/'delivery';delivery.mkdir(exist_ok=True)
    def read(path):return json.loads((root/path).read_text(encoding='utf-8-sig'))
    receipt=read('download/download-receipt.json');hand=read('download/verification/result.json')
    river=read('river-exact.json');owned=read('owned/resultado.json');alias=read('alias-validation/result.json')
    if (receipt['policy_sha256']!=hand['policy_sha256'] or receipt['policy_sha256']!=river['source_policy_sha256']
            or hand['status']!='PASS' or not hand['complete_to_showdown']
            or not hand['hero_selected_actions_match_lab_actions'] or not river['exact_enumeration']):
        raise SystemExit('Reference evidence does not refer to one validated policy')
    if alias.get('status')!='PASS' or alias['quality'].get('source_policy_sha256')!=receipt['policy_sha256']:
        raise SystemExit('Equivalent-suit hand is not bound to the same source policy')
    if (owned['status']!='PASS' or owned.get('native_owned_capture')!='PASS'
            or len(owned['cases'])!=6 or any(c['result']['state']!='DONE' for c in owned['cases'])):
        raise SystemExit('Owned-window executor evidence is incomplete')
    native_hand=owned.get('reference_hand') or {}
    if (native_hand.get('status')!='PASS' or native_hand.get('policy_sha256')!=receipt['policy_sha256']
            or native_hand.get('event_counts')!={'action':9,'board':2,'execution_confirmed':3}):
        raise SystemExit('Published reference did not complete three native input decisions')
    tests=(root/'contracts.txt').read_text(encoding='utf-8-sig')
    count=re.search(r'Ran (\d+) tests',tests);skip=re.search(r'OK \(skipped=(\d+)\)',tests)
    if not count or not re.search(r'^OK(?: \(|\s*$)',tests,re.M):raise SystemExit('Contract test result is not PASS')
    n=int(count[1]);skipped=int(skip[1]) if skip else 0
    summary=dict(status='PASS',platform=platform.platform(),source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        run_url=args.run_url,policy_sha256=receipt['policy_sha256'],native_target_met=receipt['native_target_met'],
        contract_tests=dict(tests_run=n,passed=n-skipped,skipped=skipped),
        downloaded_policy_hand=dict(source='ACTUAL_PUBLISHED_NVT_SOLVER_POLICY',scope=hand['scope'],
            event_counts=hand['event_counts'],decisions=hand['decisions'],chain_valid=hand['journal_chain_valid'],
            library_routing_tested=hand['library_routing_tested'],selected_actions_match=hand['hero_selected_actions_match_lab_actions'],
            input_devices_used=False,scenario_sampling=hand['scenario_sampling']),
        independent_river=dict(method=river['method'],scope=river['scope'],joint_private_deals=river['joint_private_deals'],
            nash_conv_bb=river['nash_conv_bb'],elapsed_seconds=river['elapsed_seconds'],policy_modified=False),
        exact_suit_routing=dict(status=alias['status'],source_policy_sha256=receipt['policy_sha256'],
            derived_policy_sha256=alias['policy_sha256'],board=alias['board'],complete_to_showdown=alias['complete_to_showdown']),
        native_executor=dict(scope=owned['scope'],capture=owned['native_owned_capture'],
            cases=[dict(kind=c['kind'],state=c['result']['state'],callbacks=c['callbacks']) for c in owned['cases']],
            generic_case_policies='SYNTHETIC_CONTROLLED_TEST_POLICIES',
            reference_hand=dict(scope=native_hand['scope'],status=native_hand['status'],
                policy_sha256=native_hand['policy_sha256'],event_counts=native_hand['event_counts'],
                complete_to_showdown=native_hand['complete_to_showdown'],callbacks=native_hand['callbacks'],
                pot_presets_used=native_hand['pot_presets_used'],
                steps=[dict(street=s['street'],state=s['result']['state'],confirmed=s['result']['confirmed']) for s in native_hand['steps']])),
        pppoker_windows_validated=False,user_notebook_validated=False)
    atomic_json(delivery/f'integracao-windows-referencia-{args.run_id}.json',summary)
    for source,name in (('download/verification/hand.json','mao-confirmada-referencia'),
            ('download/verification/decisions.json','decisoes-tres-ruas'),('river-exact.json','river-validacao-independente'),
            ('owned/mao-referencia-input-nativo.json','mao-referencia-input-nativo')):
        shutil.copyfile(root/source,delivery/f'{name}-{args.run_id}.json')
    text=json.dumps(summary,separators=(',',':')).replace('%','%25').replace('\r','%0D').replace('\n','%0A')
    print('::notice title=Downloaded reference Windows summary::'+text)
    return 0


if __name__=='__main__':raise SystemExit(main())
