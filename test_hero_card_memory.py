"""Testes da memória temporal das cartas do hero (votação por slot).

Simula a sequência de leituras por frame (candidatos por slot), como o operador os
teria do advise_table. Trava o invariante central: recupera o par mesmo quando
nenhum frame único lê as duas, SEM nunca inventar carta. Offline (AGENTS.md)."""
import unittest

from hero_card_memory import HeroCardMemory


class HeroCardMemoryTests(unittest.TestCase):
    def setUp(self):
        self.m = HeroCardMemory(votes=2)

    def test_monta_par_quando_cada_slot_atinge_os_votos(self):
        self.assertIsNone(self.m.observe('t', 'h', ['Qd', None]))   # 1 voto slot0
        self.assertIsNone(self.m.observe('t', 'h', ['Qd', None]))   # 2 votos slot0 -> aceito, slot1 vazio
        self.assertIsNone(self.m.observe('t', 'h', [None, '5h']))   # 1 voto slot1
        self.assertEqual(self.m.observe('t', 'h', [None, '5h']), ['Qd', '5h'])  # 2 votos slot1 -> par
        self.assertEqual(self.m.stats['assembled'], 1)

    def test_recupera_quando_nenhum_frame_tem_as_duas(self):
        # cada frame falha num slot diferente -> o cache antigo (par) nunca semearia
        seq = [['Qd', None], [None, '5h'], ['Qd', None], [None, '5h']]
        got = None
        for s in seq:
            got = self.m.observe('t', 'h', s)
        self.assertEqual(got, ['Qd', '5h'])

    def test_nunca_inventa_com_slot_sempre_ambiguo(self):
        for _ in range(10):
            self.m.observe('t', 'h', ['Qd', None])   # slot1 nunca lê
        self.assertIsNone(self.m.pair('t', 'h'))     # não fabrica a 2ª carta
        self.assertGreaterEqual(self.m.stats['ignored_ambiguous'], 10)

    def test_um_voto_nao_basta(self):
        self.assertIsNone(self.m.observe('t', 'h', ['Qd', '5h']))   # 1 voto cada -> ainda não
        self.assertEqual(self.m.observe('t', 'h', ['Qd', '5h']), ['Qd', '5h'])  # 2 votos cada

    def test_leader_isolado_resolve_voto_dividido(self):
        # slot0: 5h,5h,Jh -> 5h lidera 2x1; slot1 fixo
        self.m.observe('t', 'h', ['5h', 'Kd'])
        self.m.observe('t', 'h', ['Jh', 'Kd'])       # voto espúrio, empata 1x1 -> não aceita
        self.assertIsNone(self.m.pair('t', 'h'))
        self.assertEqual(self.m.observe('t', 'h', ['5h', 'Kd']), ['5h', 'Kd'])  # 5h 2x1 + Kd 3

    def test_empate_nao_aceita(self):
        self.m.observe('t', 'h', ['5h', 'Kd'])
        self.m.observe('t', 'h', ['Jh', 'Kd'])
        # slot0 empatado 5h:1 Jh:1 -> nunca aceita slot0, par fica None
        for _ in range(3):
            self.m.observe('t', 'h', ['Jh', 'Kd'])   # agora Jh lidera -> aceita Jh
        self.assertEqual(self.m.pair('t', 'h'), ['Jh', 'Kd'])

    def test_imutavel_nao_troca_e_conta_conflito(self):
        self.m.observe('t', 'h', ['Qd', '5h'])
        self.m.observe('t', 'h', ['Qd', '5h'])       # par aceito
        self.m.observe('t', 'h', ['Kd', '5h'])       # leitura divergente no slot0
        self.assertEqual(self.m.pair('t', 'h'), ['Qd', '5h'])  # mantém o aceito
        self.assertEqual(self.m.stats['conflicts'], 1)

    def test_par_identico_rejeitado(self):
        # dois slots lendo a MESMA carta é impossível (sem baralho duplo) -> não monta
        self.m.observe('t', 'h', ['Qd', 'Qd'])
        self.m.observe('t', 'h', ['Qd', 'Qd'])
        self.assertIsNone(self.m.pair('t', 'h'))

    def test_maos_e_mesas_isoladas(self):
        self.m.observe('t', 'h1', ['Qd', '5h']); self.m.observe('t', 'h1', ['Qd', '5h'])
        self.m.observe('t', 'h2', ['Ah', 'Kc']); self.m.observe('t', 'h2', ['Ah', 'Kc'])
        self.assertEqual(self.m.pair('t', 'h1'), ['Qd', '5h'])
        self.assertEqual(self.m.pair('t', 'h2'), ['Ah', 'Kc'])

    def test_invalidate_por_mao_e_mesa(self):
        self.m.observe('t', 'h1', ['Qd', '5h']); self.m.observe('t', 'h1', ['Qd', '5h'])
        self.m.observe('u', 'h1', ['Ah', 'Kc']); self.m.observe('u', 'h1', ['Ah', 'Kc'])
        self.m.invalidate('t', 'h1')
        self.assertIsNone(self.m.pair('t', 'h1'))
        self.assertIsNotNone(self.m.pair('u', 'h1'))
        self.m.invalidate('u')
        self.assertIsNone(self.m.pair('u', 'h1'))

    def test_mao_sem_id_nao_entra(self):
        self.assertIsNone(self.m.observe('t', None, ['Qd', '5h']))
        self.assertEqual(len(self.m), 0)

    def test_entrada_malformada_ignorada(self):
        self.assertIsNone(self.m.observe('t', 'h', None))
        self.assertIsNone(self.m.observe('t', 'h', ['Qd']))         # só 1 slot
        self.assertEqual(len(self.m), 0)

    def test_lru_limita(self):
        m = HeroCardMemory(limit=2, votes=1)
        for i in range(4):
            m.observe('t', 'h%d' % i, ['Qd', '5h'])
        self.assertEqual(len(m), 2)


if __name__ == '__main__':
    unittest.main()
