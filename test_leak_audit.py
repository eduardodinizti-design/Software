"""Testes do auditor nativo de leaks pós-flop (sem IA)."""
import os
import unittest

from leak_audit import audit_text, audit_file

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures', 'pppoker_sample.txt')


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.r = audit_file(_FIX, 'Hero')

    def test_report_shape_and_counts(self):
        self.assertEqual(self.r['source'], 'native_brain_no_ai')
        self.assertEqual(self.r['total_hands_detected'], 5)
        self.assertEqual(self.r['postflop_hands_reviewed'], 5)
        self.assertGreaterEqual(self.r['decisions_reviewed'], 15)
        self.assertGreaterEqual(self.r['total_mistakes_found'], 5)
        self.assertIn(self.r['overall_grade'], ('A', 'B', 'C+', 'C', 'D'))

    def test_catches_known_leaks(self):
        cats = {t['category'] for t in self.r['top_mistakes']}
        self.assertIn('C-Bet de ar multi-way', cats)
        self.assertIn('Hero Call no River (pool underbluff)', cats)

    def test_spew_pool_recommends_tight(self):
        self.assertEqual(self.r['recommended_profile'], 'tight')

    def test_top_mistakes_sorted_by_severity(self):
        weight = dict(alta=3, media=2, baixa=1)
        ws = [weight[t['severity']] for t in self.r['top_mistakes']]
        self.assertEqual(ws, sorted(ws, reverse=True))
        # Frequências somam ~100% do total de leaks.
        self.assertAlmostEqual(sum(t['frequency_pct'] for t in self.r['top_mistakes']), 100.0, delta=0.5)

    def test_every_mistake_has_example_and_fix(self):
        for t in self.r['top_mistakes']:
            self.assertTrue(t['example_spot'])
            self.assertTrue(t['recommended_fix'])
            self.assertIn(t['affected_street'], ('Flop', 'Turn', 'River'))

    def test_deterministic(self):
        again = audit_file(_FIX, 'Hero')
        self.assertEqual(again['total_mistakes_found'], self.r['total_mistakes_found'])
        self.assertEqual([t['category'] for t in again['top_mistakes']],
                         [t['category'] for t in self.r['top_mistakes']])

    def test_empty_and_garbage(self):
        empty = audit_text('', 'Hero')
        self.assertEqual(empty['total_hands_detected'], 0)
        self.assertEqual(empty['total_mistakes_found'], 0)
        self.assertEqual(empty['overall_grade'], 'A')
        self.assertEqual(empty['top_mistakes'], [])


if __name__ == '__main__':
    unittest.main()
