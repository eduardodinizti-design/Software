"""hand_db: dedup de adversários por id canônico (junta variações de caixa do OCR)."""
import unittest

from hand_db import by_opponent, canonical_id


class CanonicalTests(unittest.TestCase):
    def test_junta_caixa_e_pontuacao(self):
        self.assertEqual(canonical_id('TyTwot'), canonical_id('Tytwot'))
        self.assertEqual(canonical_id('sacatrapoo'), 'sacatrapoo')
        self.assertEqual(canonical_id(' Vory.Sky '), 'vorysky')

    def test_conservador_nao_funde_troca_de_char(self):
        self.assertNotEqual(canonical_id('VorySky'), canonical_id('Vory5ky'))

    def test_vazio(self):
        self.assertEqual(canonical_id(None), '')


class ByOpponentDedupTests(unittest.TestCase):
    def test_dedup_por_caixa_do_ocr(self):
        hands = [
            {'opponents': [{'id': 'TyTwot', 'hud': {'vpip': 33}}], 'result': {}},
            {'opponents': [{'id': 'Tytwot'}], 'result': {}},
            {'opponents': [{'id': 'sacatrapoo'}], 'result': {}},
        ]
        opp = by_opponent(hands)
        self.assertEqual(len(opp), 2)                       # TyTwot+Tytwot = 1 vilão
        ty = next(k for k in opp if k.casefold() == 'tytwot')
        self.assertEqual(opp[ty]['hands'], 2)               # as 2 mãos somadas
        self.assertEqual(opp[ty]['hud_last'], {'vpip': 33})

    def test_net_bb_agrega_com_dedup(self):
        hands = [
            {'opponents': [{'id': 'Fish'}], 'result': {'delta_bb': 5.0}},
            {'opponents': [{'id': 'fish'}], 'result': {'delta_bb': -2.0}},
        ]
        opp = by_opponent(hands)
        self.assertEqual(len(opp), 1)
        self.assertEqual(next(iter(opp.values()))['net_bb'], 3.0)


if __name__ == '__main__':
    unittest.main()
