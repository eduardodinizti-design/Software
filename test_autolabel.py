"""TRAVA da auto-rotulagem (F1, offline): VALORES da mesa + LAYOUT de caixas -> labels YOLO
corretos (ids casam com classes.py, formato ultralytics). Prova o mecanismo sem Frida/tela."""
import os
import tempfile
import unittest

from vision_yolo.autolabel import to_yolo_labels, format_yolo, write_example
from vision_yolo.classes import NAME_TO_ID, ID_TO_NAME, card_name

LAYOUT = {
    'hero_card_slots': [(0.45, 0.85, 0.06, 0.09), (0.52, 0.85, 0.06, 0.09)],
    'board_slots': [(0.40, 0.45, 0.06, 0.09), (0.47, 0.45, 0.06, 0.09),
                    (0.54, 0.45, 0.06, 0.09), (0.61, 0.45, 0.06, 0.09), (0.68, 0.45, 0.06, 0.09)],
    'buttons': {'fold': (0.18, 0.95, 0.2, 0.06), 'call': (0.50, 0.95, 0.2, 0.06),
                'raise': (0.82, 0.95, 0.2, 0.06)},
}
VALUES = {'hero_cards': ['As', 'Ad'], 'board': ['9c', '6d', '2h'],
          'legal_actions': ['fold', 'call', 'raise']}


class AutoLabel(unittest.TestCase):

    def test_ids_e_caixas(self):
        labels = to_yolo_labels(VALUES, LAYOUT)
        # 2 hero + 3 board + 3 botoes = 8 objetos
        self.assertEqual(len(labels), 8)
        # 1a label = herói As no slot 1
        cid, cx, cy, w, h = labels[0]
        self.assertEqual(ID_TO_NAME[cid], 'As')
        self.assertEqual((cx, cy, w, h), (0.45, 0.85, 0.06, 0.09))
        # os 3 primeiros pares de carta decodificam de volta
        self.assertEqual([card_name(l[0]) for l in labels[:5]], ['As', 'Ad', '9c', '6d', '2h'])

    def test_botao_mapeia_classe(self):
        labels = to_yolo_labels(VALUES, LAYOUT)
        btns = [ID_TO_NAME[l[0]] for l in labels if ID_TO_NAME[l[0]].startswith('btn_')]
        self.assertEqual(set(btns), {'btn_fold', 'btn_call', 'btn_raise'})

    def test_so_emite_com_valor_E_slot(self):
        # board com 1 carta -> só 1 slot usado (não inventa os outros 4)
        v = {'hero_cards': ['As', 'Ad'], 'board': ['9c'], 'legal_actions': []}
        labels = to_yolo_labels(v, LAYOUT)
        self.assertEqual(len(labels), 3)              # 2 hero + 1 board
        # ação sem caixa no layout -> não emite
        v2 = {'hero_cards': [], 'board': [], 'legal_actions': ['all_in']}   # all_in não está em buttons
        self.assertEqual(to_yolo_labels(v2, LAYOUT), [])

    def test_format_ultralytics(self):
        txt = format_yolo([(5, 0.5, 0.5, 0.1, 0.2)])
        self.assertEqual(txt, '5 0.500000 0.500000 0.100000 0.200000')

    def test_write_example_grava_par(self):
        with tempfile.TemporaryDirectory() as d:
            img = os.path.join(d, 'src.png')
            open(img, 'wb').write(b'\x89PNG fake')
            ip, lp = write_example('f0001', img, VALUES, LAYOUT,
                                   os.path.join(d, 'images'), os.path.join(d, 'labels'))
            self.assertTrue(os.path.exists(ip) and os.path.exists(lp))
            self.assertEqual(len(open(lp).read().splitlines()), 8)


if __name__ == '__main__':
    unittest.main()
