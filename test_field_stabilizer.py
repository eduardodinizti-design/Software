"""Memória temporal de campos: preenche buracos de leitura de pot/to_call/stack
DENTRO da mão (fill-only, limitado, marcado held), e NUNCA cruza fronteira de
mão nem sobrescreve leitura presente."""
import unittest

from field_stabilizer import FieldStabilizer


def _state(pot=None, to_call=None, seats=None):
    return dict(
        pot=dict(pot_bb=pot, confidence=('high' if pot is not None else 'abstain'), source='ocr'),
        to_call=dict(to_call_bb=to_call, confidence=('high' if to_call is not None else 'abstain'), source='ocr'),
        seats=seats or {},
    )


def _seat(stack=None, occupied=True):
    return dict(occupied=occupied, stack_bb=stack,
                confidence=('high' if stack is not None else 'abstain'), source='ocr')


class FieldStabilizerTest(unittest.TestCase):
    def test_present_read_passes_through_not_held(self):
        fs = FieldStabilizer()
        out = fs.apply(table_key='t', hand_key='H1', state=_state(pot=10.0, to_call=3.0))
        self.assertEqual(out['pot']['pot_bb'], 10.0)
        self.assertNotIn('held', out['pot'])
        self.assertEqual(out['to_call']['to_call_bb'], 3.0)

    def test_single_frame_pot_gap_is_filled_and_marked_held(self):
        fs = FieldStabilizer()
        fs.apply(table_key='t', hand_key='H1', state=_state(pot=10.0, to_call=3.0))
        out = fs.apply(table_key='t', hand_key='H1', state=_state(pot=None, to_call=None))
        self.assertEqual(out['pot']['pot_bb'], 10.0)         # buraco preenchido
        self.assertTrue(out['pot']['held'])
        self.assertEqual(out['pot']['age'], 1)
        self.assertEqual(out['pot']['source'], 'held')
        self.assertEqual(out['to_call']['to_call_bb'], 3.0)
        self.assertTrue(out['to_call']['held'])

    def test_hold_expires_after_max_age(self):
        fs = FieldStabilizer(max_age=dict(pot=2))
        fs.apply(table_key='t', hand_key='H1', state=_state(pot=10.0))
        a = fs.apply(table_key='t', hand_key='H1', state=_state(pot=None))   # age 1
        b = fs.apply(table_key='t', hand_key='H1', state=_state(pot=None))   # age 2 (cap)
        c = fs.apply(table_key='t', hand_key='H1', state=_state(pot=None))   # expira
        self.assertEqual(a['pot']['pot_bb'], 10.0)
        self.assertEqual(b['pot']['pot_bb'], 10.0)
        self.assertIsNone(c['pot']['pot_bb'])
        self.assertNotIn('held', c['pot'])

    def test_new_hand_clears_memory_no_cross_boundary(self):
        fs = FieldStabilizer()
        fs.apply(table_key='t', hand_key='H1', state=_state(pot=50.0))
        out = fs.apply(table_key='t', hand_key='H2', state=_state(pot=None))
        self.assertIsNone(out['pot']['pot_bb'])              # NÃO herda o pote de H1

    def test_none_hand_key_treated_as_same_hand(self):
        fs = FieldStabilizer()
        fs.apply(table_key='t', hand_key='H1', state=_state(pot=10.0))
        out = fs.apply(table_key='t', hand_key=None, state=_state(pot=None))
        self.assertEqual(out['pot']['pot_bb'], 10.0)         # id ilegível não reseta
        self.assertTrue(out['pot']['held'])

    def test_present_read_is_never_overridden(self):
        fs = FieldStabilizer()
        fs.apply(table_key='t', hand_key='H1', state=_state(pot=10.0))
        out = fs.apply(table_key='t', hand_key='H1', state=_state(pot=25.0))
        self.assertEqual(out['pot']['pot_bb'], 25.0)         # usa a leitura nova
        self.assertNotIn('held', out['pot'])

    def test_refresh_resets_age(self):
        fs = FieldStabilizer(max_age=dict(pot=2))
        fs.apply(table_key='t', hand_key='H1', state=_state(pot=10.0))
        fs.apply(table_key='t', hand_key='H1', state=_state(pot=None))      # age 1
        fs.apply(table_key='t', hand_key='H1', state=_state(pot=12.0))      # confirma -> age 0
        out = fs.apply(table_key='t', hand_key='H1', state=_state(pot=None))  # age 1 de novo
        self.assertEqual(out['pot']['pot_bb'], 12.0)
        self.assertTrue(out['pot']['held'])
        self.assertEqual(out['pot']['age'], 1)

    def test_to_call_zero_is_a_real_value_not_a_gap(self):
        fs = FieldStabilizer()
        fs.apply(table_key='t', hand_key='H1', state=_state(to_call=5.0))
        out = fs.apply(table_key='t', hand_key='H1', state=_state(to_call=0.0))
        self.assertEqual(out['to_call']['to_call_bb'], 0.0)  # 0.0 (check) não é buraco
        self.assertNotIn('held', out['to_call'])

    def test_seat_stack_gap_is_filled_within_hand(self):
        fs = FieldStabilizer()
        fs.apply(table_key='t', hand_key='H1', state=_state(seats={'bot_left': _seat(40.0)}))
        out = fs.apply(table_key='t', hand_key='H1', state=_state(seats={'bot_left': _seat(None)}))
        self.assertEqual(out['seats']['bot_left']['stack_bb'], 40.0)
        self.assertTrue(out['seats']['bot_left']['held'])

    def test_empty_seat_is_not_held(self):
        fs = FieldStabilizer()
        fs.apply(table_key='t', hand_key='H1', state=_state(seats={'bot_left': _seat(40.0)}))
        out = fs.apply(table_key='t', hand_key='H1',
                       state=_state(seats={'bot_left': _seat(None, occupied=False)}))
        self.assertIsNone(out['seats']['bot_left']['stack_bb'])   # assento vazio: não ressuscita

    def test_tables_are_independent(self):
        fs = FieldStabilizer()
        fs.apply(table_key='t1', hand_key='H1', state=_state(pot=10.0))
        out = fs.apply(table_key='t2', hand_key='H1', state=_state(pot=None))
        self.assertIsNone(out['pot']['pot_bb'])               # t2 não vê a memória de t1

    def test_does_not_mutate_input_state(self):
        fs = FieldStabilizer()
        fs.apply(table_key='t', hand_key='H1', state=_state(pot=10.0))
        src = _state(pot=None)
        fs.apply(table_key='t', hand_key='H1', state=src)
        self.assertIsNone(src['pot']['pot_bb'])               # original intacto


if __name__ == '__main__':
    unittest.main()
