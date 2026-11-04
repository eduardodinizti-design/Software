"""Text fixtures are manual transcriptions, not OCR output from user images."""
import json
from pathlib import Path
import unittest

import numpy as np

from visualpilot.lab.pppoker_lobby_reference import (
    annotated_crops, compare_details, compare_modal, lobby_card, price, start_time,
    recognize_reference_field)


def fields(**texts):
    return {key: [([], value, .99)] for key, value in texts.items()}


def corujao():
    return fields(name='CORUJAO HYPER PKO10K', buyin='Buy-in: 50',
                  start='Horário de início: 10/31 22:00')


def details():
    return fields(name='CORUJAO HYPER PKO10K', buyin='Buy-in: 50 (28.34+14.16+7.5)',
                  start='Horário de início: 10/31 22:00', stack='Fichas iniciais: 20,000', register='Registrar')


class ReferenceReadingTests(unittest.TestCase):
    def test_paired_ocr_conflicting_confident_readings_stay_pending(self):
        class Reader:
            def field(self, image):return 'Buy-in: 50', .99
            def detect(self, image):return [([], 'Buy-in: 500', .99)]
        rows, evidence=recognize_reference_field(Reader(),None,'buyin')
        self.assertEqual(rows,[])
        self.assertEqual(evidence['reason'],'conflicting_confident_readings')

    def test_paired_ocr_does_not_join_price_digits(self):
        class Reader:
            def field(self, image):return 'Buy-in: 5 0', .99
            def detect(self, image):return [([], 'Buy-in: 50', .99)]
        self.assertEqual(recognize_reference_field(Reader(),None,'buyin')[0],[])

    def test_name_whitespace_is_not_letter_digit_substitution(self):
        selected=lobby_card(corujao())
        data=details();data['name']=fields(name='CORUJAOHYPERPKO10K')['name']
        self.assertTrue(compare_details(selected,data)['matches'])
        data['name']=fields(name='CORUJA0HYPERPKO10K')['name']
        self.assertFalse(compare_details(selected,data)['matches'])

    def test_paired_ocr_does_not_repair_high_confidence_name(self):
        class Reader:
            def field(self, image):return 'CORUJA0 HYPER PKO10K', .99
            def detect(self, image):return [([], 'CORUJAO HYPER PKO10K', .98)]
        self.assertEqual(recognize_reference_field(Reader(),None,'name')[0],[])

    def test_paired_ocr_accepts_legible_detection_and_keeps_alternative(self):
        class Reader:
            def field(self, image):return 'Confirma?', .90
            def detect(self, image):return [([], 'Confirmar', .99)]
        rows,evidence=recognize_reference_field(Reader(),None,'confirm')
        self.assertEqual(rows[0][1],'Confirmar')
        self.assertEqual(evidence['direct'][0][1],'Confirma?')

    def test_total_and_all_components_agree(self):
        self.assertEqual(price('Buy-in: 50 (28.34+14.16+7.5)'), '50.00')
        self.assertEqual(price('Buy-in: 28,34+14,16+7,50'), '50.00')
        for text in ('Buy-in: 50 (28.34+14.16+7.51)', 'Buy-in: 50+', 'Buy-in: 5O',
                     'Premiação: 10,000', 'Blinds: 1/2', 'Buy-in: 1.000'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                price(text)

    def test_lobby_only_allows_inspection_unknown_currency_and_status(self):
        result = lobby_card(corujao())
        self.assertTrue(result['can_inspect_details'])
        self.assertEqual(result['registration'], 'unknown')
        self.assertEqual(result['currency'], 'unknown')
        self.assertFalse(result['can_register'])

    def test_cost_closed_and_partial_filters(self):
        for changes in ({'buyin': 'Buy-in: 200'}, {'buyin': 'Buy-in: 50.01'},
                        {'status': 'Registros encerrados'}):
            data = corujao(); data.update(fields(**changes))
            self.assertFalse(lobby_card(data)['can_inspect_details'])
        self.assertFalse(lobby_card(corujao(), complete=False)['can_inspect_details'])
        with self.assertRaises(ValueError):
            lobby_card(corujao(), max_buyin='100')

    def test_prize_and_blinds_never_replace_missing_buyin(self):
        for data in (fields(name='TORNEIO DIAMANTE', prize='Premiação: 10,000'),
                     fields(name='OMAHA - 6', blinds='Blinds: 1/2')):
            result = lobby_card(data)
            self.assertIsNone(result['buyin'])
            self.assertFalse(result['can_inspect_details'])

    def test_low_confidence_duplicate_or_missing_fields_block(self):
        for rows in ([], [([], 'Buy-in: 50', .94)], [([], 'Buy-in: 50', float('nan'))],
                     [([], 'Buy-in: 50', .99), ([], 'Buy-in: 50', .99)]):
            data = corujao(); data['buyin'] = rows
            self.assertFalse(lobby_card(data)['can_inspect_details'])

    def test_details_compare_name_time_cost_and_stack_separately(self):
        selected = lobby_card(corujao())
        result = compare_details(selected, details())
        self.assertTrue(result['matches'])
        self.assertEqual(result['initial_stack'], 20000)
        self.assertEqual(result['buyin'], '50.00')
        self.assertFalse(result['can_register'])
        for key, value in [('name', 'OUTRO'), ('start', 'Horário de início: 10/31 23:00'),
                           ('buyin', 'Buy-in: 60 (40+10+10)')]:
            data = details(); data.update(fields(**{key: value}))
            self.assertFalse(compare_details(selected, data)['matches'])

    def test_modal_values_match_but_do_not_prove_navigation_or_registration(self):
        detail = compare_details(lobby_card(corujao()), details())
        data = fields(buyin='Buy-in: 28.34+14.16+7.5', start='Horário de início: 10/31 22:00', confirm='Confirmar')
        result = compare_modal(detail, data)
        self.assertTrue(result['matches'])
        self.assertFalse(result['can_register'])
        self.assertFalse(result['adjustable_amount'])
        data['buyin'] = fields(buyin='Buy-in: 50+7.5')['buyin']
        self.assertFalse(compare_modal(detail, data)['matches'])

    def test_date_does_not_invent_year_and_rejects_invalid_dates(self):
        self.assertEqual(start_time('Horário de início: 10/31 22:00'), '10/31 22:00')
        for value in ('02/30 22:00', '13/01 22:00', '10/31 24:00'):
            with self.assertRaises(ValueError):
                start_time('Horário de início: '+value)

    def test_manual_regions_fit_reference_and_reject_resize(self):
        profile = json.loads((Path(__file__).resolve().parents[1]/'docs/lab-lobby-real/reference.json').read_text())
        for view in profile['views'].values():
            image = np.zeros((view['size'][1], view['size'][0], 3), dtype=np.uint8)
            crops = annotated_crops(image, view)
            self.assertEqual(len(crops), len(view['items']))
            with self.assertRaises(ValueError):
                annotated_crops(image[:-1], view)
        lobby = profile['views']['lobby']
        self.assertEqual(annotated_crops(np.zeros((1115,623,3), dtype=np.uint8), lobby)[2]['image_point'], [315.0, 773.0])


if __name__ == '__main__':
    unittest.main()
