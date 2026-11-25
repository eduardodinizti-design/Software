"""DayTournamentSink: roteia mãos p/ <base>/ANO/MÊS/DIA/<torneio>.jsonl."""
import json
import os
import tempfile
import unittest

from hand_sink import DayTournamentSink, hand_path, sanitize_name


class SanitizeTests(unittest.TestCase):
    def test_nome_seguro(self):
        self.assertEqual(sanitize_name('EJNEFERTITI'), 'EJNEFERTITI')
        self.assertEqual(sanitize_name('BRL - FLOP HOTEL'), 'BRL_-_FLOP_HOTEL')
        self.assertEqual(sanitize_name(None), 'sem_torneio')
        self.assertNotIn('/', sanitize_name('a/b:c*d'))


class PathTests(unittest.TestCase):
    def test_pasta_por_dia_arquivo_por_torneio(self):
        rec = {'ts': '2026-11-05T13:00:00+00:00', 'tournament': {'name': 'GOLD'}}
        p = hand_path(r'C:\base', rec)
        parts = p.replace('/', '\\').split('\\')
        self.assertIn('2026', parts)
        self.assertIn('11', parts)
        self.assertTrue(p.endswith('GOLD.jsonl'))

    def test_sem_ts_usa_hoje_sem_quebrar(self):
        p = hand_path('base', {'tournament': {'name': 'X'}})
        self.assertTrue(p.endswith('X.jsonl'))


class SinkTests(unittest.TestCase):
    def test_grava_torneios_em_arquivos_separados(self):
        with tempfile.TemporaryDirectory() as base:
            sink = DayTournamentSink(base)
            sink({'ts': '2026-11-05T10:00:00+00:00', 'tournament': {'name': 'GOLD'}, 'hand_id': 'a'})
            sink({'ts': '2026-11-05T10:05:00+00:00', 'tournament': {'name': 'GOLD'}, 'hand_id': 'b'})
            sink({'ts': '2026-11-05T10:10:00+00:00', 'tournament': {'name': 'NEFERTITI'}, 'hand_id': 'c'})
            self.assertEqual(len(sink.written), 2)             # 2 arquivos (2 torneios)
            # GOLD tem 2 mãos no mesmo arquivo
            gold = [p for p in sink.written if p.endswith('GOLD.jsonl')][0]
            with open(gold, encoding='utf-8') as f:
                lines = [json.loads(ln) for ln in f if ln.strip()]
            self.assertEqual([h['hand_id'] for h in lines], ['a', 'b'])

    def test_integra_com_handrecorder_via_sink(self):
        from hand_recorder import HandRecorder
        with tempfile.TemporaryDirectory() as base:
            sink = DayTournamentSink(base)
            rec = HandRecorder(path=None, sink=sink)            # só roteia (sem arquivo único)
            h = rec.begin(hand_id='z1', tournament={'name': 'MINI'})
            rec.commit(h)
            self.assertTrue(any(p.endswith('MINI.jsonl') for p in sink.written))


if __name__ == '__main__':
    unittest.main()
