from pathlib import Path
import unittest
import cv2
import numpy as np
from visualpilot.pppoker.card_reader import CardRegionReader
from visualpilot.pppoker.replay.reader import ReplayReader

ROOT = Path(__file__).parent/'fixtures'/'colored_deck'

class ColoredCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = CardRegionReader(ReplayReader(), colored_deck=True)
        cls.flop = cv2.cvtColor(cv2.imread(str(ROOT/'flop.png')), cv2.COLOR_BGR2RGB)
        cls.hero = cv2.cvtColor(cv2.imread(str(ROOT/'hero.png')), cv2.COLOR_BGR2RGB)

    def test_observed_cards_and_folded_cards(self):
        for region, image, expected in [('board_flop', self.flop, ['2c','4h','9c']),
                                        ('hero_cards', self.hero, ['Th','6c'])]:
            with self.subTest(region=region):
                result = self.reader.read_region(region, image)
                self.assertEqual([c['card'] for c in result['cards']], expected, result)

    def test_compression_and_scale_keep_folded_ten(self):
        variants = [cv2.resize(self.hero, None, fx=.6, fy=.6),
                    (self.hero.astype(float)*.45).astype(np.uint8)]
        for quality in (50, 80):
            ok, data = cv2.imencode('.jpg', self.hero[:, :, ::-1],
                                   [cv2.IMWRITE_JPEG_QUALITY, quality])
            self.assertTrue(ok)
            variants.append(cv2.cvtColor(cv2.imdecode(data, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB))
        for index, image in enumerate(variants):
            with self.subTest(index=index):
                result = self.reader.read_region('hero_cards',image)
                self.assertEqual([c['card'] for c in result['cards']],['Th','6c'], result)

    def test_stricter_rank_threshold_is_respected(self):
        reader = CardRegionReader(self.reader.field_reader, 1.0, colored_deck=True)
        self.assertEqual(reader.read_region('hero_cards',self.hero)['status'],'PENDING')

    def test_solid_backgrounds_without_glyphs_never_become_cards(self):
        for color in [(180,30,30),(20,160,20),(20,80,180),(70,70,70)]:
            with self.subTest(color=color):
                image = np.zeros((140,100,3),np.uint8)
                image[5:135,5:95] = color
                self.assertEqual(self.reader.read_region('board_turn',image)['status'],'PENDING')

    def test_duplicate_physical_cards_are_rejected(self):
        result = self.reader.read_region('hero_cards',self.hero,occupied={'Th'})
        self.assertEqual(result['status'],'PENDING')
        self.assertIn('duplicadas',result['reason'])

    def test_cropped_cards_are_not_published(self):
        result = self.reader.read_region('board_flop',self.flop[25:])
        self.assertEqual(result['status'],'PENDING',result)

    def test_wrong_expected_count_is_rejected(self):
        result = self.reader.read_region('board_turn',self.flop)
        self.assertEqual(result['status'],'PENDING',result)

    def test_removed_suit_symbol_is_rejected(self):
        image = self.flop.copy()
        # First card: erase its small suit, preserve the rank and green background.
        image[49:80,3:34] = image[90,10]
        result = self.reader.read_region('board_flop',image)
        self.assertEqual(result['status'],'PENDING',result)

if __name__ == '__main__':
    unittest.main()
