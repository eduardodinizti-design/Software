"""Sync range-coach-pro -> pack. Foco no núcleo PURO (diff por sha256 + lock);
o sync completo roda contra uma pasta HRC sintética (sem rede/git)."""
import json
import tempfile
import unittest
from pathlib import Path

import sync_ranges as sr
from test_hrc_ingest import _synthetic_hrc


class DiffTests(unittest.TestCase):
    def test_added_changed_removed_unchanged(self):
        lock = {'a.json': 'h1', 'b.json': 'h2', 'c.json': 'h3'}
        cur = {'a.json': 'h1', 'b.json': 'X', 'd.json': 'h4'}   # a igual, b mudou, c saiu, d novo
        d = sr.diff_sources(cur, lock)
        self.assertEqual(d['unchanged'], ['a.json'])
        self.assertEqual(d['changed'], ['b.json'])
        self.assertEqual(d['removed'], ['c.json'])
        self.assertEqual(d['added'], ['d.json'])

    def test_empty_lock_is_all_added(self):
        d = sr.diff_sources({'x.json': 'h'}, {})
        self.assertEqual(d['added'], ['x.json'])
        self.assertFalse(d['changed'] or d['removed'])


class LockRoundTripTests(unittest.TestCase):
    def test_write_then_load(self):
        tmp = Path(tempfile.mkdtemp()) / 'lock.json'
        sr.write_lock(tmp, {'a.json': 'h1'}, source={'dir': 'x'})
        self.assertEqual(sr.load_lock(tmp), {'a.json': 'h1'})

    def test_load_missing_is_empty(self):
        self.assertEqual(sr.load_lock(Path(tempfile.mkdtemp()) / 'none.json'), {})


class SyncE2ETests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.hrc = self.root / 'public' / 'solver' / 'hrc'
        self.hrc.mkdir(parents=True)
        for nm in ('hrc_chip_25', 'hrc_ft_iguais_icm_30'):
            (self.hrc / (nm + '.json')).write_text(json.dumps(_synthetic_hrc(name=nm)), encoding='utf-8')
        self.out = self.root / 'pack.json'
        self.lock = self.root / 'lock.json'

    def test_first_sync_all_added_and_builds_pack(self):
        rep = sr.sync(self.root, self.out, self.lock)       # git_pull=False -> sem rede
        self.assertEqual(len(rep['diff']['added']), 2)
        self.assertEqual(rep['diff']['changed'], [])
        self.assertTrue(self.out.exists())
        self.assertGreater(rep['nodes'], 0)
        self.assertEqual(rep['coverage']['by_mode'].get('icm', 0) >= 0, True)

    def test_second_sync_detects_change_only(self):
        sr.sync(self.root, self.out, self.lock)             # 1º: popula o lock
        # altera 1 arquivo
        (self.hrc / 'hrc_chip_25.json').write_text(
            json.dumps(_synthetic_hrc(name='hrc_chip_25', unit='pct')), encoding='utf-8')
        rep = sr.sync(self.root, self.out, self.lock)
        self.assertEqual(rep['diff']['changed'], ['hrc_chip_25.json'])
        self.assertEqual(rep['diff']['added'], [])
        self.assertIn('hrc_ft_iguais_icm_30.json', rep['diff']['unchanged'])

    def test_no_files_raises(self):
        empty = Path(tempfile.mkdtemp())
        with self.assertRaises(FileNotFoundError):
            sr.sync(empty, empty / 'p.json', empty / 'l.json')


if __name__ == '__main__':
    unittest.main()
