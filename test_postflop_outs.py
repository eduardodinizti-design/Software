"""Manipulação de outs (Pós-flop Avançado): LIMPEZA (draw forte -> aposta grande folda
dominadores, limpa outs) vs MANUTENÇÃO (mão feita mediana -> pequeno/check mantém as
dominadas do vilão por implied). Classificador puro + tags no conselho (auditoria)."""
import unittest

from postflop_adjustments import out_manipulation
from postflop_advisor import advise_postflop


def st(pot, tocall, stack=40):
    return dict(pot=dict(pot_bb=pot), to_call=dict(to_call_bb=tocall),
                hero=dict(stack_bb=stack), n_opponents=1)


class Classificador(unittest.TestCase):
    def test_draw_forte_limpeza(self):
        om = out_manipulation('overcards', {'combo': True})
        self.assertEqual(om['intent'], 'limpeza')
        self.assertEqual(om['size_hint'], 'big')
        self.assertEqual(out_manipulation('air', {'oesd': True})['intent'], 'limpeza')
        self.assertEqual(out_manipulation('air', {'flush_draw': True})['intent'], 'limpeza')

    def test_mao_feita_mediana_manutencao(self):
        for made in ('top_pair', 'second_pair', 'third_pair', 'low_pair', 'underpair'):
            om = out_manipulation(made, {})
            self.assertEqual(om['intent'], 'manutencao', made)
            self.assertEqual(om['size_hint'], 'small', made)

    def test_nutada_e_ar_puro_none(self):
        self.assertIsNone(out_manipulation('set', {'combo': True}))    # nut: valor direto
        self.assertIsNone(out_manipulation('two_pair', {}))
        self.assertIsNone(out_manipulation('air', {}))                 # ar puro: blefe, não outs


class TagsNoConselho(unittest.TestCase):
    def test_semibluff_tagueia_limpeza(self):
        a = advise_postflop(st(6, 0), ['Jh', 'Th'], ['9h', '8c', '2d'], aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertIn('OUT_MANIP_LIMPEZA', a['caveats'])

    def test_top_pair_aposta_tagueia_manutencao(self):
        a = advise_postflop(st(6, 0), ['Ah', 'Qc'], ['Ac', '9d', '3h'], aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertIn('OUT_MANIP_MANUTENCAO', a['caveats'])

    def test_top_pair_cbeta_polar_tagueia_manutencao(self):
        # PFR agressivo: c-beta o top pair em board de c-bet-range, mantendo a tag de outs
        a = advise_postflop(st(6, 0), ['9h', 'Kc'], ['9c', '6d', '2h'], aggressor='hero')
        self.assertEqual(a['recommended'], 'bet')
        self.assertIn('OUT_MANIP_MANUTENCAO', a['caveats'])


if __name__ == '__main__':
    unittest.main()
