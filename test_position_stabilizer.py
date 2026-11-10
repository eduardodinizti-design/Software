"""Estabilizador de posições: ignora blips de 1 frame (ocupação e dealer) e só
troca de epoch quando o botão do dealer persiste (mão nova)."""
import unittest

from position_stabilizer import PositionStabilizer
from table_reading.dealer_button import derive_positions
from table_reading.seat_layout import CLOCKWISE

FULL = list(CLOCKWISE)                      # 9-handed cheio
DEALER = 'hero'


def raw(dealer, occ):
    return derive_positions(dealer, occ)


class PositionStabilizerTest(unittest.TestCase):
    def feed(self, stab, n, dealer, occ, key='t'):
        out = None
        for _ in range(n):
            out = stab.update(table_key=key, dealer_seat=dealer, occupied_seats=occ)
        return out

    def test_steady_state_matches_raw(self):
        stab = PositionStabilizer()
        d, pos = self.feed(stab, 4, DEALER, FULL)
        self.assertEqual(d, DEALER)
        self.assertEqual(pos, raw(DEALER, FULL))

    def test_single_frame_occupancy_blip_is_ignored(self):
        stab = PositionStabilizer()
        self.feed(stab, 4, DEALER, FULL)
        blip = [s for s in FULL if s != 'top_left']          # cai 1 assento (não-dealer)
        self.assertNotEqual(raw(DEALER, blip), raw(DEALER, FULL))   # o cru MUDARIA
        d, pos = stab.update(table_key='t', dealer_seat=DEALER, occupied_seats=blip)
        self.assertEqual(pos, raw(DEALER, FULL))             # estabilizado = maioria
        self.assertNotIn(pos, (raw(DEALER, blip),))

    def test_single_frame_dealer_blip_is_ignored(self):
        stab = PositionStabilizer()
        self.feed(stab, 4, DEALER, FULL)
        d, pos = stab.update(table_key='t', dealer_seat='top_right', occupied_seats=FULL)
        self.assertEqual(d, DEALER)                          # debounce segura 1 frame
        self.assertEqual(pos, raw(DEALER, FULL))

    def test_persistent_dealer_move_starts_new_epoch(self):
        stab = PositionStabilizer(debounce=2)
        self.feed(stab, 4, DEALER, FULL)
        # novo dealer persiste 2 frames -> vira epoch novo (mão nova)
        stab.update(table_key='t', dealer_seat='bot_left', occupied_seats=FULL)
        d, pos = stab.update(table_key='t', dealer_seat='bot_left', occupied_seats=FULL)
        self.assertEqual(d, 'bot_left')
        self.assertEqual(pos, raw('bot_left', FULL))

    def test_no_dealer_yet_returns_empty(self):
        stab = PositionStabilizer()
        d, pos = stab.update(table_key='t', dealer_seat=None, occupied_seats=FULL)
        self.assertIsNone(d)
        self.assertEqual(pos, {})

    def test_recovers_locked_dealer_when_badge_missing(self):
        stab = PositionStabilizer()
        self.feed(stab, 3, DEALER, FULL)
        d, pos = stab.update(table_key='t', dealer_seat=None, occupied_seats=FULL)
        self.assertEqual(d, DEALER)                          # mantém o travado
        self.assertEqual(pos, raw(DEALER, FULL))

    def test_tables_are_independent(self):
        stab = PositionStabilizer()
        self.feed(stab, 3, 'hero', FULL, key='A')
        self.feed(stab, 3, 'bot_left', FULL, key='B')
        _, pa = stab.update(table_key='A', dealer_seat='hero', occupied_seats=FULL)
        _, pb = stab.update(table_key='B', dealer_seat='bot_left', occupied_seats=FULL)
        self.assertEqual(pa, raw('hero', FULL))
        self.assertEqual(pb, raw('bot_left', FULL))


if __name__ == '__main__':
    unittest.main()
