"""Teste do analisador de prontidão por telemetria real. Estrutural (os números
dependem dos logs reais do repo); garante que roda e classifica de forma coerente."""
import unittest

import session_readiness as sr


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.r = sr.analyze()

    def test_roda_e_tem_estrutura(self):
        for k in ('sessions', 'total_decisions', 'status', 'abstain_reason',
                  'would_execute_commit', 'study_only_commit', 'safety_floor_exec',
                  'exec_rate_pct', 'validated'):
            self.assertIn(k, self.r)

    def test_processou_decisoes_reais(self):
        self.assertGreater(self.r['total_decisions'], 0)
        soma = (self.r['would_execute_commit'] + self.r['study_only_commit']
                + self.r['safety_floor_exec'] + self.r['status'].get('ABSTAIN', 0))
        # ADVICE com recomendação vazia pode sobrar; a soma nunca passa do total.
        self.assertLessEqual(soma, self.r['total_decisions'])

    def test_commit_armavel_exige_validacao(self):
        # Nenhum commit 'armável' pode vir de nó não-validado sem autoridade (gate).
        self.assertLessEqual(self.r['would_execute_commit'], self.r['validated'].get(True, 0))

    def test_taxas_coerentes(self):
        self.assertIsNotNone(self.r['exec_rate_pct'])
        self.assertGreaterEqual(self.r['abstain_rate_pct'], 0.0)
        self.assertLessEqual(self.r['abstain_rate_pct'], 100.0)


if __name__ == '__main__':
    unittest.main()
