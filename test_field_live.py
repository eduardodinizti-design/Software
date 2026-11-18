import json
import os
import tempfile
import unittest

from field_live import hud_from_seats, read_live_seats, load_exploit_db, MIN_HANDS

_DB = {
    '8709072': {'category': 'reg', 'hands': 4494, 'tags': ['cbet_light'],
                'stats': {'vpip': 22.1, 'pfr': 14.9, 'threebet': 6.0, 'af': 2.04,
                          'steal': 35.2, 'cbet': 40.9, 'foldcbet': 54.1, 'fold3bet': 52.1}},
    '111': {'category': 'fish', 'hands': 120, 'tags': ['station'],
            'stats': {'vpip': 55.0, 'pfr': 8.0, 'threebet': 1.0, 'af': 0.6,
                      'steal': 10.0, 'cbet': 20.0, 'foldcbet': 15.0, 'fold3bet': 20.0}},
    '222': {'category': 'reg', 'hands': 5, 'stats': {'vpip': 20.0}},   # amostra pequena
}


class TestHudFromSeats(unittest.TestCase):
    def test_known_villain_becomes_high_conf_entry(self):
        hud = hud_from_seats({'bot_left': '8709072'}, _DB)
        self.assertIn('bot_left', hud)
        e = hud['bot_left']
        self.assertEqual(e['confidence'], 'high')     # exigido pelo advisor
        self.assertFalse(e['_age'])                    # exigido pelo advisor
        self.assertEqual(e['stats']['vpip'], 22.1)
        self.assertEqual(e['_source'], 'field_db')

    def test_unknown_id_omitted(self):
        self.assertEqual(hud_from_seats({'s': '99999'}, _DB), {})

    def test_small_sample_omitted(self):
        self.assertEqual(hud_from_seats({'s': '222'}, _DB), {})  # 5 maos < MIN_HANDS

    def test_none_id_and_empty(self):
        self.assertEqual(hud_from_seats({'s': None}, _DB), {})
        self.assertEqual(hud_from_seats({}, _DB), {})
        self.assertEqual(hud_from_seats({'s': '111'}, {}), {})

    def test_multiple_seats(self):
        hud = hud_from_seats({'a': '8709072', 'b': '111', 'c': '222'}, _DB)
        self.assertEqual(set(hud), {'a', 'b'})         # c tem amostra pequena


class TestReadLiveSeats(unittest.TestCase):
    def _write(self, obj):
        fd, p = tempfile.mkstemp(suffix='.json'); os.close(fd)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(obj, f)
        return p

    def test_by_table_key(self):
        p = self._write({'mesaA': {'s1': '111'}, 'mesaB': {'s2': '222'}})
        try:
            self.assertEqual(read_live_seats(p, 'mesaA'), {'s1': '111'})
        finally:
            os.remove(p)

    def test_flat(self):
        p = self._write({'s1': '111', 's2': '222'})
        try:
            self.assertEqual(read_live_seats(p), {'s1': '111', 's2': '222'})
        finally:
            os.remove(p)

    def test_missing_file(self):
        self.assertEqual(read_live_seats('nao_existe_xyz.json'), {})


class TestLoadDb(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(load_exploit_db('nao_existe.json'), {})


if __name__ == '__main__':
    unittest.main()
