"""TRAVA do gate de 1º clique da Suprema (offline, sem janela/sem clicar): o FoldGate só libera
UM clique, só de FOLD, só armado, e desarma após disparar (one-shot)."""
import unittest

import suprema_act as A
from suprema_operar import FoldGate


class FoldGateTest(unittest.TestCase):

    def test_desarmado_nunca_clica(self):
        g = FoldGate(armed=False)
        self.assertEqual(g.decide({'action': A.FOLD}), 'dry')

    def test_armado_so_fold_dispara(self):
        g = FoldGate(armed=True)
        self.assertEqual(g.decide({'action': A.RAISE, 'preset': '3X'}), 'dry')   # raise NÃO
        self.assertEqual(g.decide({'action': A.CALL}), 'dry')                    # call NÃO
        self.assertEqual(g.decide({'action': A.CHECK}), 'dry')                   # check NÃO
        self.assertEqual(g.decide({'action': A.FOLD}), 'click')                  # fold SIM

    def test_one_shot_desarma_apos_disparar(self):
        g = FoldGate(armed=True)
        self.assertEqual(g.decide({'action': A.FOLD}), 'click')
        g.mark_fired()
        self.assertEqual(g.decide({'action': A.FOLD}), 'dry')    # já disparou: volta a dry-run
        self.assertFalse(g.armed)

    def test_wait_abstain_sem_alvo(self):
        g = FoldGate(armed=True)
        self.assertEqual(g.decide({'action': A.WAIT}), 'skip')
        self.assertEqual(g.decide({'action': A.ABSTAIN}), 'skip')
        self.assertEqual(g.decide({'action': None}), 'skip')
        self.assertEqual(g.decide(None), 'skip')


if __name__ == '__main__':
    unittest.main()
