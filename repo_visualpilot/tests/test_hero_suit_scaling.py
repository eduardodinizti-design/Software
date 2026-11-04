"""Real Hero glyphs, independent board reference, and invalid red shapes."""
import unittest
import cv2
import numpy as np
from visualpilot.pppoker.card_reader import CardRegionReader
from visualpilot.pppoker.observer.perception import CachedReader
from visualpilot.pppoker.replay.reader import ReplayReader
from visualpilot.pppoker.roi_engine import REGIONS, scaled_box
from visualpilot.pppoker.stream_node import prepare_capture
from visualpilot.pppoker.training.perception import suit
from pathlib import Path

class HeroSuitScalingTests(unittest.TestCase):
    def test_visual_discovery_crop_keeps_dim_hero_and_absent_cards_stay_pending(self):
        from visualpilot.pppoker.discovery import detect_tables
        from visualpilot.pppoker.observer.perception import read_table
        ocr = CachedReader(ReplayReader())
        reader = CardRegionReader(ocr)
        original = cv2.cvtColor(cv2.imread(str(Path(__file__).parent/'fixtures/actions/left_99.png')), cv2.COLOR_BGR2RGB)
        for visible in (True, False):
            with self.subTest(hero_visible=visible):
                table = original.copy()
                if not visible:
                    y, x, yy, xx = REGIONS['hero_cards'][0]
                    table[y:yy, x:xx] = (40, 70, 120)
                desktop = np.full((1700, 2200, 3), 32, np.uint8)
                desktop[20:20+table.shape[0], 20:20+table.shape[1]] = table
                x, y, width, height = detect_tables(desktop)[0]['box']
                image = prepare_capture(desktop[y:y+height, x:x+width])
                y, x, yy, xx = scaled_box(REGIONS['hero_cards'][0], image.shape[1], image.shape[0])
                result = reader.read_region('hero_cards', image[y:yy, x:xx])
                self.assertEqual([card['card'] for card in result['cards']], ['Th', '4d'] if visible else [], result)
                consolidated = read_table(ocr, image)
                self.assertEqual(consolidated['hero'], ['Th', '4d'] if visible else [], consolidated)
                if not visible:
                    self.assertEqual(result['status'], 'PENDING')

    def test_real_pairs_across_resampling_scales(self):
        reader = CardRegionReader(CachedReader(ReplayReader()))
        for filename, expected in [('left_99.png',['Th','4d']),('right_99.png',['5c','2s'])]:
            source = cv2.cvtColor(cv2.imread(str(Path(__file__).parent/'fixtures/actions'/filename)),cv2.COLOR_BGR2RGB)
            for scale in (1.,1.1,1.25,1.5,1.75,2.):
                with self.subTest(frame=filename,scale=scale):
                    image = prepare_capture(cv2.resize(source,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC))
                    y,x,yy,xx = scaled_box(REGIONS['hero_cards'][0],image.shape[1],image.shape[0])
                    result = reader.read_region('hero_cards',image[y:yy,x:xx])
                    self.assertEqual([c['card'] for c in result['cards']],expected,result)

    def test_red_non_suits_remain_pending(self):
        for name in ('rectangle','circle','line','noise','empty'):
            image = np.full((40,40,3),255,np.uint8)
            if name=='rectangle': cv2.rectangle(image,(8,8),(30,30),(240,0,0),-1)
            if name=='circle': cv2.circle(image,(20,20),12,(240,0,0),-1)
            if name=='line': cv2.line(image,(5,5),(30,30),(240,0,0),3)
            if name=='noise': image[np.random.default_rng(82).random((40,40))<.15]=(240,0,0)
            with self.subTest(shape=name): self.assertIsNone(suit(image)[0])
