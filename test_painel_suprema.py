"""TRAVA da LIGAÇÃO painel<->session_summary (desempenho da Suprema, em Play money R$).

Testa a LÓGICA pura (sem GUI): formatação de R$/lucro/ROI/%, sinal verde/vermelho,
montagem das linhas da tabela, KPIs a partir de um Summary e troca de recorte Hoje×Tudo.
A parte Tkinter é testada só se houver display (senão skipTest — nunca falha por isso).
"""
import os
import unittest

import painel as P
import session_summary as _ss

SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'logs', 'metrics', 'torneios_suprema.SAMPLE.jsonl')


def _row(**kw):
    base = dict(schema=1, event='tournament_end', room='Suprema', currency='R$',
                date='2026-11-25', session_id='2026-11-25#1', result='busted')
    base.update(kw)
    return base


class Formatacao(unittest.TestCase):

    def test_fmt_rs_ptbr(self):
        self.assertEqual(P._fmt_rs(29900), 'R$ 29.900,00')
        self.assertEqual(P._fmt_rs(10), 'R$ 10,00')
        self.assertEqual(P._fmt_rs(1234.5), 'R$ 1.234,50')
        self.assertEqual(P._fmt_rs(0), 'R$ 0,00')

    def test_fmt_rs_none_e_invalido(self):
        self.assertEqual(P._fmt_rs(None), '--')
        self.assertEqual(P._fmt_rs('abc'), '--')

    def test_fmt_lucro_sinal_explicito(self):
        self.assertEqual(P._fmt_lucro(29900), '+R$ 29.900,00')
        self.assertEqual(P._fmt_lucro(-1000), '-R$ 1.000,00')
        self.assertEqual(P._fmt_lucro(0), '+R$ 0,00')
        self.assertEqual(P._fmt_lucro(None), '--')

    def test_fmt_roi(self):
        self.assertEqual(P._fmt_roi(3.05), '305%')
        self.assertEqual(P._fmt_roi(-0.5), '-50%')
        self.assertEqual(P._fmt_roi(None), '--')

    def test_fmt_pct(self):
        self.assertEqual(P._fmt_pct(33.3), '33%')
        self.assertEqual(P._fmt_pct(None), '--')

    def test_lucro_sinal(self):
        self.assertEqual(P._lucro_sinal(100), 'pos')
        self.assertEqual(P._lucro_sinal(0), 'pos')
        self.assertEqual(P._lucro_sinal(-1), 'neg')
        self.assertEqual(P._lucro_sinal(None), 'neutro')


class KpisELinhas(unittest.TestCase):

    def test_kpi_values_lucro_positivo_verde(self):
        rows = [_row(buyin=1000, prize=8000, bounty=2000, kos=3, rank=2, field=300,
                     itm=True, reached_ft=True, result='itm'),
                _row(buyin=1000, prize=0, rank=120, field=300)]
        s = _ss.summarize(rows)
        kv = P._kpi_values(s)
        d = {label: (value, sinal) for label, value, sinal in kv}
        self.assertEqual(len(kv), 9)
        self.assertEqual(d['Torneios'][0], '2')
        self.assertEqual(d['Investido (R$)'][0], 'R$ 2.000,00')
        self.assertEqual(d['Prêmios (R$)'][0], 'R$ 8.000,00')
        self.assertEqual(d['Bounty / KOs'][0], 'R$ 2.000,00 / 3')
        # lucro = (8000+2000-1000) + (0-1000) = 8000 -> verde
        self.assertEqual(d['Lucro (R$)'], ('+R$ 8.000,00', 'pos'))
        self.assertEqual(d['ROI'][1], 'pos')

    def test_kpi_values_lucro_negativo_vermelho_e_roi_none(self):
        # sem dado de dinheiro em lugar nenhum -> ROI None -> neutro
        s = _ss.summarize([_row(rank=50, field=300)])
        d = {label: (value, sinal) for label, value, sinal in P._kpi_values(s)}
        self.assertEqual(d['ROI'], ('--', 'neutro'))
        # agora um prejuízo real -> vermelho
        s2 = _ss.summarize([_row(buyin=1000, prize=0, rank=200, field=300)])
        d2 = {label: (value, sinal) for label, value, sinal in P._kpi_values(s2)}
        self.assertEqual(d2['Lucro (R$)'], ('-R$ 1.000,00', 'neg'))

    def test_row_to_cells_pko_vencido(self):
        r = _row(name='Suprema Bounty Hunter R$10', mode='pko', buyin=10.0, invested=10.0,
                 prize=72.0, bounty=50.0, kos=5, rank=2, field=320, itm=True, profit=112.0)
        cells = P._row_to_cells(r)
        self.assertEqual(cells, ('Suprema Bounty Hunter R$10', 'pko', 'R$ 10,00', 'R$ 72,00',
                                 'R$ 50,00', '5', '2/320', 'Sim', '+R$ 112,00'))

    def test_row_to_cells_sem_dados(self):
        r = _row(tournament_id='X', buyin=1000, prize=0, rank=88, field=210, itm=False)
        cells = P._row_to_cells(r)
        self.assertEqual(cells[0], 'X')          # cai no tournament_id
        self.assertEqual(cells[1], '--')         # modo ausente
        self.assertEqual(cells[3], 'R$ 0,00')    # prêmio R$ 0
        self.assertEqual(cells[4], '--')         # bounty None
        self.assertEqual(cells[5], '--')         # KOs None
        self.assertEqual(cells[6], '88/210')
        self.assertEqual(cells[7], 'Não')


