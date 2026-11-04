import time
import unittest
from visualpilot.pppoker.stream_control import AdaptiveFpsThrottler

class TestAdaptiveFpsThrottler(unittest.TestCase):
    def test_adaptive_fps_throttling(self):
        # idle_fps = 10 (interval = 0.1s), active_fps = 30 (interval = 0.0333s)
        throttler = AdaptiveFpsThrottler(idle_fps=10, active_fps=30)

        # Primeira captura deve ser permitida imediatamente (is_hero_turn=False)
        self.assertTrue(throttler.should_capture("tbl-1", is_hero_turn=False))
        # Captura imediata subsequente deve ser bloqueada (< 0.1s)
        self.assertFalse(throttler.should_capture("tbl-1", is_hero_turn=False))

        # Mudar para turno do Hero (active_fps = 30 -> interval ~0.033s)
        time.sleep(0.04)
        self.assertTrue(throttler.should_capture("tbl-1", is_hero_turn=True))

if __name__ == "__main__":
    unittest.main()
