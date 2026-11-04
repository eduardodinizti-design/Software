import json
from pathlib import Path
import unittest
import numpy as np
from visualpilot.pppoker.observer.validation import confirmations,validate_latest,confirmation_previous

class FieldValidationTests(unittest.TestCase):
    def test_empty_repeated_values_never_confirm_cards(self):
        r=dict(hero=[],board=[],street='preflop',hand_id='one')
        f=confirmations(r,r);self.assertFalse(f['hero']['confirmed']);self.assertFalse(f['board']['confirmed']);self.assertEqual(f['board']['state'],'not_dealt')
    def test_confirmation_window_requires_known_hand_and_does_not_rejuvenate(self):
        r=dict(hero=['As','Kh'],board=['2c','3c','4h'],street='flop',hand_id='one')
        self.assertIs(confirmation_previous(r,r,8,0),r)
        self.assertIsNone(confirmation_previous(r,r,11,0))
        self.assertIsNone(confirmation_previous(dict(r,hand_id='two'),r,8,0))
        self.assertIsNone(confirmation_previous(dict(r,hand_id=None),dict(r,hand_id=None),2,0))
        self.assertFalse(confirmations(dict(r,hand_id=None),dict(r,hand_id=None))['hero']['confirmed'])

    def test_cards_confirm_independently(self):
        r=dict(hero=['As','Kh'],board=['2c','3c','4h'],street='flop',hand_id='one')
        old=dict(r,hero=[])
        f=confirmations(r,old);self.assertFalse(f['hero']['confirmed']);self.assertTrue(f['board']['confirmed'])
        self.assertTrue(confirmations(r,r)['hero']['confirmed'])
        self.assertFalse(confirmations(dict(r,hand_id='two'),r)['hero']['confirmed'])
    def test_changed_button_preserves_cards(self):
        a=np.zeros((100,100,3),dtype='uint8');b=a.copy();b[90:99,0:100]=255
        r=dict(hero=['As','Kh'],board=['2c','3c','4h'],street='flop',actions=['Call'],evidence_size=[100,100],evidence=dict(hero=[[50,70,20,10]],board=[[30,40,40,10]],actions=[[0,90,100,10]]))
        out=validate_latest(r,a,b);self.assertEqual(out['hero'],r['hero']);self.assertEqual(out['board'],r['board']);self.assertEqual(out['actions'],[])
    def test_changed_hero_preserves_board(self):
        a=np.zeros((100,100,3),dtype='uint8');b=a.copy();b[70:80,50:70]=255
        r=dict(hero=['As','Kh'],board=['2c','3c','4h'],street='flop',evidence_size=[100,100],evidence=dict(hero=[[50,70,20,10]],board=[[30,40,40,10]]))
        out=validate_latest(r,a,b);self.assertEqual(out['hero'],[]);self.assertEqual(out['board'],r['board'])
    def test_minor_noise_does_not_discard(self):
        a=np.full((100,100,3),100,dtype='uint8');b=np.full_like(a,104)
        out=validate_latest(dict(hero=['As','Kh'],board=[],street='preflop'),a,b);self.assertEqual(out['invalidated_fields'],[])
    def test_hand_change_invalidates_all(self):
        a=np.zeros((100,100,3),dtype='uint8');b=a.copy();b[10:20,10:30]=255
        r=dict(hero=['As','Kh'],board=['2c','3c','4h'],street='flop',hand_id='old',evidence_size=[100,100],evidence=dict(hand_id=[[10,10,20,10]]))
        out=validate_latest(r,a,b);self.assertEqual(out['hero'],[]);self.assertEqual(out['board'],[]);self.assertIsNone(out['hand_id'])

class RecordedRegressionTests(unittest.TestCase):
    def test_user_log_never_confirms_missing_hero(self):
        rows=[json.loads(x) for x in (Path(__file__).parent/'fixtures/field_fix/reported_session.jsonl').read_text().splitlines()]
        previous={};old_false=0
        for row in rows:
            reading=row['reading'];key=row['table'];fields=confirmations(reading,previous.get(key))
            self.assertFalse(fields['hero']['confirmed'])
            old_false+=int(row['confirmed'] and not reading['hero']);previous[key]=reading
        self.assertEqual(old_false,12)
    def test_real_dim_cards_and_coloured_board_ranks(self):
        from PIL import Image
        from visualpilot.pppoker.observer.perception import CachedReader,read_table
        from visualpilot.pppoker.replay.reader import ReplayReader
        reader=CachedReader(ReplayReader())
        cases={'33_0':(['7d','3s'],[]),'66_0':(['8h','Jd'],[]),'33_1':(['Kd','Js'],['Ts','Th','Qh','5d']),'164_1':(['5c','2s'],['Ad','Qc','2h','Kh','9d'])}
        for name,(hero,board) in cases.items():
            with self.subTest(image=name):
                path=Path(__file__).parent/'fixtures/field_fix'/(name+'.png')
                if not path.is_file():
                    self.skipTest('Imagem ausente no arquivo recebido: '+name+'.png')
                rgb=np.array(Image.open(path).convert('RGB'))
                reading=read_table(reader,rgb)
                self.assertEqual(reading['hero'],hero,name);self.assertEqual(reading['board'],board,name)
