"""A3 — testes do escalonador por prazo (anti-timeout multi-mesa). Puro, determinístico
(passa `now` explícito, sem relógio real)."""
import unittest

from action_scheduler import DeadlineScheduler


class DeadlineSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.s = DeadlineScheduler(default_budget_s=12.0)

    def test_espera_mais_longa_primeiro_sem_relogio(self):
        self.s.observe('A', True, now=0.0)
        self.s.observe('B', True, now=1.0)
        self.s.observe('C', True, now=2.0)
        self.assertEqual(self.s.order(now=3.0), ['A', 'B', 'C'])   # A espera há mais tempo
        self.assertEqual(self.s.next_due(now=3.0), 'A')

    def test_relogio_curto_pula_a_fila(self):
        self.s.observe('A', True, now=0.0)                         # prazo efetivo = 12.0
        self.s.observe('B', True, now=5.0, seconds_left=2.0)       # prazo real = 7.0 (mais urgente)
        self.assertEqual(self.s.next_due(now=5.0), 'B')
        self.assertEqual(self.s.order(now=5.0), ['B', 'A'])

    def test_relogio_longo_nao_passa_na_frente_de_espera_velha(self):
        self.s.observe('A', True, now=0.0)                         # efetivo 12.0
        self.s.observe('B', True, now=1.0, seconds_left=30.0)      # real 31.0 (menos urgente)
        self.assertEqual(self.s.order(now=2.0), ['A', 'B'])

    def test_served_tira_da_fila(self):
        self.s.observe('A', True, now=0.0)
        self.s.observe('B', True, now=1.0)
        self.s.served('A')
        self.assertEqual(self.s.order(now=2.0), ['B'])
        self.assertEqual(len(self.s), 1)

    def test_pending_false_tira_da_fila(self):
        self.s.observe('A', True, now=0.0)
        self.s.observe('A', False, now=1.0)
        self.assertEqual(self.s.next_due(now=2.0), None)

    def test_reobservar_mantem_first_seen(self):
        self.s.observe('A', True, now=0.0)
        self.s.observe('A', True, now=5.0)                         # re-visita: não reseta espera
        self.assertEqual(self.s.effective_deadline('A'), 12.0)     # 0.0 + 12, não 5.0 + 12

    def test_deadline_so_aperta_nunca_relaxa(self):
        self.s.observe('A', True, now=0.0, seconds_left=10.0)      # prazo 10.0
        self.s.observe('A', True, now=1.0, seconds_left=20.0)      # tentaria 21.0 -> ignora (relaxa)
        self.assertEqual(self.s.effective_deadline('A'), 10.0)
        self.s.observe('A', True, now=2.0, seconds_left=1.0)       # 3.0 -> aperta -> adota
        self.assertEqual(self.s.effective_deadline('A'), 3.0)

    def test_mesa_reaparece_apos_served_reseta_espera(self):
        self.s.observe('A', True, now=0.0)
        self.s.served('A')
        self.s.observe('A', True, now=10.0)                        # nova vez -> first_seen novo
        self.assertEqual(self.s.effective_deadline('A'), 22.0)

    def test_fila_vazia(self):
        self.assertEqual(self.s.next_due(now=0.0), None)
        self.assertEqual(self.s.order(now=0.0), [])

    def test_empate_desempata_estavel(self):
        self.s.observe('B', True, now=0.0)
        self.s.observe('A', True, now=0.0)                         # mesmo first_seen/prazo
        self.assertEqual(self.s.order(now=1.0), ['A', 'B'])        # desempate por table_key

    def test_seconds_left_negativo_ignorado(self):
        self.s.observe('A', True, now=0.0, seconds_left=-5.0)      # inválido -> sem prazo lido
        self.assertEqual(self.s.effective_deadline('A'), 12.0)     # cai no orçamento padrão


if __name__ == '__main__':
    unittest.main()
