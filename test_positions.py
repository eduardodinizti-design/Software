"""TRAVA das posições por visão (offline): dealer (assento) + ativos -> posições RangeLab
ancoradas no BTN, ordem horária. Sem modelo/tela."""
import unittest

from vision_yolo.positions import (resolve_positions, clockwise_seats, nearest_seat,
                                   resolve_from_detections)
from vision_yolo.vision_state import Detection
from vision_yolo.classes import NAME_TO_ID

ATIVOS7 = ['hero', 'top', 'top_left', 'top_right', 'mid_right', 'low_left', 'low_right']


class Positions(unittest.TestCase):

    def test_ordem_horaria(self):
        order = clockwise_seats()
        self.assertEqual(order[0], 'top')                 # começa no topo
        self.assertEqual(len(order), 8)
        self.assertEqual(order.index('top_right') < order.index('low_right'), True)  # horário

    def test_dealer_vira_btn(self):
        pos = resolve_positions(ATIVOS7, 'low_right')
        self.assertEqual(pos['low_right'], 'BTN')
        self.assertEqual(pos['hero'], 'SB')               # clockwise-next do BTN
        self.assertEqual(pos['low_left'], 'BB')
        self.assertIn('hero', pos)
        self.assertEqual(set(pos.values()) <= {'UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'}, True)

    def test_heads_up_dealer_e_sb(self):
        pos = resolve_positions(['hero', 'top'], 'hero')
        self.assertEqual(pos['hero'], 'SB')               # HU: dealer = SB
        self.assertEqual(pos['top'], 'BB')

    def test_nearest_seat(self):
        self.assertEqual(nearest_seat(0.82, 0.70), 'low_right')
        self.assertEqual(nearest_seat(0.50, 0.14), 'top')

    def test_abstem_dealer_fora(self):
        self.assertEqual(resolve_positions(['hero', 'top'], 'low_left'), {})   # dealer não ativo

    def test_resolve_from_detections(self):
        # detecção do dealer_button perto de low_right -> posições
        dealer = Detection(NAME_TO_ID['dealer_button'], 0.9, (0.80, 0.68, 0.84, 0.72))
        pos = resolve_from_detections([dealer], ATIVOS7)
        self.assertEqual(pos.get('low_right'), 'BTN')


if __name__ == '__main__':
    unittest.main()
