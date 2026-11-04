import unittest
import numpy as np
from visualpilot.pppoker.multi_table_tracker import MultiTableTracker

class ObserverRegression(unittest.TestCase):
    def frame(self, swapped=False):
        f=np.full((800,1400,3),20,dtype=np.uint8)
        for x,color in [(50,(255,0,0) if not swapped else (0,0,255)),(750,(0,0,255) if not swapped else (255,0,0))]:
            f[50:750,x:x+350]=[30,120,50]
            f[70:100,x+20:x+50]=color
        return f
    def test_gray_background_and_swap(self):
        t=MultiTableTracker();a=t.scan_unity_surface(self.frame());b=t.scan_unity_surface(self.frame(True))
        self.assertEqual(len(a),2)
        self.assertEqual(a[0].box_physical,[50,50,350,700])
        self.assertEqual(a[0].table_id,b[1].table_id)
        self.assertEqual(a[1].table_id,b[0].table_id)
        self.assertEqual(b[1].geometry_version,2)
    def test_identical_regions_are_ambiguous(self):
        f=self.frame();f[50:750,750:1100]=f[50:750,50:400]
        t=MultiTableTracker();result=t.scan_unity_surface(f)
        self.assertEqual(len(result),2)
        self.assertTrue(all(x.status=='AMBIGUOUS' for x in result))
        self.assertNotEqual(result[0].table_id,result[1].table_id)
    def test_non_image_never_creates_tables(self):
        t=MultiTableTracker()
        self.assertEqual(t.scan_unity_surface([[100,100,700,1400]]),[])
        self.assertEqual(t.scan_unity_surface(None),[])
    def test_invalid_crop_rejected(self):
        self.assertEqual(MultiTableTracker().scan_unity_surface(self.frame(),[[0,700,500,500]]),[])

    def test_local_content_change_preserves_unique_anchor(self):
        tracker=MultiTableTracker();first=tracker.scan_unity_surface(self.frame())
        changed=self.frame();changed[500:580,100:200]=[255,255,255]
        second=tracker.scan_unity_surface(changed)
        self.assertEqual(first[0].table_id,second[0].table_id)
        self.assertEqual(second[0].geometry_version,1)
        self.assertEqual(second[0].status,'CANDIDATE')
        self.assertEqual(len({v[0] for v in tracker._visual_tracks.values()}),2)

    def test_shared_anchor_does_not_transfer_identity(self):
        f=self.frame();f[50:190,750:1100]=f[50:190,50:400]
        f[300:340,800:850]=[255,255,255]
        tracker=MultiTableTracker();tracker.scan_unity_surface(f)
        f[500:580,100:200]=[255,255,255]
        second=tracker.scan_unity_surface(f)
        self.assertEqual(second[0].status,'AMBIGUOUS')

    def test_gap_blocks_anchor_recovery(self):
        tracker=MultiTableTracker();tracker.scan_unity_surface(self.frame())
        tracker.scan_unity_surface(None)
        changed=self.frame();changed[500:580,100:200]=[255,255,255]
        self.assertEqual(tracker.scan_unity_surface(changed)[0].status,'AMBIGUOUS')
