"""Lobby grade reader: field parsing and modality classification.

Pure parsers over synthetic OCR text (lab-safe). The badge detection and the
field OCR are validated live on a real Karekas lobby gabarito; these pin the
parsing and naming so a real read is interpreted consistently."""
import unittest

import grade_reader as gr


class ModalityTests(unittest.TestCase):
    def test_keywords_and_bounty(self):
        self.assertEqual(gr.classify_modality('KOMBAT MISTERY'), 'mko')
        self.assertEqual(gr.classify_modality('BOX MYSTERY MKO'), 'mko')
        self.assertEqual(gr.classify_modality('HYPER PKO 10K'), 'pko')
        self.assertEqual(gr.classify_modality('BOUNTY HUNTER'), 'pko')
        self.assertEqual(gr.classify_modality('MINI FREEZE'), 'freezeout')
        self.assertEqual(gr.classify_modality('SUPER DEEP'), 'deep')
        self.assertEqual(gr.classify_modality('SUPER ADD-ON'), 'addon')
        self.assertEqual(gr.classify_modality('CRAZY REBUY'), 'rebuy')

    def test_unknown_is_flagged_not_guessed(self):
        self.assertEqual(gr.classify_modality('MICRO LUDIKA'), 'unknown')
        self.assertEqual(gr.classify_modality(''), 'unknown')

    def test_mystery_beats_rebuy_keyword_order(self):
        # A mystery rebuy is still treated as the bounty format (mko) first.
        self.assertEqual(gr.classify_modality('MYSTERY REBUY'), 'mko')


class FieldParseTests(unittest.TestCase):
    def test_buyin(self):
        self.assertEqual(gr.parse_buyin('Buy-in: 10'), 10)
        self.assertEqual(gr.parse_buyin('Buyin:50'), 50)
        self.assertIsNone(gr.parse_buyin('Buy-in:'))

    def test_players(self):
        self.assertEqual(gr.parse_players('96/263'), (96, 263))
        self.assertEqual(gr.parse_players('& 58/75 @12min'), (58, 75))
        self.assertEqual(gr.parse_players('14'), (None, None))

    def test_level_minutes(self):
        self.assertEqual(gr.parse_level_minutes('96/263 10 min'), 10)
        self.assertIsNone(gr.parse_level_minutes('no time here'))

    def test_status_reg_open(self):
        s = gr.parse_status('Registro encerra em 56 min')
        self.assertEqual((s['state'], s['closes_in_min']), ('reg_open', 56))

    def test_status_not_started(self):
        s = gr.parse_status('Horario de inicio: 11/08 23:00')
        self.assertEqual(s['state'], 'not_started')
        self.assertEqual(s['starts_at'], '11/08 23:00')

    def test_status_unknown(self):
        s = gr.parse_status('{ something unreadable')
        self.assertEqual(s['state'], 'unknown')


if __name__ == '__main__':
    unittest.main()
