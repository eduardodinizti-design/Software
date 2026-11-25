"""TRAVA do detector do modal "Confirma saída?" do PPPoker (offline, fixture real).
Garante que o modal é detectado NO PAINEL CERTO (o do meio, com o modal) e NÃO nos painéis
normais (sem falso-positivo) — sem baixar limiar p/ forçar (AGENTS.md). Pula se a fixture some.
Ver [[nvt-multitable-tiled-bug]]."""
import os
import unittest

import cv2

import ppp_modal

FIX = os.path.join(os.path.dirname(__file__), "research", "ppp_il2cpp",
                   "multitable_tiled_20261120.png")
# banda de conteúdo (3 colunas iguais) confirmada: x 1924..3998
PANELS = [(1924, 2615), (2615, 3306), (3306, 3998)]


@unittest.skipUnless(os.path.exists(FIX), "fixture tilada ausente")
class ExitModalDetect(unittest.TestCase):

    def setUp(self):
        self.img = cv2.imread(FIX)

    def test_modal_detectado_so_no_painel_do_meio(self):
        hits = ppp_modal.find_exit_confirm_modal(self.img, PANELS)
        self.assertEqual(len(hits), 1, "esperava 1 modal, veio %r" % hits)
        h = hits[0]
        self.assertEqual(h["panel"], 1)                       # painel do meio
        cx, cy = h["confirmar_center"]
        self.assertTrue(abs(cx - 3079) <= 40 and abs(cy - 943) <= 40,
                        "centro do Confirmar fora do esperado: %r" % (h["confirmar_center"],))
        self.assertIn("SAIDA", h["hazard"])                   # marcado como PERIGO

    def test_paineis_laterais_sem_modal(self):
        # só os painéis normais (sem o do meio) -> nenhum modal (sem falso-positivo)
        hits = ppp_modal.find_exit_confirm_modal(self.img, [PANELS[0], PANELS[2]])
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
