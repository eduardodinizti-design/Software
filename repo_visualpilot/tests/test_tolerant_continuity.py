import unittest
import numpy as np
from visualpilot.pppoker.visual_continuity import normalized_upper, patch_error, tolerant_links


class TolerantContinuity(unittest.TestCase):
    def setUp(self):
        self.box=[0,0,350,700]
        self.a=np.random.default_rng(9).random((48,128,3),dtype=np.float32)
        self.record=('test-id',self.box,1)

    def test_single_close_candidate(self):
        links=tolerant_links([self.a+.005],[self.box],[(self.record,self.a)])
        self.assertEqual(links,{0:0})

    def test_near_identical_previous_tables_block_match(self):
        old=[(self.record,self.a),(('other',self.box,1),self.a+.001)]
        self.assertEqual(tolerant_links([self.a+.005],[self.box],old),{})

    def test_two_current_candidates_cannot_share_identity(self):
        self.assertEqual(tolerant_links([self.a+.005,self.a+.006],[self.box,self.box],[(self.record,self.a)]),{})

    def test_flat_surface_has_no_descriptor(self):
        self.assertIsNone(normalized_upper(np.full((700,350,3),90,np.uint8),self.box))

    def test_local_change_not_diluted(self):
        changed=self.a.copy();changed[:12,:16]=1-self.a[:12,:16]
        self.assertGreater(patch_error(self.a,changed),.045)
        self.assertEqual(tolerant_links([changed],[self.box],[(self.record,self.a)]),{})

    def test_nonuniform_resize_blocked(self):
        self.assertEqual(tolerant_links([self.a],[[0,0,400,1400]],[(self.record,self.a)]),{})

    def test_geometry_cannot_disambiguate_similar_previous_tables(self):
        other=('other',[0,0,1000,1000],1)
        self.assertEqual(tolerant_links([self.a],[self.box],[(self.record,self.a),(other,self.a)]),{})

    def test_additional_screenshot_resampling(self):
        import cv2
        from PIL import Image
        from pathlib import Path
        from visualpilot.pppoker.multi_table_tracker import MultiTableTracker
        root=Path(__file__).resolve().parents[2]/'public/assets/aistudio'
        fixtures=[('_4CCF9DD1-A945-450A-9C7C-2334847FE3E4__02419b13.png',(14,36,704,1244)),
                  ('image_2da5ef3e.png',(755,30,376,664))]
        for name,(x,y,w,h) in fixtures:
            crop=np.array(Image.open(root/name).convert('RGB'))[y:y+h,x:x+w].copy()
            for method in (cv2.INTER_LINEAR,cv2.INTER_CUBIC,cv2.INTER_AREA):
                for scale in (.75,1.25,2):
                    with self.subTest(fixture=name,method=method,scale=scale):
                        def place(im):
                            hh,ww=im.shape[:2];canvas=np.zeros((hh+40,ww+40,3),np.uint8)
                            canvas[20:20+hh,20:20+ww]=im
                            return canvas,[20,20,ww,hh]
                        tracker=MultiTableTracker();before,box=place(crop)
                        first=tracker.scan_unity_surface(before,[box])[0]
                        edited=crop.copy();edited[int(h*.8):int(h*.88),int(w*.4):int(w*.6)]=240
                        after,box2=place(cv2.resize(edited,(round(w*scale),round(h*scale)),interpolation=method))
                        second=tracker.scan_unity_surface(after,[box2])[0]
                        self.assertEqual(first.table_id,second.table_id)
                        self.assertEqual(second.status,'CANDIDATE')
