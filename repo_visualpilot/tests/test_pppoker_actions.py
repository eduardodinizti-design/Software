from pathlib import Path
import unittest
import numpy as np
from PIL import Image
from visualpilot.pppoker.observer.perception import read_table,CachedReader
from visualpilot.pppoker.replay.reader import ReplayReader
from visualpilot.pppoker.observer.actions import read_actions

class ActionReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.reader=CachedReader(ReplayReader())
    def read(self,name):return read_table(self.reader,np.array(Image.open(Path(__file__).parent/'fixtures/actions'/name).convert('RGB')))
    def test_real_five_badges_and_hero_buttons_are_separate(self):
        r=self.read('right_99.png')
        actual={(a['player_label'],a['action']) for a in r['observed_actions']}
        self.assertEqual(actual,{('Jhavidpino','call'),('Chow Mein...','fold'),('smilekilla','raise'),('Mihcardoso7','fold'),('KenLy','call')})
        self.assertEqual(r['hero'],['5c','2s'])
        self.assertEqual(len(r['actions']),3)
        self.assertTrue(all(a['amount'] is None and a['player_id'] is None for a in r['observed_actions']))
    def test_real_flop_and_hero_fold(self):
        r=self.read('left_99.png');self.assertEqual(r['board'],['7h','As','Ts']);self.assertEqual(r['street'],'flop')
        self.assertIn(('vitriago','check'),{(a['player_label'],a['action']) for a in r['observed_actions']})
        self.assertTrue(any(a['player_label'].startswith('KKing') and a['action']=='fold' for a in r['observed_actions']))
    def test_unassigned_badge_is_not_given_an_invented_player(self):
        rgb=np.zeros((1400,755,3),dtype='uint8');box=[[300,300],[350,300],[350,320],[300,320]]
        r=read_actions([(box,'Raise',.99)],rgb)
        self.assertEqual(r[0]['action'],'raise');self.assertIsNone(r[0]['player_label'])
    def test_bottom_buttons_are_not_player_actions(self):
        rgb=np.zeros((1400,755,3),dtype='uint8');box=[[300,1300],[350,1300],[350,1320],[300,1320]]
        self.assertEqual(read_actions([(box,'Raise',.99)],rgb),[])

if __name__=='__main__':unittest.main()

class DuplicateCandidateTests(unittest.TestCase):
    def test_native_fallback_does_not_duplicate_visual_table(self):
        import threading
        from unittest.mock import patch
        from visualpilot.pppoker.multitable import discover
        stop=threading.Event();captured=[]
        class Capture:
            def __enter__(self):return self
            def __exit__(self,*args):pass
        detection=dict(monitor=1,box=[100,0,500,900],binding='visual',binding_reason='unbound',window_key=None,window_box=None)
        win=dict(pid=99999,handle=20,title='PPPoker',box=[100,0,500,900])
        reports=[dict(monitor=1,region=dict(left=0,top=0,width=1920,height=1080))]
        def receive(queue,payload):captured.append(payload);stop.set()
        with patch('visualpilot.pppoker.multitable.scan_monitors',return_value=(reports,[detection])),patch('visualpilot.pppoker.multitable.attach_windows',return_value=[detection]),patch('visualpilot.pppoker.multitable.latest',receive):
            discover(stop,None,lambda:[],capture_factory=Capture,windows_reader=lambda:[win])
        self.assertEqual(len(captured[0]['found']),1)
