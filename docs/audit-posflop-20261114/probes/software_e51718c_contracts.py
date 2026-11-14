"""Synthetic audit cases for Software e51718c; no capture or operating-system input.

The selection and epoch cases expose missing evidence/invalidation contracts,
not observed PPPoker clicks. Histories below are invented analytical fixtures.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
args = parser.parse_args()
root = args.root.resolve()
sys.path.insert(0, str(root))

from anticipation import AnticipationStore, TurnEpochTracker
from hand_history import parse_hand_histories
from hero_card_memory import HeroCardMemory
from leak_audit import audit_text
from raise_plan import plan_raise, verify_selected_preset

presets = [dict(mult=float(v), label=f'{v}x', box=[0, 0, 20, 10]) for v in (2, 3, 4)]
plan = plan_raise(6.0, presets)
selection = verify_selected_preset(dict(presets=presets), 3.0)
empty = audit_text('')

royal = """PPPoker Hand #9001: Tournament #1, Hold'em No Limit (0.5/1)
Table 'Synthetic royal' 2-max Seat #1 is the button
Seat 1: Hero (2000 in chips)
Seat 2: Villain (2000 in chips)
Hero: posts small blind 0.5
Villain: posts big blind 1
Dealt to Hero [2c 3d]
Hero: raises 4.5 to 5
Villain: calls 4
*** FLOP *** [As Ks Qs]
Hero: checks
Villain: checks
*** TURN *** [As Ks Qs] [Js]
Hero: checks
Villain: checks
*** RIVER *** [As Ks Qs Js] [Ts]
Hero: checks
Villain: bets 1000
Hero: calls 1000
*** SHOW DOWN ***
"""
royal_report = audit_text(royal, 'Hero')
royal_decision = [d for d in parse_hand_histories(royal, 'Hero')[0].hero_decisions
                  if d['street'] == 'RIVER' and d['hero_action'] == 'call'][0]
royal_call_mistakes = [m for m in royal_report['top_mistakes']
                      if 'CALL' in m['example_spot'] and m['affected_street'] == 'River']

multiway = """PPPoker Hand #9002: Tournament #1, Hold'em No Limit (1/2)
Table 'Synthetic line' 3-max Seat #3 is the button
Seat 1: Bettor (200 in chips)
Seat 2: Caller (200 in chips)
Seat 3: Hero (200 in chips)
Bettor: posts small blind 1
Caller: posts big blind 2
Dealt to Hero [Ac Qd]
Hero: calls 2
Bettor: calls 1
Caller: checks
*** FLOP *** [As 7d 2c]
Bettor: bets 4
Caller: calls 4
Hero: calls 4
*** TURN *** [As 7d 2c] [3s]
Bettor: bets 10
Caller: calls 10
Hero: calls 10
"""
line_decision = [d for d in parse_hand_histories(multiway, 'Hero')[0].hero_decisions
                 if d['street'] == 'TURN'][0]

epochs = TurnEpochTracker()
store = AnticipationStore()
old_epoch = epochs.on_turn('table', 'hand')
store.prepare('table', ('hand', old_epoch),
              dict(status='ADVICE', phase='preflop', recommended='check', validated=True),
              old_epoch, ['2c', '3d'])
for _ in range(2):
    epochs.on_nonturn('table')
# A new street can appear without changing the hand key. The operator supplies
# only the epoch as fingerprint, not fresh board, street, prices or candidates.
new_epoch = epochs.on_turn('table', 'hand')
reused = store.take('table', ('hand', new_epoch), new_epoch, {'CHECK'}, ['2c', '3d'])

memory = HeroCardMemory(votes=2)
for _ in range(2):
    memory.observe('table', 'hand', ['Qd', '5h'])
for _ in range(5):
    memory.observe('table', 'hand', ['Kd', '5h'])

cases = [
    dict(id='ordinary_raise_above_menu_is_not_all_in',
         input=dict(target_mult=6, presets=[2, 3, 4], hero_stack_bb=100,
                    explicit_all_in_intent=False), actual=plan,
         expected='Do not infer ALL_IN merely from exceeding the largest preset.',
         satisfies=plan['kind'] != 'SHOVE'),
    dict(id='preset_presence_does_not_prove_selected_amount',
         actual=dict(ok=selection[0], reason=selection[1]),
         scope='Contract gap: the function sees the unchanged menu only, no selected-value evidence.',
         expected='Selection/BB amount must be confirmed separately before submission.'),
    dict(id='no_graded_decisions_are_not_grade_A',
         actual={k: empty[k] for k in ('overall_grade', 'decisions_reviewed', 'total_hands_detected')},
         expected='UNASSESSED / no eligible decisions, not a positive poker grade.',
         satisfies=empty['overall_grade'] != 'A'),
    dict(id='guaranteed_profitable_chop_call_is_not_a_leak',
         synthetic_decision=royal_decision, exact_incremental_call_ev_bb=5.0,
         actual=royal_call_mistakes,
         expected='No call mistake: equity is exactly 0.5 on the royal board.',
         satisfies=not royal_call_mistakes),
    dict(id='passive_caller_is_not_aggressive_bettor',
         actual=dict(villain_line=line_decision['villain_line']),
         input='Bettor bets flop and turn; Caller only calls; hero faces turn bet.',
         expected='No passive-to-aggressive classification of Bettor from Caller contributions.',
         satisfies=line_decision['villain_line'] is None),
    dict(id='street_change_requires_more_than_same_epoch',
         actual=dict(old_epoch=old_epoch, new_epoch=new_epoch, reused=reused),
         scope='Pure invalidation contract; no executed wrong action is claimed.',
         expected='A fresh street/board fingerprint must invalidate a preflop payload.',
         satisfies=reused is None),
    dict(id='accepted_card_conflict_diagnostic', actual=dict(pair=memory.pair('table', 'hand'),
                                                           stats=memory.stats),
         scope='Availability design observation, not an independent accuracy benchmark.')
]
output = dict(scope='All states and histories synthetic; no screen, mouse, game, registration or AI API.',
              commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              cases=cases, violations=sum(c.get('satisfies') is False for c in cases))
print(json.dumps(output, ensure_ascii=False, indent=2))
sys.exit(1 if output['violations'] else 0)
