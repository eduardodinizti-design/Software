from concurrent.futures import ThreadPoolExecutor
import threading
from time import monotonic
import unittest

from visualpilot.pppoker.scheduler import GenerationBatchConsolidator


def card_result(table, generation, region="hero_cards", cards=None):
    return {"table_key": table, "generation": generation, "region": region,
            "reading": {"status": "SUCCESS", "cards": cards or ["As", "Kd"]}}


class SchedulerTests(unittest.TestCase):
    def test_cards_publish_before_delayed_text_on_six_tables(self):
        scheduler = GenerationBatchConsolidator()
        release_text = threading.Event()
        for index in range(6):
            scheduler.register_capture(str(index), 1, ["hero_cards"], expect_text=True)

        def cards(index):
            return scheduler.inject_card_result(card_result(str(index), 1))

        def text(index):
            release_text.wait(2)
            return scheduler.inject_text_result(str(index), 1, {"pot": "10 BB"})

        with ThreadPoolExecutor(max_workers=12) as executor:
            card_futures = [executor.submit(cards, i) for i in range(6)]
            text_futures = [executor.submit(text, i) for i in range(6)]
            partial = [event for future in card_futures for event in future.result(timeout=1)]
            self.assertEqual(len(partial), 6)
            self.assertEqual({event["stage"] for event in partial}, {"PARTIAL_CARDS"})
            self.assertTrue(all(not future.done() for future in text_futures))
            release_text.set()
            consolidated = [event for future in text_futures for event in future.result(timeout=1)]
        self.assertEqual(len(consolidated), 6)
        self.assertEqual({event["stage"] for event in consolidated}, {"CONSOLIDATED"})
        self.assertEqual(scheduler.metrics["partial"], 6)
        self.assertEqual(scheduler.metrics["consolidated"], 6)

    def test_new_generation_rejects_late_old_results(self):
        scheduler = GenerationBatchConsolidator()
        scheduler.register_capture("a", 4, ["hero_cards"])
        scheduler.register_capture("a", 5, ["hero_cards"])
        self.assertEqual(scheduler.inject_card_result(card_result("a", 4)), [])
        events = scheduler.inject_card_result(card_result("a", 5))
        self.assertEqual(events[0]["generation"], 5)
        self.assertEqual(scheduler.metrics["stale_results"], 1)

    def test_waits_for_every_scheduled_card_region(self):
        scheduler = GenerationBatchConsolidator()
        scheduler.register_capture("a", 1, ["hero_cards", "board_flop"])
        self.assertEqual(scheduler.inject_card_result(card_result("a", 1)), [])
        events = scheduler.inject_card_result(card_result("a", 1, "board_flop",
                                                           ["2s", "3h", "4d"]))
        self.assertEqual([event["stage"] for event in events], ["PARTIAL_CARDS"])

    def test_text_first_emits_partial_then_consolidated_when_cards_finish(self):
        scheduler = GenerationBatchConsolidator()
        scheduler.register_capture("a", 1, ["hero_cards"])
        self.assertEqual(scheduler.inject_text_result("a", 1, {"pot": "3 BB"}), [])
        events = scheduler.inject_card_result(card_result("a", 1))
        self.assertEqual([event["stage"] for event in events],
                         ["PARTIAL_CARDS", "CONSOLIDATED"])

    def test_duplicate_results_do_not_publish_twice(self):
        scheduler = GenerationBatchConsolidator()
        scheduler.register_capture("a", 1, ["hero_cards"])
        result = card_result("a", 1)
        self.assertTrue(scheduler.inject_card_result(result))
        self.assertEqual(scheduler.inject_card_result(result), [])

    def test_expiration_and_table_removal_are_bounded(self):
        now = [0.0]
        scheduler = GenerationBatchConsolidator(20, clock=lambda: now[0])
        scheduler.register_capture("a", 1, ["hero_cards"])
        now[0] = 21
        self.assertEqual(scheduler.cleanup_stale_generations(), [("a", 1)])
        scheduler.register_capture("b", 1, ["hero_cards"])
        scheduler.remove_table("b")
        self.assertEqual(scheduler.inject_card_result(card_result("b", 1)), [])

    def test_invalid_or_non_monotonic_generation_is_rejected(self):
        scheduler = GenerationBatchConsolidator()
        scheduler.register_capture("a", 2, ["hero_cards"])
        with self.assertRaises(ValueError):
            scheduler.register_capture("a", 2, ["hero_cards"])
        with self.assertRaises(ValueError):
            scheduler.register_capture("a", 1, ["hero_cards"])


if __name__ == "__main__":
    unittest.main()
