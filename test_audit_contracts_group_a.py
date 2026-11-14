"""Grupo A (contraproposta v3, §ACEITE) — contratos da auditoria que apontam bugs no
código de HOJE, como testes que afirmam o comportamento CORRETO.

Origem: branch `audit/postflop-synthesis-20261114` (396820d), probes
`software_e51718c_contracts.py` e `paused_close_case.py`. Reproduzidos contra o código
real do `e51718c`. TODOS CONSERTADOS (viraram guard normal): zero-decisões≠A, street-change (invalidação
por rua), paused-close, raise-acima-do-menu≠shove (piso SHOVE_FLOOR_MULT), chop-vira-leak
(cascata do motor) e caller-passivo. Sem `@unittest.expectedFailure` restante.

Estados/históricos SINTÉTICOS reproduzidos no código; não certificam PPPoker/pixel/solver.
"""
import contextlib
import io
import unittest
from unittest.mock import Mock, patch

import numpy as np

from anticipation import AnticipationStore
from hand_history import parse_hand_histories
from leak_audit import audit_text
from raise_plan import plan_raise

_PRESETS = [dict(mult=float(v), label='%dx' % v, box=[0, 0, 20, 10]) for v in (2, 3, 4)]

_ROYAL = """PPPoker Hand #9001: Tournament #1, Hold'em No Limit (0.5/1)
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

_MULTIWAY = """PPPoker Hand #9002: Tournament #1, Hold'em No Limit (1/2)
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


class GroupAContractTests(unittest.TestCase):
    """Contratos do Grupo A. expectedFailure até a Entrega A/C corrigir o código de hoje."""

    def test_raise_above_menu_is_not_all_in(self):
        # CONSERTADO: alvo 6x com presets até 4x NÃO vira SHOVE. is_shove_target agora
        # exige o PISO absoluto (SHOVE_FLOOR_MULT=8x): "acima do maior preset" por pouco
        # (6x>4x) abstém (SEM_PRESET_NA_TOLERANCIA), não shova. 25x (jam) segue SHOVE.
        plan = plan_raise(6.0, _PRESETS)
        self.assertNotEqual(plan['kind'], 'SHOVE')
        self.assertEqual(plan['kind'], 'ABSTAIN')

    def test_zero_decisions_is_not_grade_A(self):
        # CONSERTADO: 0 decisões revisadas -> 'UNASSESSED', não nota "A".
        empty = audit_text('')
        self.assertNotEqual(empty['overall_grade'], 'A')
        self.assertEqual(empty['overall_grade'], 'UNASSESSED')

    def test_guaranteed_chop_call_is_not_a_leak(self):
        # CONSERTADO (cascata do chop): o advisor agora paga o empate garantido, então o
        # leak_audit não marca mais o call correto do hero como leak.
        rep = audit_text(_ROYAL, 'Hero')
        river_call_mistakes = [m for m in rep['top_mistakes']
                               if 'CALL' in m['example_spot'] and m['affected_street'] == 'River']
        self.assertEqual(river_call_mistakes, [])

    def test_passive_caller_is_not_aggressive_bettor(self):
        # CONSERTADO: 'passive_turned_aggressive' exige AGRESSÃO (bet/raise) após ter sido
        # passivo — um CALL não conta (antes `street_bet>0` pegava o caller junto).
        hand = parse_hand_histories(_MULTIWAY, 'Hero')[0]
        turn = [d for d in hand.hero_decisions if d['street'] == 'TURN'][0]
        self.assertIsNone(turn['villain_line'])

    def test_street_change_invalidates_preflop_payload(self):
        # CONSERTADO: o operador agora dobra a assinatura da RUA (_board_sig) na
        # impressão digital do payload: (época, (rua, nº cartas do board)). Mesma
        # mão/época, mas RUA diferente -> NÃO reusa a decisão pré-flop; mesma rua reusa.
        store = AnticipationStore()
        preflop = (1, (None, 0))      # época 1, sem board
        flop = (1, ('flop', 3))       # mesma época, board novo
        store.prepare('t', ('h', 1),
                      dict(status='ADVICE', phase='preflop', recommended='check', validated=True),
                      preflop, ['2c', '3d'])
        self.assertIsNone(store.take('t', ('h', 1), flop, {'CHECK'}, ['2c', '3d']))      # rua nova -> invalida
        self.assertIsNotNone(store.take('t', ('h', 1), preflop, {'CHECK'}, ['2c', '3d']))  # mesma rua -> reusa

    def test_paused_control_blocks_table_close(self):
        # CONSERTADO: com controle PAUSED, o fechamento de mesa NÃO recebe autorização
        # de input — o operador passa `args.arm and control.execution_allowed()`.
        import operar_mesa as op
        from bot_control import BotControl
        from table_reading.automatic_table_crops import TableCrop
        control = BotControl()
        advisor = Mock()
        advisor.manifest.return_value = dict(sources=[], index_keys=0, total_nodes=0, collisions=[])
        engine = Mock()
        engine.capture_frame.return_value = (np.zeros((700, 400, 3), np.uint8), {'status': 'SUCCESS'})
        closed = Mock(return_value=True)
        changes = dict(configure_ocr=Mock(), PreflopAdvisor=Mock(), BotControl=Mock(return_value=control),
                       WindowCaptureEngine=Mock(return_value=engine),
                       discover_pppoker=Mock(return_value={'windows': [dict(hwnd=1, x=0, y=0, w=400, h=700)]}),
                       detect_table_crops=Mock(return_value=[TableCrop((0, 0, 400, 700), 'COMPLETE_CANDIDATE', [], 'SIMULATED')]),
                       detect_tournament_end=Mock(return_value={'status': 'TOURNAMENT_END', 'ranking': 10, 'sair_box': [0, 0, 40, 20]}),
                       _close_tournament_table=closed, record_tournament_end=Mock())
        changes['PreflopAdvisor'].from_file.return_value = advisor
        changes['PreflopAdvisor'].from_files.return_value = advisor   # cobre o caminho deep
        with contextlib.ExitStack() as stack:
            for name, value in changes.items():
                stack.enter_context(patch.object(op, name, value))
            stack.enter_context(patch.object(op.time, 'sleep'))
            with contextlib.redirect_stdout(io.StringIO()):
                op.main(['--hwnd', '0x1', '--arm', '--frames', '1', '--no-hotkeys'])
        armed_arg = closed.call_args.args[-1]
        self.assertFalse(armed_arg)


if __name__ == '__main__':
    unittest.main()
