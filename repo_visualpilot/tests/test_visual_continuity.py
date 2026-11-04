import unittest
import numpy as np
from visualpilot.pppoker.visual_continuity import sample_upper, matches

class Continuity(unittest.TestCase):
    def setUp(self):
        self.frame=np.random.default_rng(4).integers(0,256,(800,800,3),dtype=np.uint8)
        self.a=[40,40,400,700];self.b=[32,40,408,708]
    def test_common_pixels_across_crop_change(self):
        self.assertTrue(matches(sample_upper(self.frame,self.a),sample_upper(self.frame,self.b),self.a,self.b))
    def test_changed_content_rejected(self):
        changed=self.frame.copy();changed[50:150,60:200]=0
        self.assertFalse(matches(sample_upper(self.frame,self.a),sample_upper(changed,self.b),self.a,self.b))
    def test_flat_felt_rejected(self):
        frame=np.full_like(self.frame,70)
        self.assertFalse(matches(sample_upper(frame,self.a),sample_upper(frame,self.b),self.a,self.b))
    def test_large_geometry_change_rejected(self):
        box=[140,40,400,700]
        self.assertFalse(matches(sample_upper(self.frame,self.a),sample_upper(self.frame,box),self.a,box))
