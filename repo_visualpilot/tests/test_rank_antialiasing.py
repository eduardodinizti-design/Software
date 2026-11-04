import unittest
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from visualpilot.pppoker.card_reader import CardRegionReader
from visualpilot.pppoker.observer.perception import CachedReader
from visualpilot.pppoker.replay.reader import ReplayReader
from visualpilot.pppoker.roi_engine import REGIONS


class RankAntialiasingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = CardRegionReader(CachedReader(ReplayReader()))

    def test_kings_at_production_threshold_with_light_variations(self):
        y1,x1,y2,x2 = REGIONS['board_turn'][0]
        for card in ('Kh','Ks'):
            source = np.array(Image.open(Path(__file__).parent/'fixtures/synthetic_deck'/f'{card}.png').convert('RGB'))
            crop = source[y1:y2,x1:x2]
            variants = {'original':crop, 'dim':(crop*.9).astype(np.uint8),
                        'blur':cv2.GaussianBlur(crop,(3,3),.35)}
            for name,image in variants.items():
                with self.subTest(card=card,variant=name):
                    result = self.reader.read_region('board_turn',image)
                    self.assertEqual(result['status'],'SUCCESS',result)
                    self.assertEqual(result['cards'][0]['card'],card)
                    self.assertGreaterEqual(result['cards'][0]['confidence'],.90)

    def test_blank_and_noise_are_not_cards(self):
        random = np.random.default_rng(89)
        for crop in (np.full((170,110,3),238,np.uint8),
                     random.integers(0,256,(170,110,3),dtype=np.uint8)):
            self.assertEqual(self.reader.read_region('board_turn',crop)['status'],'PENDING')
