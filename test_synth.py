"""TRAVA do gerador sintético (offline): renderiza carta, compõe cena, rotula. Prova o
pipeline de dataset SEM Frida/tela (fundo sintético)."""
import os
import tempfile
import unittest

from PIL import Image

from vision_yolo.synth import render_card, make_scene, generate
from vision_yolo.classes import ID_TO_NAME, card_name


class Synth(unittest.TestCase):

    def test_render_card(self):
        img = render_card('As', 100, 140)
        self.assertEqual(img.size, (100, 140))
        self.assertEqual(img.mode, 'RGBA')

    def test_make_scene_labels(self):
        bg = Image.new('RGB', (600, 900), (30, 90, 60))        # feltro fake
        img, labels = make_scene(bg, hero=('As', 'Kd'), board=('9c', '6d', '2h'))
        self.assertEqual(img.size, (600, 900))
        self.assertEqual(len(labels), 5)                       # 2 hero + 3 board
        # os ids decodificam de volta p/ as cartas certas (bijeção)
        self.assertEqual([card_name(l[0]) for l in labels], ['As', 'Kd', '9c', '6d', '2h'])
        # caixas em fração válida
        for (_c, cx, cy, w, h) in labels:
            for v in (cx, cy, w, h):
                self.assertTrue(0.0 <= v <= 1.0)

    def test_generate_escreve_par(self):
        with tempfile.TemporaryDirectory() as d:
            bgp = os.path.join(d, 'bg.png')
            Image.new('RGB', (400, 600), (30, 90, 60)).save(bgp)
            n = generate([bgp], 3, os.path.join(d, 'images'), os.path.join(d, 'labels'), seed=1)
            self.assertEqual(n, 3)
            imgs = os.listdir(os.path.join(d, 'images'))
            lbls = os.listdir(os.path.join(d, 'labels'))
            self.assertEqual(len(imgs), 3)
            self.assertEqual(len(lbls), 3)


if __name__ == '__main__':
    unittest.main()
