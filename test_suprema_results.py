"""TRAVA do pipeline de resultados da Suprema -> jsonl (session_summary schema v1)."""
import json
import os
import tempfile
import unittest
from datetime import datetime

import suprema_results as R
import session_summary as S


class SessionId(unittest.TestCase):
    def test_dia_novo_comeca_em_1_e_reabrir_incrementa(self):
        with tempfile.TemporaryDirectory() as d:
            sp = os.path.join(d, 's.json')
            now = datetime(2026, 11, 25, 13, 0, 0)
            self.assertEqual(R.new_session_id(now=now, state_path=sp), '2026-11-25#1')
            self.assertEqual(R.new_session_id(now=now, state_path=sp), '2026-11-25#2')
            self.assertEqual(R.new_session_id(now=datetime(2026, 11, 26, 9, 0), state_path=sp), '2026-11-26#1')


class BuyinFromGrade(unittest.TestCase):
    GRADE = [{'name': 'Suprema Bounty Hunter $0', 'buyin_bb': 2500},
             {'name': 'Daily Turbo', 'buyin_bb': 1000, 'id': '777'}]

    def test_casa_por_nome_substring(self):
        self.assertEqual(R.buyin_from_grade(name='SUPREMA bounty hunter', grade=self.GRADE), 2500)

    def test_casa_por_id(self):
        self.assertEqual(R.buyin_from_grade(name='qualquer', tournament_id='777', grade=self.GRADE), 1000)

    def test_nao_acha_retorna_none(self):
        self.assertIsNone(R.buyin_from_grade(name='Inexistente', grade=self.GRADE))


class MttFields(unittest.TestCase):
    def test_extrai_pko_e_campos(self):
        state = {'mtt': {'players_total': 320, 'players_left': 140, 'places_paid': 45,
                         'rebuys': 0, 'addons': 0, 'bounty_base': 100.0}}
        mf = R.mtt_fields(state)
        self.assertEqual(mf['field'], 320)
        self.assertEqual(mf['places_paid'], 45)
        self.assertEqual(mf['players_left'], 140)
        self.assertEqual(mf['mode'], 'pko')

    def test_regular_sem_bounty(self):
        self.assertEqual(R.mtt_fields({'mtt': {'type': 'regular', 'players_total': 100}})['mode'], 'regular')

    def test_estado_vazio_nao_quebra(self):
        self.assertIsNone(R.mtt_fields({})['field'])


class BuildRow(unittest.TestCase):
    def test_deriva_invested_profit_itm(self):
        row = R.build_row(session_id='2026-11-25#1', tournament_id=20261127,
                          name='PKO', mode='pko', buyin=2500, prize=18000, bounty=12500,
                          kos=5, rank=2, field=320, places_paid=45, reached_ft=True,
                          now=lambda: '2026-11-25T15:10:00+00:00')
        self.assertEqual(row['date'], '2026-11-25')          # derivado do session_id
        self.assertEqual(row['invested'], 2500)
        self.assertEqual(row['profit'], 18000 + 12500 - 2500)
        self.assertTrue(row['itm'])                          # rank 2 <= places_paid 45
        self.assertEqual(row['currency'], 'R$')

    def test_itm_por_places_paid(self):
        row = R.build_row(session_id='2026-11-25#1', tournament_id=1, rank=50, field=300, places_paid=40)
        self.assertFalse(row['itm'])                         # 50 > 40

    def test_profit_none_sem_dinheiro(self):
        row = R.build_row(session_id='2026-11-25#1', tournament_id=1, rank=120, field=300)
        self.assertIsNone(row['profit'])
        self.assertIsNone(row['invested'])

    def test_linha_passa_pelo_agregador(self):
        # ponta-a-ponta: build_row -> record -> session_summary lê e resume
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 't.jsonl')
            R.record(p, **R.build_row(session_id='2026-11-25#1', tournament_id=1, buyin=1000,
                                      prize=4000, rank=3, field=100, places_paid=15))
            s = S.summarize_today(S.load_rows(p), today='2026-11-25')
            self.assertEqual(s.n, 1)
            self.assertEqual(s.profit, 3000)
            self.assertTrue(s.itm_pct and s.itm_pct > 0)


class BustRecorder(unittest.TestCase):
    def test_grava_uma_vez_por_torneio_do_estado_vivo(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 't.jsonl')
            state = {'mtt': {'players_total': 320, 'players_left': 138, 'places_paid': 45,
                             'bounty_base': 100.0}}
            rec = set()
            on_bust = R.make_bust_recorder(session_id='2026-11-25#1', tournament_id='20261125',
                                           name='Suprema PKO', buyin=2500, path=p,
                                           get_state=lambda: state, recorded=rec)
            row1 = on_bust(column=0)
            row2 = on_bust(column=0)          # repetição -> dedup, não grava de novo
            self.assertIsNotNone(row1)
            self.assertIsNone(row2)
            rows = S.load_rows(p)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['field'], 320)
            self.assertEqual(rows[0]['mode'], 'pko')
            self.assertEqual(rows[0]['rank'], 138)           # aproximação players_left
            self.assertEqual(rows[0]['buyin'], 2500)

    def test_nunca_lanca_sem_estado(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 't.jsonl')
            on_bust = R.make_bust_recorder(session_id='2026-11-25#1', tournament_id='x',
                                           name='T', path=p, get_state=lambda: None)
            row = on_bust(column=1)           # estado None -> grava best-effort, não quebra
            self.assertIsNotNone(row)
            self.assertEqual(len(S.load_rows(p)), 1)


if __name__ == '__main__':
    unittest.main()
