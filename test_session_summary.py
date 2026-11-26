"""TRAVA do agregador de sessão/dia (session_summary): schema -> KPIs em R$ (play money)."""
import json
import os
import tempfile
import unittest

import session_summary as S


def _row(**kw):
    base = dict(schema=1, event='tournament_end', room='Suprema', currency='R$',
                date='2026-11-25', session_id='2026-11-25#1', result='busted')
    base.update(kw)
    return base


class Aggregator(unittest.TestCase):

    def test_invested_reconstruido(self):
        r = _row(buyin=1000, rebuys=2, rebuy_cost=1000, addons=1, addon_cost=500)
        self.assertEqual(S.invested_of(r), 1000 + 2000 + 500)

    def test_invested_direto_tem_prioridade(self):
        r = _row(buyin=1000, invested=9999)
        self.assertEqual(S.invested_of(r), 9999)

    def test_profit_calculado_de_prize_bounty_invested(self):
        r = _row(buyin=1000, prize=5000, bounty=1500)
        self.assertEqual(S.profit_of(r), 5000 + 1500 - 1000)

    def test_profit_none_sem_dado_de_dinheiro(self):
        self.assertIsNone(S.profit_of(_row(rank=50, field=300)))

    def test_summarize_kpis_em_fichas(self):
        rows = [
            _row(buyin=1000, prize=0, rank=120, field=300, itm=False, reached_ft=False),
            _row(buyin=1000, prize=8000, bounty=2000, kos=3, rank=2, field=300, itm=True, reached_ft=True, result='itm'),
            _row(buyin=1000, prize=0, rank=80, field=200, itm=False, reached_ft=False),
        ]
        s = S.summarize(rows)
        self.assertEqual(s.n, 3)
        self.assertEqual(s.currency, 'R$')
        self.assertEqual(s.invested, 3000)
        self.assertEqual(s.prize, 8000)
        self.assertEqual(s.bounty, 2000)
        self.assertEqual(s.profit, (0-1000) + (8000+2000-1000) + (0-1000))  # 7000
        self.assertAlmostEqual(s.roi, 7000 / 3000)
        self.assertAlmostEqual(s.itm_pct, 100.0 * 1 / 3)
        self.assertAlmostEqual(s.ft_pct, 100.0 * 1 / 3)
        self.assertEqual(s.kos, 3)
        self.assertEqual(s.best_prize, 8000)
        self.assertEqual(s.n_with_money, 3)

    def test_roi_none_sem_investimento(self):
        s = S.summarize([_row(rank=10, field=100)])
        self.assertIsNone(s.roi)

    def test_summarize_today_filtra_dia(self):
        rows = [_row(date='2026-11-25', buyin=1000, prize=4000),
                _row(date='2026-11-24', buyin=1000, prize=0)]
        s = S.summarize_today(rows, today='2026-11-25')
        self.assertEqual(s.n, 1)
        self.assertEqual(s.profit, 3000)

    def test_group_by_day_cronologico(self):
        rows = [_row(date='2026-11-25'), _row(date='2026-11-24'), _row(date='2026-11-25')]
        g = S.group_by_day(rows)
        self.assertEqual(list(g.keys()), ['2026-11-24', '2026-11-25'])
        self.assertEqual(g['2026-11-25'].n, 2)

    def test_cumulative_profit(self):
        rows = [_row(ts='2026-11-25T10:00:00+00:00', buyin=1000, prize=0),      # -1000
                _row(ts='2026-11-25T11:00:00+00:00', buyin=1000, prize=5000)]   # +4000 -> cum 3000
        cum = S.cumulative_profit(rows)
        self.assertEqual([v for _, v in cum], [-1000, 3000])

    def test_day_key_deriva_do_ts_sem_date(self):
        self.assertEqual(S.day_key({'ts': '2026-11-20T23:59:00+00:00'}), '2026-11-20')

    def test_load_rows_tolerante(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 't.jsonl')
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write(json.dumps(_row(buyin=1000, prize=2000)) + '\n')
                fh.write('{linha corrompida\n')                       # ignorada
                fh.write(json.dumps(dict(event='other')) + '\n')      # não é tournament_end
                fh.write(json.dumps(_row(buyin=1000, prize=0)) + '\n')
            rows = S.load_rows(p)
            self.assertEqual(len(rows), 2)

    def test_load_rows_arquivo_ausente(self):
        self.assertEqual(S.load_rows(os.path.join('nao', 'existe.jsonl')), [])


if __name__ == '__main__':
    unittest.main()
