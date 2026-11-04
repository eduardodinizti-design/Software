import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[2]/'tools/check_real_table_crops.py'
spec = importlib.util.spec_from_file_location('crop_acceptance', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class CropAcceptance(unittest.TestCase):
    def test_complete_reference_passes(self):
        self.assertTrue(module.assess([module.REGIONS['visible_table']])['passed'])
    def test_felt_without_bottom_controls_fails(self):
        self.assertFalse(module.assess([(12,36,698,1100)])['passed'])
    def test_desktop_box_fails(self):
        self.assertFalse(module.assess([(0,0,2072,1278)])['passed'])
    def test_no_detection_fails(self):
        self.assertFalse(module.assess([])['passed'])
