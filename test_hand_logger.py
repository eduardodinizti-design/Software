"""LiveHandLogger: agrega frames do observador em mãos e grava (fundação do tracker)."""
import unittest

from hand_logger import LiveHandLogger, clean_nameplate


class _FakeHand:
    def __init__(self, kw):
        self.data = dict(kw)
        self.data['board'] = {}
        self.data['advice'] = []

    def board(self, street, cards):
        self.data['board'][street] = list(cards)
        return self

    def advice(self, **kw):
        self.data['advice'].append(kw)
        return self


class _FakeRecorder:
    def __init__(self):
        self.committed = []

    def begin(self, **kw):
        return _FakeHand(kw)

    def commit(self, h):
        self.committed.append(h.data)


def _result(hand_id, *, cards=None, recommended=None, hero_pos='SB', board=None):
    return dict(
        is_table=True,
        hand=dict(hand_id=hand_id, hand_number=int(hand_id.split('-')[-2]) if '-' in hand_id else 1),
        tournament=dict(name='NEFERTITI', is_pko=False, paid=9, players_left=33),
        hero_cards=cards,
        table_state=dict(
            positions={'hero': hero_pos, 'bot_left': 'BB', 'top_center': 'CO'},
            seats={'hero': dict(occupied=True, stack_bb=5.3, raw='Just do it 5,3 BB'),
                   'bot_left': dict(occupied=True, stack_bb=36.0, raw='nie sacatrapoo 36BB'),
                   'top_center': dict(occupied=True, stack_bb=42.5, raw='Homem Sol 42,5 BB'),
                   'right_up': dict(occupied=False, stack_bb=None, raw='')}),
        board=board or {},
        advice=dict(recommended=recommended, spot='push_fold', hero_position=hero_pos,
                    validated=True, ev=1.2, source='nash') if recommended else {})


class CleanNameplateTests(unittest.TestCase):
    def test_extrai_nick_do_raw(self):
        self.assertEqual(clean_nameplate('nie sacatrapoo 394BB'), 'sacatrapoo')
        self.assertEqual(clean_nameplate('ev VorySky 36,0 BB'), 'VorySky')

    def test_vazio(self):
        self.assertIsNone(clean_nameplate(''))
        self.assertIsNone(clean_nameplate(None))


class LoggerTests(unittest.TestCase):
    def test_grava_mao_ao_mudar_hand_id(self):
        rec = _FakeRecorder()
        log = LiveHandLogger(rec)
        log.observe('t1', _result('H-100-1', cards=['9d', '6d'], recommended='all_in'))
        log.observe('t1', _result('H-100-1', cards=['9d', '6d'], recommended='all_in'))  # mesma mão
        self.assertEqual(len(rec.committed), 0)                 # ainda aberta
        log.observe('t1', _result('H-200-1', cards=['As', 'Kd'], recommended='raise'))  # mão nova
        self.assertEqual(len(rec.committed), 1)                 # a 1a foi fechada
        h = rec.committed[0]
        self.assertEqual(h['hand_id'], 'H-100-1')
        self.assertEqual(h['hero']['cards'], ['9d', '6d'])
        self.assertEqual(h['hero']['position'], 'SB')
        self.assertEqual(h['advice'][0]['recommended'], 'all_in')
        self.assertTrue(h['advice'][0]['validated'])
        ids = {o['id'] for o in h['opponents']}
        self.assertIn('sacatrapoo', ids)                        # adversário por nick

    def test_flush_fecha_abertas(self):
        rec = _FakeRecorder()
        log = LiveHandLogger(rec)
        log.observe('t1', _result('H-1-1', cards=['Ah', 'Ac'], recommended='all_in'))
        log.flush()
        self.assertEqual(len(rec.committed), 1)
        self.assertEqual(rec.committed[0]['hero']['cards'], ['Ah', 'Ac'])

    def test_board_e_gravado(self):
        rec = _FakeRecorder()
        log = LiveHandLogger(rec)
        log.observe('t1', _result('H-5-1', cards=['Ah', 'Kh'],
                                   board=dict(cards=['2c', '6c', '8h'], street='FLOP')))
        log.flush()
        self.assertEqual(rec.committed[0]['board'].get('flop'), ['2c', '6c', '8h'])

    def test_ignora_sem_hand_id_e_nao_mesa(self):
        rec = _FakeRecorder()
        log = LiveHandLogger(rec)
        log.observe('t1', dict(is_table=True, hand={}))          # sem hand_id
        log.observe('t1', dict(is_table=False))                  # não é mesa
        log.flush()
        self.assertEqual(rec.committed, [])

    def test_duas_mesas_independentes(self):
        rec = _FakeRecorder()
        log = LiveHandLogger(rec)
        log.observe('t1', _result('A-1-1', cards=['9d', '6d'], recommended='all_in'))
        log.observe('t2', _result('B-1-1', cards=['As', 'Ks'], recommended='raise'))
        log.flush()
        self.assertEqual({h['hand_id'] for h in rec.committed}, {'A-1-1', 'B-1-1'})


if __name__ == '__main__':
    unittest.main()
