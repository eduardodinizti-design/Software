"""Trava o sizing de aposta pós-flop no NOSSO slider (Eduardo 19/11): 1/3,1/2,2/3,allin,
e a exceção do Plano Geométrico no turn por SPR. Garante que todo `bet` pós-flop carrega
um alvo executável (size_bb) — base do 'nao morrer no pos-flop'."""
import unittest

import postflop_sizing as ps


def _adv(**kw):
    base = dict(phase='postflop', status='ADVICE', recommended='bet', street='FLOP')
    base.update(kw)
    return base


class SnapTests(unittest.TestCase):
    def test_075_vira_dois_tercos(self):
        # heuristica beta 0.75 -> fora do slider -> encaixa em 2/3
        a = ps.enforce(_adv(sizing=dict(size_bb=4.1, fraction=0.75)), pot_bb=5.5, stack_bb=38)
        self.assertEqual(a['sizing']['bucket'], '2/3')
        self.assertAlmostEqual(a['sizing']['size_bb'], round(5.5 * 2 / 3, 1))

    def test_033_e_05_preservados(self):
        a = ps.enforce(_adv(sizing=dict(size_bb=1.8, fraction=0.33)), pot_bb=5.5, stack_bb=38)
        self.assertEqual(a['sizing']['bucket'], '1/3')
        b = ps.enforce(_adv(sizing=dict(size_bb=2.75, fraction=0.5)), pot_bb=5.5, stack_bb=38)
        self.assertEqual(b['sizing']['bucket'], '1/2')

    def test_size_from_size_bb_quando_sem_fraction(self):
        a = ps.enforce(_adv(sizing=dict(size_bb=3.6)), pot_bb=5.5, stack_bb=38)  # 3.6/5.5=0.65
        self.assertEqual(a['sizing']['bucket'], '2/3')

    def test_tag_de_caveat(self):
        a = ps.enforce(_adv(sizing=dict(fraction=0.33)), pot_bb=5.5, stack_bb=38)
        self.assertIn('POSTFLOP_SIZE_1_3', a['caveats'])


class AllinCommitTests(unittest.TestCase):
    def test_size_perto_do_stack_vira_allin(self):
        # pote grande, stack curto: 2/3 do pote >= 90% do stack -> all-in, sem stub
        a = ps.enforce(_adv(sizing=dict(fraction=0.66)), pot_bb=20, stack_bb=12)
        self.assertEqual(a['sizing']['bucket'], 'allin')
        self.assertAlmostEqual(a['sizing']['size_bb'], 12.0)


class GeometricTurnTests(unittest.TestCase):
    def test_turn_geometrico_so_com_aposta_grande(self):
        # cérebro PEDE 2/3 (stack-off), SPR na faixa -> plano geométrico, CAPADO no pote
        a = ps.enforce(_adv(street='TURN', sizing=dict(fraction=0.67), spr=3.8),
                       pot_bb=9.5, stack_bb=36)
        self.assertEqual(a['sizing']['bucket'], 'geo')
        self.assertIn('geometric_plan', a['sizing'])
        self.assertIn('POSTFLOP_SIZE_GEOMETRICO_TURN', a['caveats'])
        self.assertGreater(a['sizing']['size_bb'], 9.5 * 2 / 3)   # geométrico > 2/3 aqui
        self.assertLessEqual(a['sizing']['size_bb'], 9.5 + 1e-6)  # NUNCA overbet (capado no pote)

    def test_turn_geometrico_nao_infla_value_bet_padrao(self):
        # Pós-mortem #5: o cérebro pede c-bet 1/3 (range-bet) num turn de SPR alto. O
        # geométrico NÃO pode transformar isso em pote cheio/overbet -> fica no 1/3.
        a = ps.enforce(_adv(street='TURN', sizing=dict(fraction=0.33), spr=3.8),
                       pot_bb=14.6, stack_bb=58)
        self.assertEqual(a['sizing']['bucket'], '1/3')
        self.assertLessEqual(a['sizing']['size_bb'], 14.6 * 2 / 3)

    def test_turn_geometrico_nao_infla_controle(self):
        # cérebro pede 1/2 (controle de pote, mão vulnerável) -> respeitado, não vira geo
        a = ps.enforce(_adv(street='TURN', sizing=dict(fraction=0.5), spr=3.8),
                       pot_bb=9.5, stack_bb=36)
        self.assertEqual(a['sizing']['bucket'], '1/2')

    def test_turn_spr_deep_nao_overbeta(self):
        # Pós-mortem #5 (caso 2): pote minúsculo + SPR enorme fazia o geométrico pedir
        # overbet (2.5x) que esnapava em 1 POT. Fora da faixa de SPR -> slider padrão ≤2/3.
        a = ps.enforce(_adv(street='TURN', sizing=dict(fraction=0.33), spr=13.3),
                       pot_bb=3.0, stack_bb=40)
        self.assertNotEqual(a['sizing']['bucket'], 'geo')
        self.assertLessEqual(a['sizing']['size_bb'], 3.0 * 2 / 3 + 1e-6)

    def test_turn_big_deep_cai_no_teto_2_3_sem_overbet(self):
        # mesmo com aposta grande (2/3), SPR deep (fora da faixa) -> 2/3, nunca overbet
        a = ps.enforce(_adv(street='TURN', sizing=dict(fraction=0.67), spr=13.3),
                       pot_bb=6.0, stack_bb=80)
        self.assertEqual(a['sizing']['bucket'], '2/3')
        self.assertLessEqual(a['sizing']['size_bb'], 6.0 * 2 / 3 + 1e-6)

    def test_turn_spr_baixo_fica_no_slider(self):
        a = ps.enforce(_adv(street='TURN', sizing=dict(fraction=0.5), spr=0.8),
                       pot_bb=9.5, stack_bb=8)
        self.assertIn(a['sizing']['bucket'], ('1/2', 'allin'))    # não geométrico

    def test_flop_nunca_e_geometrico(self):
        a = ps.enforce(_adv(street='FLOP', sizing=dict(fraction=0.67), spr=3.5),
                       pot_bb=5.5, stack_bb=38)
        self.assertNotEqual(a['sizing']['bucket'], 'geo')


class GuardTests(unittest.TestCase):
    def test_idempotente(self):
        a = ps.enforce(_adv(sizing=dict(fraction=0.75)), pot_bb=5.5, stack_bb=38)
        first = dict(a['sizing'])
        ps.enforce(a, pot_bb=5.5, stack_bb=38)
        self.assertEqual(a['sizing'], first)

    def test_check_call_fold_intactos(self):
        for rec in ('check', 'call', 'fold'):
            a = ps.enforce(_adv(recommended=rec, sizing=dict(size_bb=0.0)), pot_bb=5.5, stack_bb=38)
            self.assertNotIn('bucket_enforced', a.get('sizing', {}))

    def test_raise_nao_e_snapado(self):
        # raise pós-flop tem base própria (raise-to), não fração de pote
        a = ps.enforce(_adv(recommended='raise', sizing=dict(size_bb=9.0)), pot_bb=5.5, stack_bb=38)
        self.assertNotIn('bucket_enforced', a.get('sizing', {}))

    def test_preflop_intacto(self):
        a = ps.enforce(dict(phase='preflop', status='ADVICE', recommended='bet',
                            sizing=dict(size_bb=2.0)), pot_bb=1.5, stack_bb=40)
        self.assertNotIn('bucket_enforced', a.get('sizing', {}))


if __name__ == '__main__':
    unittest.main()
