import json
from pathlib import Path
import unittest

import numpy as np
from PIL import Image

from visualpilot.pppoker.card_reader import CardRegionReader
from visualpilot.pppoker.dataset_generator import MISSING_CARDS, REAL_OBSERVED
from visualpilot.pppoker.observer.perception import CachedReader
from visualpilot.pppoker.replay.reader import ReplayReader
from visualpilot.pppoker.roi_engine import REGIONS


FOLDER = Path(__file__).parent / "fixtures" / "synthetic_deck"


class SyntheticDeckMetadataTests(unittest.TestCase):
    def test_manifest_covers_exactly_the_36_missing_combinations(self):
        manifest = json.loads((FOLDER / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(set(manifest["generated"]), set(MISSING_CARDS))
        self.assertEqual(len(MISSING_CARDS), 36)
        self.assertEqual(len(REAL_OBSERVED | set(MISSING_CARDS)), 52)
        self.assertEqual(manifest["scope"], "synthetic_regression_only")

    def test_six_and_nine_are_explicitly_marked_as_font_synthetic(self):
        manifest = json.loads((FOLDER / "manifest.json").read_text(encoding="utf-8"))
        for card, data in manifest["generated"].items():
            if card[0] in "69":
                self.assertEqual(data["rank_origin"], "synthetic_font")


class SyntheticCardReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = CardRegionReader(CachedReader(ReplayReader()))


def _card_test(card):
    def test(self):
        image = np.array(Image.open(FOLDER / f"{card}.png").convert("RGB"))
        y1, x1, y2, x2 = REGIONS["board_turn"][0]
        result = self.reader.read_region("board_turn", image[y1:y2, x1:x2])
        self.assertEqual(result["status"], "SUCCESS", result)
        self.assertEqual(result["cards"][0]["card"], card)
        self.assertGreaterEqual(result["cards"][0]["confidence"], .90)
    return test


for _card in MISSING_CARDS:
    setattr(SyntheticCardReadingTests, f"test_reads_{_card}", _card_test(_card))
