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
