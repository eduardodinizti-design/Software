from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from visualpilot.pppoker.observer.runtime import Mailbox, digest
from visualpilot.pppoker.observer.perception import read_table,CachedReader
from visualpilot.pppoker.replay.reader import ReplayReader

class QueueTests(unittest.TestCase):
    def setUp(self):self.now=0;self.q=Mailbox(limit=16,clock=lambda:self.now);self.img=np.zeros((100,50,3),dtype='uint8')
    def put(self,key):self.q.put(dict(table_key=key),self.img)
    def test_twelve_tables_do_not_evict_each_other(self):
        for k in range(12):self.put(str(k))
        self.assertEqual({self.q.take()[0]['table_key'] for _ in range(12)},{str(k) for k in range(12)})
    def test_replacements_and_expiration(self):
        self.put('one');self.now=1;self.put('one');self.assertEqual(self.q.replaced,1)
        self.assertEqual(self.q.take()[2],1);self.put('two');self.now=5;self.assertIsNone(self.q.take());self.assertEqual(self.q.expired,1)
    def test_busy_table_has_at_most_one_pending_frame(self):
        for _ in range(20):self.put('one')
        self.assertIsNone(self.q.take({'one'}));self.assertEqual(len(self.q.pending),1)
    def test_runtime_resize_matches_reader_normalization(self):
        import cv2
        rgb=np.random.default_rng(4).integers(0,256,(1485,835,3),dtype=np.uint8)
        self.q.put(dict(table_key='one'),rgb)
        normalized=self.q.take()[1]
        expected=cv2.resize(rgb,(755,round(1485*755/835)),interpolation=cv2.INTER_CUBIC)
        self.assertTrue(np.array_equal(normalized,expected))

    def test_default_limit_is_six(self):
        self.assertEqual(Mailbox().limit,6)

    def test_cache_ignores_only_window_title_strip(self):
        image=np.zeros((100,50,3),dtype='uint8')
        title=image.copy();title[:5]=255
        hero=image.copy();hero[80:90,20:30]=255
        self.assertEqual(digest(image),digest(title))
        self.assertNotEqual(digest(image),digest(hero))
    def test_capacity_is_bounded(self):
        for k in range(20):self.put(str(k))
        self.assertEqual(len(self.q.pending),16);self.assertEqual(self.q.overflow,4)
    def test_priority_and_fairness_despite_replacements(self):
        self.put('normal')
        with patch('visualpilot.pppoker.observer.runtime.action_hint',return_value=True):self.put('urgent')
        self.assertEqual(self.q.take()[0]['table_key'],'urgent')
        self.now=2.5;self.put('normal')
        with patch('visualpilot.pppoker.observer.runtime.action_hint',return_value=True):self.put('urgent')
        self.now=4;self.assertEqual(self.q.take()[0]['table_key'],'urgent')
        self.now=4.1;self.put('normal')
        with patch('visualpilot.pppoker.observer.runtime.action_hint',return_value=True):self.put('urgent')
        self.assertEqual(self.q.take()[0]['table_key'],'normal')
    def test_removed_tables_are_purged(self):
        self.put('one');self.put('two');self.q.retain({'two'});self.assertEqual(set(self.q.pending),{'two'})

class RealPerceptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.reader=CachedReader(ReplayReader())
    def read(self,path):return read_table(self.reader,np.array(Image.open(Path(__file__).parent/'fixtures'/path).convert('RGB')))
    def test_preflop_context(self):
        r=self.read('training/hero_3s_Qh.png');self.assertEqual(r['hero'],['3s','Qh']);self.assertIsNone(r['street']);self.assertEqual(r['board_status'],'unknown');self.assertEqual(r['status'],'partial')
        self.assertTrue(r['action_pending']);self.assertEqual(r['actions'],['Fold','Call 2,0 BB','Raise']);self.assertEqual(r['pot'],'Pot:7,0 BB')
    @unittest.skipUnless((Path(__file__).parent/'fixtures/training/postflop.png').is_file(), 'Imagem postflop.png ausente no arquivo recebido')
    def test_turn_board_from_real_frame(self):
        r=self.read('training/postflop.png');self.assertEqual(r['board'],['6s','Qs','8s','4d']);self.assertEqual(r['street'],'turn');self.assertFalse(r['action_pending'])
    def test_popup_rejects_all_cards(self):
        r=self.read('recorded_session/note_popup.png');self.assertEqual(r['hero'],[]);self.assertIsNone(r['street'])

if __name__=='__main__':unittest.main()

class RuntimeInvalidationTests(unittest.TestCase):
    def test_services_are_started_before_frames_are_processed(self):
        import tempfile,threading
        from queue import Queue
        from visualpilot.pppoker.observer.runtime import PerceptionSession
        stop=threading.Event();out=Queue();started=[]
        class Service:
            def __init__(self,**kw):pass
            def start(self):started.append(True);stop.set()
            def close(self):pass
        with tempfile.TemporaryDirectory() as root,patch('visualpilot.pppoker.observer.runtime.OCRService',Service):
            PerceptionSession(root,stop,out,workers=2).run(capture=False)
        self.assertEqual(started,[True,True])

    def test_change_during_ocr_discards_old_result(self):
        import tempfile,threading
        from queue import Queue,Empty
        from time import monotonic
        from visualpilot.pppoker.observer.runtime import PerceptionSession
        entered=threading.Event();release=threading.Event();stop=threading.Event();out=Queue(128)
        class Service:
            def __init__(self,**kw):self.calls=0
            def call(self,kind,rgb,stopped):
                self.calls+=1
                if self.calls==1:entered.set();release.wait(3)
                return dict(status='read',hero=['As','Kh'] if rgb[80,30,0]==0 else ['Qs','Jh'],board=[],street='preflop',hand_id='one')
            def close(self):pass
        with tempfile.TemporaryDirectory() as root,patch('visualpilot.pppoker.observer.runtime.OCRService',Service):
            session=PerceptionSession(root,stop,out,workers=1);thread=threading.Thread(target=session.run,kwargs=dict(capture=False));thread.start()
            image=np.zeros((100,50,3),dtype='uint8');item=dict(table_key='table',number=1)
            try:
                session.frames.put(item,image);self.assertTrue(entered.wait(3))
                changed=image.copy();changed[80:89,28:37]=255;session.frames.put(item,changed);release.set()
                deadline=monotonic()+5;event=None
                while monotonic()<deadline:
                    e=out.get(timeout=3)
                    if e['kind']=='reading' and e['reading'].get('hero'):event=e;break
                self.assertEqual(event['reading']['hero'],['Qs','Jh'])
                self.assertGreaterEqual(sum(session.metrics['discarded_results'].values()),1)
            finally:release.set();stop.set();thread.join(5)
            self.assertFalse(thread.is_alive())
            import json
            records=[json.loads(line) for line in next(Path(root).rglob('percepcao.jsonl')).read_text().splitlines()]
            first=records[0]
            # Stronger invariant: the obsolete reading is rejected, not published
            # with only selected fields cleared. Its source stays in the rejection log.
            self.assertEqual(first['raw_reading']['hero'],['Qs','Jh'])
            self.assertFalse(any(row['reading'].get('hero')==['As','Kh'] for row in records))
            rejected=next(Path(root).rglob('rejeicoes.jsonl'))
            self.assertTrue(rejected.read_text().strip())
            self.assertEqual(first['visual_evidence']['status'],'saved')
            self.assertTrue((next(Path(root).rglob('percepcao.jsonl')).parent/first['visual_evidence']['path']).exists())
            self.assertIsNone(first['study_context']['decision']['reason'])