class Recorte(unittest.TestCase):

    def test_filter_hoje_vs_tudo(self):
        rows = [_row(date='2026-11-25', buyin=1000, prize=4000),
                _row(date='2026-11-24', buyin=1000, prize=0),
                _row(date='2026-11-25', buyin=1000, prize=0)]
        hoje = P._filter_by_recorte(rows, P.RECORTE_HOJE, today='2026-11-25')
        tudo = P._filter_by_recorte(rows, P.RECORTE_TUDO)
        self.assertEqual(len(hoje), 2)
        self.assertEqual(len(tudo), 3)

    def test_filter_por_sessao(self):
        rows = [_row(session_id='A'), _row(session_id='B'), _row(session_id='A')]
        self.assertEqual(len(P._filter_by_recorte(rows, 'A')), 2)

    def test_recorte_options_tem_hoje_tudo_e_sessoes(self):
        rows = [_row(ts='2026-11-25T10:00:00+00:00', session_id='2026-11-25#1'),
                _row(ts='2026-11-24T10:00:00+00:00', session_id='2026-11-24#1')]
        opts = P._recorte_options(rows)
        keys = [k for _lbl, k in opts]
        self.assertEqual(keys[0], P.RECORTE_HOJE)
        self.assertEqual(keys[1], P.RECORTE_TUDO)
        self.assertIn('2026-11-25#1', keys)
        self.assertIn('2026-11-24#1', keys)

    def test_sample_carrega_e_resume(self):
        if not os.path.exists(SAMPLE):
            self.skipTest('sample ausente')
        rows = _ss.load_rows(SAMPLE)
        self.assertEqual(len(rows), 9)
        hoje = P._filter_by_recorte(rows, P.RECORTE_HOJE, today='2026-11-25')
        self.assertEqual(len(hoje), 5)   # 5 torneios no dia de hoje do sample
        s = _ss.summarize(hoje)
        self.assertEqual(s.currency, 'R$')
        self.assertEqual(s.n, 5)


class Gui(unittest.TestCase):
    """Fumaça da GUI: só roda se houver display; monta o painel e repopula a aba Suprema."""

    def _tk_or_skip(self):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            return tk, root
        except Exception as e:
            self.skipTest('sem display/tkinter: %s' % e)

    def test_monta_painel_e_aba_suprema(self):
        _tk, root = self._tk_or_skip()
        try:
            pan = P.Painel(root, select_tab='suprema')
            self.assertIn('suprema', pan._tab_frames)
            # recorte populado e render sem exceção
            self.assertTrue(pan.s_recorte['values'])
            pan._suprema_refresh()
            # a tabela é um Treeview válido (pode ter 0+ linhas conforme o dia)
            self.assertTrue(hasattr(pan, 's_tree'))
            _ = pan.s_tree.get_children()
        finally:
            try:
                root.destroy()
            except Exception:
                pass


if __name__ == '__main__':
    unittest.main()
