"""Robustez do operador p/ horas (BACKLOG D2/D3). Testes puros."""
import unittest

from operator_robustness import BoundedKeySet, CaptureWatch, raise_outcome, reconcile_targets


class BoundedKeySetTests(unittest.TestCase):
    def test_add_e_contains(self):
        s = BoundedKeySet(maxlen=3)
        s.add(('t1', 'h1'))
        self.assertIn(('t1', 'h1'), s)
        self.assertNotIn(('t1', 'h2'), s)

    def test_descarta_o_mais_antigo_ao_exceder(self):
        s = BoundedKeySet(maxlen=2)
        s.add('a'); s.add('b'); s.add('c')     # 'a' deve sair
        self.assertNotIn('a', s)
        self.assertIn('b', s)
        self.assertIn('c', s)
        self.assertEqual(len(s), 2)

    def test_reuso_renova_recencia(self):
        s = BoundedKeySet(maxlen=2)
        s.add('a'); s.add('b')
        self.assertIn('a', s)                  # toca 'a' -> vira o mais recente
        s.add('c')                             # agora 'b' é o mais antigo -> sai
        self.assertIn('a', s)
        self.assertNotIn('b', s)

    def test_readicionar_nao_duplica_e_renova(self):
        s = BoundedKeySet(maxlen=2)
        s.add('a'); s.add('b'); s.add('a'); s.add('c')  # 'a' renovado -> 'b' sai
        self.assertIn('a', s); self.assertIn('c', s); self.assertNotIn('b', s)

    def test_discard(self):
        s = BoundedKeySet(maxlen=3)
        s.add('a'); s.discard('a'); s.discard('x')      # discard inexistente não quebra
        self.assertNotIn('a', s)

    def test_nao_cresce_alem_do_teto_em_milhares(self):
        s = BoundedKeySet(maxlen=256)
        for i in range(10000):
            s.add(('mesa%d' % i, 'mao%d' % i))
        self.assertEqual(len(s), 256)          # sem vazamento


class CaptureWatchTests(unittest.TestCase):
    def test_alerta_no_limiar_e_reset(self):
        w = CaptureWatch(alert_after=3, repeat=10)
        alerts = [w.fail(1)[1] for _ in range(3)]
        self.assertEqual(alerts, [False, False, True])     # alerta na 3a falha
        w.ok(1)
        self.assertEqual(w.consecutive(1), 0)
        self.assertFalse(w.fail(1)[1])                      # zerou -> recomeça

    def test_realerta_periodico_apos_limiar(self):
        w = CaptureWatch(alert_after=5, repeat=30)
        seen = [i + 1 for i in range(70) if w.fail(9)[1]]   # falhas que alertaram
        self.assertEqual(seen, [5, 35, 65])                 # 5, depois a cada 30

    def test_janelas_independentes(self):
        w = CaptureWatch(alert_after=2, repeat=5)
        w.fail(1)
        self.assertEqual(w.consecutive(1), 1)
        self.assertEqual(w.consecutive(2), 0)               # hwnd 2 intacto
        self.assertTrue(w.fail(1)[1])                       # 2a falha do 1 -> alerta


class RaiseOutcomeTests(unittest.TestCase):
    def test_ok_submetida_nunca_retenta(self):
        # ok=True = confirmar saiu (aposta submetida) -> done, mesmo confirmed=False
        self.assertEqual(raise_outcome(dict(ok=True, confirmed=True), 0)[0], 'done')
        self.assertEqual(raise_outcome(dict(ok=True, confirmed=False), 1)[0], 'done')

    def test_unknown_confirmar_nao_saiu_retenta_ate_cap(self):
        unk = dict(ok=False, unknown=True, maybe_sent=True, reason='CONFIRMAR_CANCELADO')
        d1, a1 = raise_outcome(unk, 0, max_attempts=2)
        self.assertEqual((d1, a1), ('retry', 1))
        d2, a2 = raise_outcome(unk, a1, max_attempts=2)
        self.assertEqual((d2, a2), ('giveup', 2))   # cap -> desiste (não trava)

    def test_fail_antes_do_confirmar_tambem_retenta(self):
        fail = dict(ok=False, reason='ALVO_AUSENTE')
        self.assertEqual(raise_outcome(fail, 0)[0], 'retry')


class ReconcileTargetsTests(unittest.TestCase):
    def _w(self, h):
        return dict(hwnd=h, x=0, y=0, w=400, h=700)

    def test_adiciona_mesa_nova_e_dropa_fechada(self):
        # operava 1 e 2; agora so existem 2 e 3 -> add 3 (balanceamento), drop 1
        add, drop, by = reconcile_targets([1, 2], [self._w(2), self._w(3)])
        self.assertEqual(add, [3])
        self.assertEqual(drop, [1])
        self.assertIn(3, by)

    def test_allowlist_restringe_novos(self):
        add, drop, _ = reconcile_targets([1], [self._w(1), self._w(9)], allow={1, 2})
        self.assertEqual(add, [])          # 9 nao esta no allow -> nao adiciona

    def test_respeita_teto_max_targets(self):
        disc = [self._w(h) for h in range(1, 20)]
        add, _, _ = reconcile_targets([1], disc, max_targets=5)
        self.assertEqual(len(add), 4)      # 1 ja operado + 4 novos = teto 5

    def test_sem_mudanca_nada_a_fazer(self):
        add, drop, _ = reconcile_targets([1, 2], [self._w(1), self._w(2)])
        self.assertEqual((add, drop), ([], []))


if __name__ == '__main__':
    unittest.main()
