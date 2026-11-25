"""Registro de desempenho em torneios (métricas futuras)."""
import json
import os
import tempfile
import unittest

from tournament_metrics import parse_ranking, record_tournament_end


class ParseRankingTests(unittest.TestCase):
    def test_parses_place_and_field(self):
        self.assertEqual(parse_ranking('65/272'), (65, 272))

    def test_tolerates_spaces(self):
        self.assertEqual(parse_ranking('65 / 272'), (65, 272))

    def test_none_when_illegible(self):
        self.assertEqual(parse_ranking(None), (None, None))
        self.assertEqual(parse_ranking('???'), (None, None))


class RecordTests(unittest.TestCase):
    def _path(self):
        d = tempfile.mkdtemp()
        return os.path.join(d, 'sub', 'torneios.jsonl')      # testa criação do diretório

    def test_appends_json_line_with_parsed_fields(self):
        p = self._path()
        row = record_tournament_end(ranking='65/272', tournament='Karekas Yellow',
                                    closed=True, table_key='29x3', path=p,
                                    now=lambda: '2026-11-13T00:00:00+00:00')
        self.assertEqual((row['placed'], row['field']), (65, 272))
        self.assertEqual(row['result'], 'busted')
        self.assertTrue(row['closed'])
        with open(p, encoding='utf-8') as fh:
            lines = fh.read().strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])['tournament'], 'Karekas Yellow')

    def test_itm_flag(self):
        # 65/272 -> fora do dinheiro (65 > 272/5); 40/272 -> dentro.
        out = record_tournament_end(ranking='40/272', path=self._path(),
                                    now=lambda: 't')
        self.assertTrue(out['itm'])
        out2 = record_tournament_end(ranking='65/272', path=self._path(),
                                     now=lambda: 't')
        self.assertFalse(out2['itm'])

    def test_appends_not_overwrites(self):
        p = self._path()
        record_tournament_end(ranking='1/10', path=p, now=lambda: 't1')
        record_tournament_end(ranking='2/10', path=p, now=lambda: 't2')
        with open(p, encoding='utf-8') as fh:
            self.assertEqual(len(fh.read().strip().splitlines()), 2)


if __name__ == '__main__':
    unittest.main()
