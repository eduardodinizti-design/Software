import tempfile
from pathlib import Path
import unittest
import numpy as np
from coletar_sessao import run_session

class Clock:
    def __init__(self):self.t=0
    def __call__(self):return self.t
    def sleep(self,n):self.t+=n
class Engine:
    def __init__(self,clock,change=False):self.clock=clock;self.n=0;self.change=change
    def capture_frame(self,hwnd):
        self.clock.t+=15;self.n+=1
        return np.zeros((20,30,3),np.uint8),dict(status='SUCCESS',hwnd=hwnd,pid=2,process_created=self.n if self.change else 1,executable='PPPoker.exe')
class SessionTests(unittest.TestCase):
    def run_case(self,**kwargs):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);clock=Clock()
        return run_session(Engine(clock,kwargs.pop('change',False)),[1,2],minutes=1,output=Path(tmp.name),clock=clock,sleep=clock.sleep,analyze=lambda *a,**k:{'tables':[]},**kwargs)
    def test_duration_and_all_captures(self):
        folder,s=self.run_case();self.assertEqual(s['stop_reason'],'DURATION_COMPLETE');self.assertEqual(s['counts']['saved_frames'],4)
        self.assertEqual(len(list(folder.glob('*.png'))),4);self.assertFalse(s['accuracy_validated']);self.assertFalse(s['actions_executed'])
    def test_identity_change_stops(self):
        _,s=self.run_case(change=True);self.assertEqual(s['stop_reason'],'SOURCE_CHANGED')
    def test_budget(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);c=Clock()
        _,s=run_session(Engine(c),[1],minutes=1,budget_mb=1,output=Path(tmp.name),clock=c,sleep=c.sleep,analyze=lambda *a,**k:{'tables':[],'large':'x'*1100000})
        self.assertEqual(s['stop_reason'],'STORAGE_LIMIT');self.assertEqual(s['counts'].get('saved_frames',0),0)
if __name__=='__main__':unittest.main()
