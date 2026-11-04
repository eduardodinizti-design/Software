"""Synthetic pixel sequences: motion + changing lower content, not live poker."""
import unittest
import numpy as np
from visualpilot.pppoker.multi_table_tracker import MultiTableTracker


def frame(positions=(50,750), changed=False, shared=False):
    image=np.full((850,1500,3),20,dtype=np.uint8)
    for identity,x in enumerate(positions):
        image[50:750,x:x+350]=[30,120,50]
        color=[255,0,0] if identity==0 or shared else [0,0,255]
        image[70:110,x+20:x+80]=color
        image[400:440,x+100:x+170]=[255,255,255] if identity==0 else [0,0,0]
        if changed:
            image[500:560,x+100:x+170]=[200,100,200]
    return image


class MovingContent(unittest.TestCase):
    def test_translation_and_lower_content_change(self):
        tracker=MultiTableTracker()
        first=tracker.scan_unity_surface(frame())
        second=tracker.scan_unity_surface(frame((100,800),True))
        self.assertEqual([t.table_id for t in first],[t.table_id for t in second])
        self.assertEqual([t.geometry_version for t in second],[2,2])

    def test_swap_and_lower_content_change(self):
        tracker=MultiTableTracker()
        first=tracker.scan_unity_surface(frame())
        second=tracker.scan_unity_surface(frame((750,50),True))
        self.assertEqual(first[0].table_id,second[1].table_id)
        self.assertEqual(first[1].table_id,second[0].table_id)
        self.assertEqual([t.geometry_version for t in second],[2,2])
        self.assertEqual(len(tracker.active_tables),2)

    def test_shared_upper_region_blocks_swapping(self):
        tracker=MultiTableTracker();first=tracker.scan_unity_surface(frame(shared=True))
        second=tracker.scan_unity_surface(frame((750,50),True,True))
        self.assertTrue(all(t.status=='AMBIGUOUS' for t in second))
        self.assertFalse({t.table_id for t in first}&{t.table_id for t in second})

    def test_changed_upper_region_blocks_identity(self):
        tracker=MultiTableTracker();first=tracker.scan_unity_surface(frame())
        image=frame((100,800),True)
        image[70:110,120:180]=[255,255,0]
        second=tracker.scan_unity_surface(image)
        self.assertEqual(second[0].status,'AMBIGUOUS')
        self.assertNotEqual(first[0].table_id,second[0].table_id)

    def test_capture_gap_blocks_moving_anchor(self):
        tracker=MultiTableTracker();tracker.scan_unity_surface(frame())
        tracker.scan_unity_surface(None)
        self.assertTrue(all(t.status=='AMBIGUOUS' for t in tracker.scan_unity_surface(frame((100,800),True))))

    def resized_frame(self, changed):
        import cv2
        source=frame(changed=changed)
        output=np.full((1650,1700,3),20,dtype=np.uint8)
        for old_x,new_x in [(50,50),(750,900)]:
            crop=source[50:750,old_x:old_x+350]
            output[100:1500,new_x:new_x+700]=cv2.resize(crop,(700,1400),interpolation=cv2.INTER_NEAREST)
        return output

    def test_resize_unchanged_content_preserves_exact_signature(self):
        tracker=MultiTableTracker();first=tracker.scan_unity_surface(frame())
        second=tracker.scan_unity_surface(self.resized_frame(False))
        self.assertEqual(len(second),2)
        self.assertEqual([t.table_id for t in first],[t.table_id for t in second])
        self.assertEqual([t.geometry_version for t in second],[2,2])

    def test_resize_with_changed_content_blocks_uncertain_history(self):
        tracker=MultiTableTracker();first=tracker.scan_unity_surface(frame())
        second=tracker.scan_unity_surface(self.resized_frame(True))
        self.assertEqual(len(second),2)
        self.assertTrue(all(t.status=='AMBIGUOUS' for t in second))
        self.assertFalse({t.table_id for t in first}&{t.table_id for t in second})
        self.assertEqual(len(tracker.active_tables),2)

    def test_changed_top_does_not_poison_other_table(self):
        tracker=MultiTableTracker();first=tracker.scan_unity_surface(frame())
        changed=frame((100,800),True)
        changed[70:110,120:180]=[255,255,0]
        second=tracker.scan_unity_surface(changed)
        self.assertEqual(second[0].status,'AMBIGUOUS')
        self.assertEqual(second[1].table_id,first[1].table_id)
        self.assertEqual(second[1].status,'CANDIDATE')

    def test_repeat_resize_keeps_state_bounded(self):
        tracker=MultiTableTracker()
        for i in range(40):
            tracker.scan_unity_surface(frame() if i%2==0 else self.resized_frame(True))
            self.assertLessEqual(len(tracker.active_tables),2)
            self.assertLessEqual(len(tracker._visual_tracks),tracker.max_tables*4)
            self.assertLessEqual(len(tracker._continuity),tracker.max_tables)
