import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from visualpilot.pppoker.core import Region
from visualpilot.pppoker.lobby_capture import capture_lobby


class Capture:
    source='test_rgb_fixture'
    def __init__(self):
        self.bounds=[Region(-100,0,100,80),Region(0,0,120,80)]
        self.closed=False;self.grabs=[];self.fail=False;self.wrong_shape=False;self.changed=False;self.uniform=False
    def __enter__(self):return self
    def __exit__(self,*args):self.closed=True
    def monitors(self):return self.bounds if not self.changed or not self.grabs else [Region(0,0,80,80)]
    def grab(self,region):
        self.grabs.append(region)
        if self.fail:raise OSError('captura indisponível')
        pixels=np.zeros((region.height,region.width,3),np.uint8)
        if not self.uniform:
            pixels[:,:,0]=np.arange(region.width,dtype=np.uint8)
            pixels[:,:,1]=np.arange(region.height,dtype=np.uint8)[:,None]
            pixels[:,:,2]=217
        self.original=pixels.copy()
        return pixels[:-1] if self.wrong_shape else pixels


class LobbyCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.output=Path(self.temp.name)/'capture';self.capture=Capture()
    def tearDown(self):self.temp.cleanup()
    def run_capture(self,**kwargs):return capture_lobby(self.output,capture_factory=lambda:self.capture,**kwargs)

    def test_native_rgb_png_and_negative_monitor_origin(self):
        result=self.run_capture(region=Region(-80,10,50,40))
        with Image.open(self.output/'lobby.png') as image:
            self.assertEqual(image.format,'PNG');self.assertEqual(image.size,(50,40))
            np.testing.assert_array_equal(np.asarray(image),self.capture.original)
        saved=json.loads((self.output/'capture.json').read_text())
        self.assertEqual(saved,result)
        self.assertEqual(saved['region'],dict(left=-80,top=10,width=50,height=40))
        self.assertEqual(saved['png_sha256'],hashlib.sha256((self.output/'lobby.png').read_bytes()).hexdigest())
        self.assertEqual(saved['source'],'test_rgb_fixture')
        self.assertEqual(saved['validation_state'],'awaiting_visual_check')
        self.assertTrue(self.capture.closed)

    def test_whole_monitor_uses_reported_bounds(self):
        result=self.run_capture(monitor=2)
        self.assertEqual(result['image_size'],[120,80])
        self.assertEqual(self.capture.grabs,[self.capture.bounds[1]])

    def test_outside_cross_monitor_and_invalid_index_do_not_capture(self):
        for kwargs in (dict(region=Region(-110,0,20,20)),dict(region=Region(-10,0,20,20)),dict(monitor=3)):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.run_capture(**kwargs)
        self.assertFalse(self.capture.grabs);self.assertFalse(self.output.exists())

    def test_gap_between_monitors_rejected(self):
        self.capture.bounds=[Region(-120,0,100,80),Region(0,0,120,80)]
        with self.assertRaises(ValueError):self.run_capture(region=Region(-20,0,10,10))
        self.assertFalse(self.capture.grabs)

    def test_no_overwrite_and_no_capture_on_existing_output(self):
        self.output.mkdir();(self.output/'lobby.png').write_bytes(b'preserve')
        with self.assertRaises(ValueError):self.run_capture(monitor=1)
        self.assertEqual((self.output/'lobby.png').read_bytes(),b'preserve')
        self.assertFalse(self.capture.grabs)

    def test_capture_failure_closes_context_and_does_not_write_image(self):
        self.capture.fail=True
        with self.assertRaises(OSError):self.run_capture(monitor=1)
        self.assertTrue(self.capture.closed);self.assertFalse(self.output.exists())

    def test_shape_or_monitor_change_prevents_success_artifact(self):
        for attr in ('wrong_shape','changed'):
            self.capture=Capture();setattr(self.capture,attr,True)
            with self.subTest(attr=attr),self.assertRaises(ValueError):self.run_capture(monitor=1)
            self.assertTrue(self.capture.closed);self.assertFalse(self.output.exists())

    def test_uniform_image_requires_review(self):
        self.capture.uniform=True
        result=self.run_capture(monitor=1)
        self.assertTrue(result['uniform_image'])
        self.assertEqual(result['validation_state'],'awaiting_visual_check')

    def test_mutually_exclusive_inputs_and_region_validation(self):
        for kwargs in ({},dict(region=Region(0,0,1,1),monitor=1),dict(monitor=0),dict(monitor=True)):
            with self.assertRaises(ValueError):self.run_capture(**kwargs)
        for values in ((0,0,0,10),(0,0,10,-1),(0.5,0,10,10)):
            with self.assertRaises(ValueError):Region(*values)


if __name__=='__main__':unittest.main()
