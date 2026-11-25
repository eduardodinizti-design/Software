"""Loader/validador da GRADE DO DIA: aceita e preserva `club` por torneio, faz a
ponte reg_opens->reg_opens_min, e é fail-safe (reporta entrada ruim, não inventa)."""
import json
import os
import tempfile
import unittest

from grade_do_dia import normalize_entry, normalize_grade, load_grade


class NormalizeEntryTests(unittest.TestCase):
    def test_minimo_valido(self):
        e, errs = normalize_entry({'id': 'MICRO LUDIKA', 'start': '20:00', 'buyin_bb': 10})
        self.assertEqual(errs, [])
        self.assertEqual(e['id'], 'MICRO LUDIKA')
        self.assertEqual(e['buyin_bb'], 10.0)
        self.assertNotIn('club', e)            # club é opcional

    def test_club_preservado_e_trim(self):
        e, errs = normalize_entry(
            {'id': 'AK NIGHT', 'start': '21:00', 'buyin_bb': 50, 'club': '  AK Ahakha club2 '})
        self.assertEqual(errs, [])
        self.assertEqual(e['club'], 'AK Ahakha club2')

    def test_reg_opens_vira_min(self):
        e, _ = normalize_entry({'id': 't', 'start': '20:00', 'buyin_bb': 1, 'reg_opens': '19:30'})
        self.assertEqual(e['reg_opens'], '19:30')
        self.assertEqual(e['reg_opens_min'], 19 * 60 + 30)   # o que o planner consome

    def test_id_vazio_e_start_ruim_bloqueiam(self):
        _, errs = normalize_entry({'id': '  ', 'start': '25:99', 'buyin_bb': 10})
        self.assertTrue(any('id' in m for m in errs))
        self.assertTrue(any('start' in m for m in errs))

    def test_buyin_invalido_nao_inventa_zero(self):
        for bad in (None, 'abc', -5, float('inf'), float('nan')):
            e, errs = normalize_entry({'id': 't', 'start': '20:00', 'buyin_bb': bad})
            self.assertIsNone(e)
            self.assertTrue(any('buyin_bb' in m for m in errs))

    def test_club_vazio_e_erro(self):
        _, errs = normalize_entry({'id': 't', 'start': '20:00', 'buyin_bb': 1, 'club': '   '})
        self.assertTrue(any('club' in m for m in errs))


class NormalizeGradeTests(unittest.TestCase):
    def test_lista_mista_bloqueia_so_a_ruim(self):
        raw = [
            {'id': 'KAREKAS MINI', 'start': '20:00', 'buyin_bb': 10, 'club': 'Karekas'},
            {'id': 'BAD', 'start': '99:99', 'buyin_bb': 5},
            {'id': 'AK DEEP', 'start': '21:00', 'buyin_bb': 50, 'club': 'AK Ahakha club2'},
        ]
        r = normalize_grade(raw)
        self.assertFalse(r['ok'])                       # houve erro...
        self.assertEqual([e['id'] for e in r['grade']], ['KAREKAS MINI', 'AK DEEP'])  # ...mas as boas passam
        self.assertEqual([e['club'] for e in r['grade']], ['Karekas', 'AK Ahakha club2'])
        self.assertEqual(r['errors'][0][0], 1)          # índice da ruim

    def test_id_duplicado_e_erro(self):
        raw = [{'id': 'X', 'start': '20:00', 'buyin_bb': 1},
               {'id': 'X', 'start': '21:00', 'buyin_bb': 1}]
        r = normalize_grade(raw)
        self.assertFalse(r['ok'])
        self.assertEqual(len(r['grade']), 1)

    def test_grade_nao_lista(self):
        self.assertFalse(normalize_grade({'id': 'x'})['ok'])


class LoadGradeTests(unittest.TestCase):
    def test_round_trip_com_clubes(self):
        raw = [
            {'id': 'KAREKAS MINI', 'reg_opens': '19:30', 'start': '20:00', 'buyin_bb': 10, 'club': 'Karekas'},
            {'id': 'AK DEEP', 'reg_opens': '20:30', 'start': '21:00', 'buyin_bb': 50, 'club': 'AK Ahakha club2'},
        ]
        fd, path = tempfile.mkstemp(suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(raw, f)
            r = load_grade(path)
        finally:
            os.remove(path)
        self.assertTrue(r['ok'])
        self.assertEqual([e['club'] for e in r['grade']], ['Karekas', 'AK Ahakha club2'])

    def test_arquivo_ausente_nao_explode(self):
        r = load_grade('nao_existe_123.json')
        self.assertFalse(r['ok'])
        self.assertIn('não encontrado', r['errors'][0][1][0])


class PlannerCarriesClubTests(unittest.TestCase):
    """A grade normalizada atravessa o grind_planner carregando club + reg_opens_min."""
    def test_club_e_janela_atravessam_due_to_register(self):
        from grind_planner import GrindPlanner
        grade = normalize_grade(
            [{'id': 'AK DEEP', 'start': '21:00', 'buyin_bb': 50,
              'reg_opens': '20:30', 'club': 'AK Ahakha club2'}])['grade']
        p = GrindPlanner(max_simultaneous=4, reg_lead_min=60)
        # 20:45 (1245): a janela [20:30, 21:00) do OPERADOR (reg_opens_min) está aberta,
        # e NÃO a default [20:00,21:00) — prova que a ponte reg_opens->reg_opens_min pega.
        due = p.due_to_register(20 * 60 + 45, grade)
        self.assertEqual([e['id'] for e in due], ['AK DEEP'])
        self.assertEqual(due[0]['club'], 'AK Ahakha club2')   # club chega ao runner
        # 20:15 (1215): ainda ANTES do reg_opens do operador -> não registra.
        self.assertEqual(p.due_to_register(20 * 60 + 15, grade), [])


if __name__ == '__main__':
    unittest.main()
