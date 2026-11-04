import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from visualpilot.pppoker.table_boundaries import detect_control_anchored_tables

class RealBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[2]
        cls.image=Image.open(root/'public/assets/aistudio/_21D744E1-8BE6-4C79-82AF-5582DD6A9547__6988a9e2.png').convert('RGB')

    def test_scales_and_translation(self):
        for scale in (.5,.75,1.0,1.25):
            with self.subTest(scale=scale):
                im=self.image.resize((round(self.image.width*scale),round(self.image.height*scale)))
                frame=np.zeros((im.height+100,im.width+200,3),dtype=np.uint8)
                frame[40:40+im.height,70:70+im.width]=np.asarray(im)
                boxes=detect_control_anchored_tables(frame)
                self.assertTrue(boxes)
                x,y,w,h=boxes[0]
                self.assertLess(abs(x-(70+12*scale)),8)
                self.assertLess(abs(y-(40+36*scale)),8)
                self.assertGreaterEqual(x+w,70+698*scale)
                self.assertGreaterEqual(y+h,40+1260*scale)

    def test_missing_controls_not_invented(self):
        frame=np.array(self.image)
        frame[1190:1278,:710]=0
        self.assertEqual(detect_control_anchored_tables(frame),[])

    def test_green_controls_without_blue_table_rejected(self):
        frame=np.zeros_like(np.asarray(self.image))
        frame[1190:1278,:710]=np.asarray(self.image)[1190:1278,:710]
        self.assertEqual(detect_control_anchored_tables(frame),[])

    def test_two_real_table_copies_and_mixed_felt(self):
        from visualpilot.pppoker.multi_table_tracker import MultiTableTracker
        # Composed fixture, not evidence of two independent live tables.
        table=np.asarray(self.image)[:,:710]
        frame=np.zeros((1400,2400,3),dtype=np.uint8)
        frame[30:1308,30:740]=table
        frame[30:1308,820:1530]=table
        frame[100:1100,1700:2200]=[30,120,50]
        boxes=MultiTableTracker().detect_tables_from_unity_pixels(frame)
        self.assertEqual(len(boxes),3)
        self.assertTrue(any(x<100 and h>1200 for x,y,w,h in boxes))
        self.assertTrue(any(800<x<900 and h>1200 for x,y,w,h in boxes))
        self.assertIn((1700,100,500,1000),boxes)

    def test_upper_bound_six_candidates(self):
        from visualpilot.pppoker.multi_table_tracker import MultiTableTracker
        frame=np.zeros((700,3200,3),dtype=np.uint8)
        for i in range(7):
            frame[50:650,20+450*i:320+450*i]=[30,120,50]
        self.assertEqual(len(MultiTableTracker().detect_tables_from_unity_pixels(frame)),6)
