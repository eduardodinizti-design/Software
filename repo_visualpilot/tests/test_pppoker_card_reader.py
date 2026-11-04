from pathlib import Path
import unittest
import threading

import numpy as np
from PIL import Image

from visualpilot.pppoker.card_reader import CardRegionReader
from visualpilot.pppoker.replay.reader import ReplayReader
from visualpilot.pppoker.observer.perception import CachedReader
from visualpilot.pppoker.roi_engine import REGIONS
from visualpilot.pppoker.replay.service import OCRService


ROOT = Path(__file__).parent / "fixtures" / "actions"


def crop(image, region):
    ymin, xmin, ymax, xmax = REGIONS[region][0]
    return image[ymin:ymax, xmin:xmax]


class CardReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = CardRegionReader(CachedReader(ReplayReader()))
        cls.left = np.array(Image.open(ROOT / "left_99.png").convert("RGB"))
        cls.right = np.array(Image.open(ROOT / "right_99.png").convert("RGB"))

    def test_reads_real_hero_cards_independently(self):
        left = self.reader.read_region("hero_cards", crop(self.left, "hero_cards"))
        right = self.reader.read_region("hero_cards", crop(self.right, "hero_cards"))
        self.assertEqual(left["status"], "SUCCESS", left)
        self.assertEqual(right["status"], "SUCCESS", right)
        self.assertEqual([x["card"] for x in left["cards"]], ["Th", "4d"])
        self.assertEqual([x["card"] for x in right["cards"]], ["5c", "2s"])

    def test_reads_real_flop_without_full_table_ocr(self):
        result = self.reader.read_region("board_flop", crop(self.left, "board_flop"))
        self.assertEqual(result["status"], "SUCCESS", result)
        self.assertEqual([x["card"] for x in result["cards"]], ["7h", "As", "Ts"])

    def test_empty_board_remains_pending(self):
        result = self.reader.read_region("board_flop", crop(self.right, "board_flop"))
        self.assertEqual(result["status"], "PENDING")
        self.assertEqual(result["cards"], [])

    def test_duplicate_against_other_region_is_rejected(self):
        result = self.reader.read_region("hero_cards", crop(self.left, "hero_cards"),
                                         occupied={"Th"})
        self.assertEqual(result["status"], "PENDING")
        self.assertIn("duplicadas", result["reason"])

    def test_invalid_or_unknown_region_is_pending(self):
        invalid = self.reader.read_region("hero_cards", np.array([]))
        unknown = self.reader.read_region("names", crop(self.left, "hero_cards"))
        self.assertEqual(invalid["status"], "PENDING")
        self.assertEqual(unknown["status"], "PENDING")

    def test_process_protocol_preserves_table_generation_and_region(self):
        service = OCRService(timeout=20)
        stop = threading.Event()
        try:
            result = service.read_cards("table-3", 17, "board_flop",
                                        crop(self.left, "board_flop"), stop)
        finally:
            service.close()
        self.assertEqual(result["table_key"], "table-3")
        self.assertEqual(result["generation"], 17)
        self.assertEqual(result["region"], "board_flop")
        self.assertEqual(result["reading"]["status"], "SUCCESS")
        self.assertEqual([item["card"] for item in result["reading"]["cards"]],
                         ["7h", "As", "Ts"])

    def test_process_protocol_validates_identity_before_queueing(self):
        service = OCRService(timeout=2)
        stop = threading.Event()
        try:
            with self.assertRaises(ValueError):
                service.read_cards("", 0, "hero_cards", crop(self.left, "hero_cards"), stop)
            with self.assertRaises(ValueError):
                service.read_cards("table", -1, "hero_cards", crop(self.left, "hero_cards"), stop)
        finally:
            service.close()


if __name__ == "__main__":
    unittest.main()
