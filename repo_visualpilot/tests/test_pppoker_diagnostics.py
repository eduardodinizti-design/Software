import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from visualpilot.pppoker.observer.perception import read_table,CachedReader
from visualpilot.pppoker.replay.reader import ReplayReader
from visualpilot.pppoker.observer.validation import validate_latest

class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader=CachedReader(ReplayReader())
        cls.image=np.array(Image.open(Path(__file__).parent/'fixtures/training/hero_3s_Qh.png').convert('RGB'))
    def test_partial_card_preserved_only_in_diagnostics(self):
        with patch('visualpilot.pppoker.training.perception.rank_field',side_effect=[('?',0.),('Q',.99)]):
            r=read_table(self.reader,self.image)
        details=r['diagnostics']['hero']['cards']
        self.assertEqual(len(details),2)
        self.assertEqual(details[0]['rejection'],'rank')
        self.assertEqual(details[1]['card'],'Qh')
        self.assertEqual(r['hero'],[])
        self.assertEqual(r['status'],'partial')
        self.assertEqual(len(r['evidence']['hero']),2)
    def test_missing_board_detection_never_means_preflop(self):
        with patch('visualpilot.pppoker.observer.perception.rectangles',return_value=[]):
            r=read_table(self.reader,self.image)
        self.assertIsNone(r['street'])
        self.assertEqual(r['board_status'],'unknown')
        self.assertEqual(r['status'],'partial')
    def test_invalidation_downgrades_complete_read(self):
        a=np.zeros((100,100,3),dtype=np.uint8);b=a.copy();b[70:80,50:70]=255
        r=dict(status='read',hero=['As','Kh'],board=['2c','3c','4h'],street='flop',evidence_size=[100,100],evidence=dict(hero=[[50,70,20,10]],board=[[30,40,40,10]]))
        result=validate_latest(r,a,b)
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['board'],r['board'])
