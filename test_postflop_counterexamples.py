"""Fase 1 (contraproposta v2) — os 4 contraexemplos da auditoria pós-flop, como
testes que afirmam o comportamento CORRETO.

Origem: branch de auditoria `audit/postflop-synthesis-20261114` (commit 96d447e),
probe `docs/audit-posflop-20261114/probes/policy_counterexamples.py`. Reproduzem,
contra o `advise_postflop` REAL do `e51718c`, quatro decisões erradas (verificadas
localmente: 4/4 violam a expectativa analítica).

Cada caso é `@unittest.expectedFailure`: a asserção é o comportamento CERTO, que
HOJE falha (documenta o bug) sem quebrar a suíte verde. Quando o motor for corrigido
(Fase 1), o teste vira "unexpected success" -> remover o decorador e virar guard.

Estados analíticos sintéticos; não certificam solver nem pixel/PPPoker."""
import unittest

from postflop_advisor import advise_postflop


def _table(pot=30, call=10, stack=100):
    """Mesa mínima como o probe oficial a monta: hero + 1 vilão ativos."""
    return {'pot': {'pot_bb': pot}, 'to_call': {'to_call_bb': call},
            'seats': {'hero': {'occupied': True, 'in_hand': True, 'stack_bb': stack},
                      'v': {'occupied': True, 'in_hand': True, 'stack_bb': 100}}}


class PostflopCounterexampleTests(unittest.TestCase):
    """Cada teste trava uma decisão que o motor atual erra. expectedFailure até Fase 1."""

    def test_occupied_seats_are_not_active_opponents(self):
        # CONSERTADO: 7 assentos foldados (in_hand=False) não contam como oponentes;
        # n_opp=1 -> sem penalidade multiway -> AA (trinca) bate KK -> não folda.
        s = _table()
        for i in range(7):
            s['seats']['folded%d' % i] = {'occupied': True, 'in_hand': False, 'stack_bb': 100}
        a = advise_postflop(s, ['As', 'Ad'], ['Ac', 'Kh', '7d', '2c', '3s'],
                            pot_type='single_raised', villain_range=['KK'], iters=100)
        self.assertNotEqual(a.get('recommended'), 'fold')   # fix: contar oponentes ATIVOS

    def test_three_bet_branch_respects_supplied_range(self):
        # CONSERTADO: 77 full vs [AA] quadra -> o ramo 3bet computa a equidade vs a range
        # e folda o monstro dominado (equity < pot odds), em vez de comprometer por categoria.
        a = advise_postflop(_table(), ['7h', '7d'], ['Ac', 'Ad', '7c', '2d', '3s'],
                            pot_type='three_bet', villain_range=['AA'], iters=100)
        self.assertEqual(a.get('recommended'), 'fold')      # fix: equidade vs range, nunca commit null

    def test_mdf_uses_pot_after_opponent_bet(self):
        # CONSERTADO: pote 20 já inclui a aposta de 10; call 10. MDF = (pot-call)/pot =
        # 10/20 = 0.5 (antes 0.6667, que usava o denominador errado).
        a = advise_postflop(_table(pot=20, call=10), ['As', 'Ad'], ['Ac', 'Kh', '7d', '2c', '3s'],
                            pot_type='single_raised', villain_range=['KK'], iters=100)
        self.assertAlmostEqual(a.get('mdf', 0.0), 0.5, places=6)

    def test_guaranteed_chop_is_a_call(self):
        # CONSERTADO: board royal -> CHOP garantido; pote 1010, call 1000 -> CALL (+5BB).
        # Detecção: plays_board + river + equity>=0.5 -> lock, paga sem haircut.
        a = advise_postflop(_table(pot=1010, call=1000, stack=5000), ['2c', '3d'],
                            ['As', 'Ks', 'Qs', 'Js', 'Ts'],
                            pot_type='single_raised', villain_range=['AA'], iters=100)
        self.assertEqual(a.get('recommended'), 'call')      # fix: empate garantido é +EV


if __name__ == '__main__':
    unittest.main()
