"""Tournament phase: parsing the on-table info and mapping to an ICM stage."""
import unittest
from unittest.mock import patch
import numpy as np

from table_reading import tournament
from table_reading.tournament import tournament_stage, tournament_context, is_pko


class StageTests(unittest.TestCase):
    def test_stages_from_remaining_and_paid(self):
        self.assertEqual(tournament_stage(8, 20), 'ft')          # final table
        self.assertEqual(tournament_stage(22, 20), 'bubble')     # just above the money
        self.assertEqual(tournament_stage(30, 20), 'pre_itm')    # approaching
        self.assertEqual(tournament_stage(55, 20), 'far')        # deep, chip EV
        self.assertIsNone(tournament_stage(15, 20))              # in the money, pre-FT: no pack stage
        self.assertIsNone(tournament_stage(None, 20))

    def test_context_maps_mode(self):
        self.assertEqual(tournament_context(dict(players_left=22, paid=20)), ('icm', 'bubble'))
        self.assertEqual(tournament_context(dict(players_left=55, paid=20)), ('chip_ev', 'mid'))
        self.assertEqual(tournament_context(dict(players_left=None, paid=None)), ('chip_ev', 'mid'))

    def test_pko_detection_and_context(self):
        self.assertFalse(is_pko('MINI FREEZE'))
        self.assertTrue(is_pko('SUPER KO'))
        self.assertTrue(is_pko('OMAHA 5 PKO'))
        self.assertEqual(tournament_context(dict(players_left=55, paid=20, is_pko=True)), ('pko', 'mid'))
        self.assertEqual(tournament_context(dict(players_left=22, paid=20, is_pko=True)), ('pko_icm', 'bubble'))


class ReadTests(unittest.TestCase):
    def _read(self, text):
        with patch('table_reading.tournament.image_to_string', return_value=text):
            return tournament.read_tournament(np.zeros((1334, 750, 3), np.uint8))

    def test_reads_paid_and_remaining(self):
        r = self._read('MINI FREEZE Blinds: 600/1,200(200) Lugares pagos: 20 Minha posigao: 40/55')
        self.assertEqual((r['paid'], r['players_left'], r['hero_rank']), (20, 55, 40))
        self.assertEqual(r['confidence'], 'high')

    def test_unread_abstains(self):
        r = self._read('MINI FREEZE Blinds: 600/1,200')
        self.assertIsNone(r['players_left'])
        self.assertEqual(r['confidence'], 'abstain')


if __name__ == '__main__':
    unittest.main()
