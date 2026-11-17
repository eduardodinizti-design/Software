"""One lab verification: new three-player rules plus existing HU contracts."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULES = ('test_multiway_study', 'test_multiway_bb_defense', 'test_hu_policy_engine',
    'test_hu_policy_json', 'test_hu_operational')
FILES = ('strategy/multiway_state.py', 'strategy/multiway_study.py',
    'strategy/multiway_bb_defense.py', 'test_multiway_bb_defense.py',
    'tools/prepare_multiway_pilot.py', 'tools/verify_multiway_pilot.py',
    'test_multiway_study.py', 'hrc/MP_BTN_BB40_MENU.js',
    'docs/multiway-mp-btn-bb40-20261116/referencias-nvt.json')
HU_FILES = ('operar_mesa.py', 'hu_executor.py', 'strategy/state_contract.py',
    'strategy/action_tree.py', 'strategy/policy_library.py', 'strategy/confirmed_history.py',
    'strategy/texassolver_backend.py')
BASE = 'b8187c3756b4c67f1eb026436f45df536d59c7ff'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Pasta nova para provas')
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('Preserve a verificacao anterior: escolha uma pasta nova')
    args.output.mkdir(parents=True)
    started = time.monotonic()
    with (args.output / 'regressao.txt').open('w', encoding='utf-8') as log:
        with redirect_stdout(log), redirect_stderr(log):
            suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    preserved = {}
    for name in HU_FILES:
        prior = subprocess.check_output(['git', 'show', f'{BASE}:{name}'], cwd=ROOT)
        preserved[name] = hashlib.sha256(prior).hexdigest() == hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    ok = result.wasSuccessful() and not result.skipped and all(preserved.values())
    value = dict(schema='software.multiway-pilot-lab-verification.v1',
        status='PASS' if ok else 'FAIL', os=platform.platform(), python=sys.version,
        tests_run=result.testsRun,
        passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
        errors=len(result.errors), failures=len(result.failures),
        skipped=[dict(test=str(t), reason=r) for t, r in result.skipped],
        elapsed_seconds=time.monotonic()-started, modules=list(MODULES),
        tested_file_sha256={name:hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES},
        original_hu_code_unchanged=preserved, preserved_hu_base_commit=BASE,
        synthetic_hands_in_rule_tests=True, optimized_multiway_policies_calculated=0,
        hrc_script_test='NODE_MOCK_OF_DOCUMENTED_API_NOT_REAL_HRC',
        hrc_native_executed=False, real_pppoker_validated=False, gameplay_input_sent=False)
    (args.output / 'resultado.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(value), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
