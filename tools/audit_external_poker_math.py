"""Passive mathematical probes of an existing dickreuter/Poker checkout.

Loads its real numeric class definitions with AST, leaving application imports,
GUI, capture, logging services and input entrypoints unexecuted. Upstream source
is not copied or modified. This is a defect reproduction, not a gameplay test.
"""
import argparse
import ast
from collections import Counter
from copy import copy
import hashlib
import json
import logging
import operator
from pathlib import Path
import subprocess
import sys
import time

import numpy as np


def numeric_class(repo, filename, name):
    path = repo / 'poker/decisionmaker' / filename
    tree = ast.parse(path.read_text())
    definition = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    space = dict(np=np, json=json, logging=logging, operator=operator, os=__import__('os'),
                 sys=sys, time=time, Counter=Counter, copy=copy,
                 get_dir=lambda _: str(repo / 'poker'))
    exec(compile(ast.Module(body=[definition], type_ignores=[]), str(path), 'exec'), space)
    return space[name]


def run(repo):
    mc = numeric_class(repo, 'montecarlo_python.py', 'MonteCarlo')()
    base = numeric_class(repo, 'base.py', 'DecisionBase')()
    logger = logging.getLogger('external-math-audit')
    royal = ['AS', 'KS', 'QS', 'JS', 'TS']
    np.random.seed(42)
    tied, _ = mc.run_montecarlo(logger, [['2C', '3D'], ['4C', '5D'], ['6C', '7D']], royal, 3, None,
                               max_runs=200, timeout=time.time() + 5, ghost_cards='', opponent_range=1)
    board = ['2C', '2D', '2H', '2S', 'AC']
    quad_a = ['KS', 'QD', *board]; quad_b = ['JS', '9D', *board]
    sa, sb = mc.calc_score(quad_a), mc.calc_score(quad_b)
    np.random.seed(13)
    outside = 0; first_example = None
    for _ in range(1000):
        hands, _, _ = mc.distribute_cards_to_players(mc.create_card_deck(), 2, [['AS', 'KS']], [], {'22'}, 0)
        if hands[1][0][0] != '2' or hands[1][1][0] != '2':
            outside += 1
            if first_example is None:first_example = hands[1]
    mc.use_range_of_range = False
    zero_range = mc.get_opponent_allowed_cards_list(0)
    known = [(0.2, 10., 2.5), (0.5, 10., 10.), (1., 10., 5.)]
    call_examples = [dict(equity=e, pot=p, call=c, actual=base.calc_call_EV(e,p,c),
                          expected=e*(p+c)-c) for e,p,c in known]
    cases = [
        dict(name='royal_board_threeway_split', expected=1/3, actual=tied,
             defect_reproduced=abs(tied-1/3)>.01),
        dict(name='shared_board_quads_ace_kicker', expected='equal_scores',
             actual=[sa,sb], defect_reproduced=sa!=sb),
        dict(name='restricted_22_range_keeps_actual_draw_in_range', expected=0,
             actual=outside, draws=1000, example=first_example, defect_reproduced=outside>0),
        dict(name='zero_requested_range_is_not_full_range', expected=0,
             actual=len(zero_range), defect_reproduced=len(zero_range)>0),
        dict(name='terminal_call_ev_identity', examples=call_examples,
             matches=all(abs(r['actual']-r['expected'])<1e-9 for r in call_examples)),
        dict(name='call_limit_with_certain_win', equity=1.,pot=10.,
             actual=float(base.calc_EV_call_limit(1.,10.)),
             limitation='Diagnostic only: the primary decision uses fitted curve limits, not this value.'),
    ]
    hashes={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [repo/'poker/decisionmaker/montecarlo_python.py',repo/'poker/decisionmaker/base.py']}
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    return dict(repository='dickreuter/Poker',commit=commit,source_hashes=hashes,
                scope='AST-isolated original numeric classes; synthetic known inputs; no upstream entrypoint, capture, input or strategy database.',
                cases=cases,all_four_defects_reproduced=all(c.get('defect_reproduced') for c in cases[:4]))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path)
    args=p.parse_args();result=run(args.repo.resolve())
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result['all_four_defects_reproduced'] else 1


if __name__=='__main__':raise SystemExit(main())
