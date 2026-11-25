"""Regressão do detector de ADD-ON/re-entrada da Suprema (Eduardo 24/11). Fixtures = frames REAIS
capturados ao vivo: `drawer_clipped.png` (drawer de add-on presente, botão vermelho CORTADO pela
janela estreita) e `mesa_sem_drawer.png` (mesa normal, sem drawer). Pula se não houver tesseract
(o detector usa OCR p/ o padrão "Entradas X/Y")."""
import os
import unittest

import cv2

import suprema_addon as A

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "suprema_addon")
_HAS_TESS = any(os.path.exists(p) for p in (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"))


@unittest.skipUnless(_HAS_TESS, "tesseract não instalado (detector usa OCR)")
class TestSupremaAddon(unittest.TestCase):
    def _load(self, name):
        path = os.path.join(_FIX, name)
        if not os.path.exists(path):
            self.skipTest("fixture ausente (PNG gitignored): %s" % name)
        img = cv2.imread(path)
        self.assertIsNotNone(img, "fixture ilegível: %s" % name)
        return img

    def test_drawer_detectado_e_marcado_cortado(self):
        d = A.detect_addon(self._load("drawer_clipped.png"))
        self.assertTrue(d["detected"], "o drawer de add-on deve ser detectado")
        self.assertTrue(d["clipped"], "o botão está cortado pela janela estreita -> clipped")
        self.assertFalse(d["clickable"], "cortado -> NÃO clicável (não clica na beirada)")
        self.assertIsNotNone(d["confirm"])

    def test_mesa_normal_nao_dispara(self):
        d = A.detect_addon(self._load("mesa_sem_drawer.png"))
        self.assertFalse(d["detected"], "mesa sem drawer NÃO pode dar falso-positivo")
        self.assertFalse(d["clickable"])


if __name__ == "__main__":
    unittest.main()
