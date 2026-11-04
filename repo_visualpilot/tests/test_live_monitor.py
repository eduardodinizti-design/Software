import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from visualpilot.viz.monitor import LiveMonitor


class LiveMonitorTests(unittest.TestCase):
    def setUp(self):
        self.now=10.;self.m=LiveMonitor(clock=lambda:self.now)
        self.image=np.zeros((40,30,3),dtype=np.uint8)

    def observe(self,t,buttons,hand='one',status='ok'):
        self.now=t
        self.m.frame('table',1,self.image)
        self.m.observe(dict(table='table',number=1,observed=t,latency=.2,
            reading=dict(status=status,hand_id=hand,hero=['As','Ks'],hero_buttons=buttons)),self.image)

    def test_preview_is_independent_from_reading_and_freezes_explicitly(self):
        self.m.frame('table',1,self.image)
        self.assertIsNotNone(self.m.snapshot()['table']['preview'])
        self.assertIsNone(self.m.snapshot()['table']['reading_age'])
        self.now=16
        self.assertEqual(self.m.snapshot()['table']['frame_age'],6)

    def test_interval_is_not_a_verified_action_and_gap_cancels(self):
        self.observe(10,[{'action':'call'}]);self.observe(12,[])
        event=self.m.snapshot()['table']['events'][-1]
        self.assertEqual(event['kind'],'buttons_hidden');self.assertEqual(event['seconds'],2)
        self.assertFalse(event['action_verified'])
        self.observe(13,[{'action':'call'}]);self.observe(20,[])
        self.assertEqual(self.m.snapshot()['table']['events'][-1]['kind'],'interval_cancelled')

    def test_unknown_and_hand_change_do_not_claim_action(self):
        self.observe(10,['call']);self.observe(11,[],status='pending')
        self.observe(12,['call']);self.observe(13,[],hand='two')
        self.assertFalse(any(e['kind']=='buttons_hidden' for e in self.m.snapshot()['table']['events']))

    def test_evidence_matches_observation_not_newer_preview_and_persists(self):
        with tempfile.TemporaryDirectory() as d:
            self.m.start(d);self.observe(10,['call'])
            self.m.frame('table',1,np.full_like(self.image,255))
            self.m.mark('table')
            entries=[json.loads(x) for x in (Path(d)/'acompanhamento/eventos.jsonl').read_text().splitlines()]
            sample=next(e for e in entries if e['kind']=='reading_sample')
            self.assertTrue((Path(d)/'acompanhamento'/sample['evidence']['path']).exists())
            self.assertEqual(sample['reading']['hero'],['As','Ks'])
            self.assertEqual(entries[-1]['kind'],'manual_review_marker')
            self.assertFalse(entries[-1]['action_verified'])

    def test_partial_board_still_times_legible_buttons_and_context_change_cancels(self):
        self.observe(10,['call'],status='partial')
        self.assertIsNotNone(self.m.snapshot()['table']['button_seconds'])
        self.now=11
        self.m.observe(dict(table='table',observed=11,reading=dict(status='read',hero=['Ah','Kh'],hero_buttons=[])),self.image)
        self.assertEqual(self.m.snapshot()['table']['events'][-1]['kind'],'interval_cancelled')

    def test_retired_table_and_bounds(self):
        for i in range(8):self.m.frame(str(i),i,self.image)
        self.assertEqual(len(self.m.snapshot()),6)
        self.m.retain({'1'});self.assertEqual(set(self.m.snapshot()),{'1'})
        for i in range(40):self.m.mark('1')
        self.assertEqual(len(self.m.snapshot()['1']['events']),30)
