"""Testes da estratégia por vilão (villain_strategy) — exploratório, nunca executa."""
import unittest

import villain_strategy as vs


class PlanTests(unittest.TestCase):
    def test_desconhecido_sem_exploracao(self):
        p = vs.plan(None)
        self.assertEqual(p['category'], 'unknown')
        self.assertEqual(p['preflop'], [])
        self.assertEqual(p['postflop'], [])

    def test_station_corta_blefe_e_value_mais_fino(self):
        # vpip alto, foldcbet baixo -> fish/station.
        p = vs.plan(dict(vpip=55, pfr=10, steal=20, cr=5, threebet=2,
                         fold3bet=40, cbet=40, foldcbet=25))
        sits_post = {a['situation']: a for a in p['postflop']}
        self.assertIn('station', p['tags'])
        self.assertEqual(sits_post['c_bet_blefe']['direction'], 'less')
        self.assertEqual(sits_post['value_bet']['direction'], 'wider')

    def test_folds_to_cbet_barrel_mais(self):
        p = vs.plan(dict(vpip=24, pfr=18, steal=30, cr=3, threebet=6,
                         fold3bet=50, cbet=60, foldcbet=65))
        sits = {a['situation']: a for a in p['postflop']}
        self.assertIn('folds_to_cbet', p['tags'])
        self.assertEqual(sits['c_bet']['direction'], 'more')

    def test_3bet_happy_aperta_flat(self):
        p = vs.plan(dict(vpip=26, pfr=22, steal=35, cr=4, threebet=12,
                         fold3bet=30, cbet=55, foldcbet=45))
        sits = {a['situation']: a for a in p['preflop']}
        self.assertIn('3bet_happy', p['tags'])
        self.assertIn('flat_e_4bet', sits)

    def test_summary_e_string(self):
        p = vs.plan(dict(vpip=55, pfr=10, steal=20, cr=5, threebet=2,
                         fold3bet=40, cbet=40, foldcbet=25))
        self.assertIsInstance(p['summary'], str)
        self.assertIn('VilÃo'.upper()[:5], p['summary'].upper())

    def test_table_plan_por_assento(self):
        huds = {'s1': dict(vpip=55, pfr=10, steal=20, cr=5, threebet=2,
                           fold3bet=40, cbet=40, foldcbet=25),
                's2': None}
        tp = vs.table_plan(huds)
        self.assertIn('s1', tp)
        self.assertEqual(tp['s2']['category'], 'unknown')


if __name__ == '__main__':
    unittest.main()
