"""Trava a leitura automática do bounty (PKO). O Henrique coleta o dado sozinho; conversão
fichas->BB, precedência (calibrado>vilão>hero/médio) e guarda de frescor."""
import json
import os
import tempfile
import time
import unittest

import bounty_reader as br


def _write(d):
    fd, p = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(d, fh)
    return p


class BountyReader(unittest.TestCase):
    def tearDown(self):
        for p in getattr(self, '_paths', []):
            try:
                os.remove(p)
            except OSError:
                pass

    def _p(self, d):
        self._paths = getattr(self, '_paths', [])
        p = _write(d)
        self._paths.append(p)
        return p

    def test_bounty_bb_calibrado_tem_precedencia(self):
        p = self._p(dict(ts=time.time(), bounty_bb=5.0, bb_chips=2000,
                         players={'42': 999999}))
        self.assertEqual(br.read_bounty_bb(p, villain_uid=42), 5.0)

    def test_converte_fichas_do_vilao_para_bb(self):
        p = self._p(dict(ts=time.time(), bb_chips=2000, players={'42': 10000, '7': 4000}))
        self.assertEqual(br.read_bounty_bb(p, villain_uid=42), 5.0)   # 10000/2000
        self.assertEqual(br.read_bounty_bb(p, villain_uid=7), 2.0)    # 4000/2000

    def test_fallback_hero_quando_sem_vilao(self):
        p = self._p(dict(ts=time.time(), bb_chips=1000, hero_bounty_chips=3000))
        self.assertEqual(br.read_bounty_bb(p), 3.0)

    def test_fallback_medio_dos_players(self):
        p = self._p(dict(ts=time.time(), bb_chips=1000, players={'1': 2000, '2': 4000}))
        self.assertEqual(br.read_bounty_bb(p, villain_uid=999), 3.0)  # (2000+4000)/2/1000

    def test_stale_devolve_none(self):
        p = self._p(dict(ts=time.time() - 120, bb_chips=1000, players={'1': 2000}))
        self.assertIsNone(br.read_bounty_bb(p, villain_uid=1))

    def test_sem_bb_chips_nao_converte(self):
        p = self._p(dict(ts=time.time(), players={'1': 2000}))
        self.assertIsNone(br.read_bounty_bb(p, villain_uid=1))

    def test_arquivo_ausente_none(self):
        self.assertIsNone(br.read_bounty_bb('/nao/existe/mtt_bounty.json'))

    def test_status_resume(self):
        p = self._p(dict(ts=time.time(), bb_chips=2000, players={'1': 2000},
                         calibrated=False, candidates={'myBounty': 2000}))
        s = br.status(p)
        self.assertTrue(s['available'] and s['fresh'])
        self.assertFalse(s['calibrated'])
        self.assertIn('myBounty', s['candidates'])


if __name__ == '__main__':
    unittest.main()
