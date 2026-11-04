import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from visualpilot.pppoker.observer.archive import EvidenceArchive, study_record

class ArchiveTests(unittest.TestCase):
    def test_lossless_image_and_reuse(self):
        with tempfile.TemporaryDirectory() as d:
            a=EvidenceArchive(d)
            rgb=np.random.default_rng(0).integers(0,256,(50,60,3),dtype=np.uint8)
            e=a.save('table',rgb,0)
            restored=cv2.cvtColor(cv2.imread(str(Path(d)/e['path'])),cv2.COLOR_BGR2RGB)
            self.assertTrue(np.array_equal(rgb,restored))
            self.assertEqual(a.save('table',rgb,1)['path'],e['path'])
            self.assertEqual(a.count,1)

    def test_throttle_per_table_and_quota(self):
        with tempfile.TemporaryDirectory() as d:
            a=EvidenceArchive(d)
            rgb=np.zeros((30,30,3),dtype=np.uint8)
            a.save('a',rgb,0)
            self.assertEqual(a.save('a',rgb+1,1)['status'],'throttled')
            self.assertEqual(a.save('b',rgb+1,1)['status'],'saved')
            self.assertEqual(a.save('a',rgb+2,10)['status'],'saved')
            a.max_bytes=a.bytes
            self.assertEqual(a.save('a',rgb+3,20)['status'],'limit_reached')

    def test_storage_failure_is_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            a=EvidenceArchive(d)
            with patch.object(Path,'write_bytes',side_effect=OSError('disk full')):
                e=a.save('a',np.zeros((20,20,3),dtype=np.uint8),0)
            self.assertEqual(e['status'],'error')
            self.assertEqual(a.count,0)

    def test_raw_cards_separate_and_no_invented_motive(self):
        raw=dict(hero=['As','Kd'],board=['2c','3c','4h'],street='flop')
        reading=dict(raw,hero=[],invalidated_fields=['hero'])
        entry=study_record(dict(table='a',reading=reading,confirmed=False),raw,
                           dict(status='throttled',path=None),2,
                           datetime(2026,10,24,12,tzinfo=timezone.utc))
        r=json.loads(json.dumps(entry))
        self.assertEqual(r['raw_reading']['hero'],['As','Kd'])
        self.assertEqual(r['study_context']['hero_cards'],[])
        self.assertIsNone(r['study_context']['decision']['reason'])
        self.assertFalse(r['study_context']['action_event_verified'])
        self.assertEqual(r['captured_at_estimate'],'2026-10-24T11:59:58+00:00')
