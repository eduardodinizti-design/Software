"""Fase 1 (percepção): to_call por derivação das apostas + cruzamento com o botão.

Invariantes exercitadas:
- NUNCA inventar: sem aposta lida -> abstain (None).
- O botão em BB é autoritário; a derivação PREENCHE quando o botão não traz 'BB'.
- Concordância -> confiança alta; discordância -> mantém o botão e MARCA o conflito.
Testes puros (sem imagem/OCR)."""
import unittest

from table_reading.table_state import derive_to_call, merge_to_call


class DeriveToCallTests(unittest.TestCase):
    def test_open_hero_bb_enfrenta_raise(self):
        # hero (BB) postou 1, vilão abriu p/ 3 -> to_call = 2
        bets = [dict(seat='hero', bet_bb=1.0), dict(seat='top_center', bet_bb=3.0)]
        r = derive_to_call(bets)
        self.assertEqual(r['to_call_bb'], 2.0)
        self.assertEqual(r['source'], 'derived_from_bets')
        self.assertEqual(r['confidence'], 'medium')

    def test_hero_sem_aposta_conta_como_zero(self):
        # hero ainda não colocou ficha; vilão abriu 2.5 -> to_call = 2.5
        bets = [dict(seat='top_left', bet_bb=2.5)]
        self.assertEqual(derive_to_call(bets)['to_call_bb'], 2.5)

    def test_hero_cobre_a_maior_aposta_to_call_zero(self):
        bets = [dict(seat='hero', bet_bb=3.0), dict(seat='left_up', bet_bb=3.0)]
        self.assertEqual(derive_to_call(bets)['to_call_bb'], 0.0)

    def test_ignora_bet_none_e_abstem_sem_apostas(self):
        self.assertIsNone(derive_to_call([dict(seat='hero', bet_bb=None)])['to_call_bb'])
        self.assertIsNone(derive_to_call([])['to_call_bb'])
        self.assertEqual(derive_to_call([])['confidence'], 'abstain')


class MergeToCallTests(unittest.TestCase):
    def test_botao_bb_manda_quando_sozinho(self):
        btn = dict(to_call_bb=2.0, confidence='high', source='call_button')
        r = merge_to_call(btn, dict(to_call_bb=None, confidence='abstain'))
        self.assertEqual(r['to_call_bb'], 2.0)
        self.assertEqual(r['confidence'], 'high')

    def test_derivado_preenche_quando_botao_abstem(self):
        # é o GANHO: botão sem 'BB' -> abstém; derivação preenche
        btn = dict(to_call_bb=None, confidence='abstain', source='call_button_unit_unknown')
        der = dict(to_call_bb=2.0, confidence='medium', source='derived_from_bets')
        r = merge_to_call(btn, der)
        self.assertEqual(r['to_call_bb'], 2.0)
        self.assertEqual(r['source'], 'derived_from_bets')

    def test_concordancia_sobe_confianca(self):
        btn = dict(to_call_bb=2.0, confidence='high', source='call_button')
        der = dict(to_call_bb=2.1, confidence='medium', source='derived_from_bets')
        r = merge_to_call(btn, der)
        self.assertEqual(r['to_call_bb'], 2.0)
        self.assertEqual(r['source'], 'call_button+derived_agree')
        self.assertEqual(r['confidence'], 'high')

    def test_discordancia_mantem_botao_e_marca(self):
        btn = dict(to_call_bb=2.0, confidence='high', source='call_button')
        der = dict(to_call_bb=6.0, confidence='medium', source='derived_from_bets')
        r = merge_to_call(btn, der)
        self.assertEqual(r['to_call_bb'], 2.0)  # o jogo exibido é a verdade
        self.assertTrue(any(c.startswith('DERIVED_DISAGREES') for c in r.get('caveats', [])))

    def test_check_zero_preservado(self):
        btn = dict(to_call_bb=0.0, confidence='high', source='check_button')
        r = merge_to_call(btn, dict(to_call_bb=None, confidence='abstain'))
        self.assertEqual(r['to_call_bb'], 0.0)

    def test_ambos_ausentes_abstem(self):
        r = merge_to_call(dict(to_call_bb=None), dict(to_call_bb=None))
        self.assertIsNone(r['to_call_bb'])
        self.assertEqual(r['source'], 'no_to_call')


if __name__ == '__main__':
    unittest.main()
