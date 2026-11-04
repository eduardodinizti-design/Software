import tempfile
import hashlib
import threading
import unittest
from unittest.mock import patch
from visualpilot.lab.server import LaboratorySession

class HandoffTests(unittest.TestCase):
    def event(self,index=0):
        obs=dict(table='laboratory-table',generation=index+1,frame_sha256=hashlib.sha256(b'fixture').hexdigest())
        return dict(index=index,observation=obs,reading=dict(hero_buttons=[dict(action='fold',amount=None,unit=None),dict(action='call',amount=2.5,unit='BB')]),
                    decision=dict(status='found',observation=obs,options=[dict(action='call',frequency=1,sizing_bb=2.5)])),b'fixture'

    def test_manual_override_cancelled_auto_and_fresh_resume(self):
        with tempfile.TemporaryDirectory() as root,patch('visualpilot.lab.server.VisualLaboratory') as factory:
            factory.return_value.observe.side_effect=lambda i,o:self.event(i)
            s=LaboratorySession(root)
            old=s.observe(0,False)
            s.control('paused');self.assertEqual(s.apply(old['token'])['status'],'blocked')
            s.control('manual');manual=s.observe(0,False)
            self.assertEqual(s.apply(manual['token'])['status'],'blocked')
            result=s.apply(manual['token'],'human','fold')
            self.assertEqual((result['status'],result['actor'],result['action']),('applied','human','fold'))
            self.assertEqual(s.apply(manual['token'],'human','call')['status'],'blocked')
            s.control('automatic')
            self.assertEqual(s.apply(manual['token'])['status'],'blocked')
            fresh=s.observe(1,False)
            self.assertEqual(s.apply(fresh['token'])['actor'],'engine')
            self.assertIn('"actor": "human"',(s.folder/'events.jsonl').read_text())

    def test_control_cancels_ocr_in_flight_without_waiting_for_it(self):
        with tempfile.TemporaryDirectory() as root,patch('visualpilot.lab.server.VisualLaboratory') as factory:
            entered=threading.Event();release=threading.Event()
            def slow(i,o):
                entered.set();release.wait(5);return self.event(i)
            factory.return_value.observe.side_effect=slow
            s=LaboratorySession(root);result=[]
            thread=threading.Thread(target=lambda:result.append(s.observe(0,False)))
            thread.start();self.assertTrue(entered.wait(2))
            try:
                mode=s.control('manual')
                self.assertEqual(mode['mode'],'manual')
            finally:release.set();thread.join(5)
            self.assertEqual(result[0]['status'],'cancelled')
            self.assertIsNone(s.current)
            self.assertEqual(s.observe(0,False,revision=0)['status'],'cancelled')

    def test_manual_cannot_invent_an_unavailable_button(self):
        with tempfile.TemporaryDirectory() as root,patch('visualpilot.lab.server.VisualLaboratory') as factory:
            factory.return_value.observe.side_effect=lambda i,o:self.event(i)
            s=LaboratorySession(root);s.control('manual');event=s.observe(0,False)
            self.assertEqual(s.apply(event['token'],'human','raise')['status'],'blocked')
            self.assertEqual(s.apply(event['token'],'human','call')['status'],'applied')
