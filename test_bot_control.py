"""Pause/takeover control plane: state machine + hotkey edge detection."""
import unittest

from bot_control import (BotControl, HotkeyListener, RUNNING, PAUSED, DISABLED,
                         DEFAULT_BINDINGS)


class ControlTests(unittest.TestCase):
    def test_default_is_paused_and_blocks_execution(self):
        c = BotControl()
        self.assertEqual(c.state, PAUSED)
        self.assertFalse(c.execution_allowed())   # safe default: never operating unarmed

    def test_resume_arms_and_allows_execution(self):
        c = BotControl()
        c.resume()
        self.assertEqual(c.state, RUNNING)
        self.assertTrue(c.execution_allowed())

    def test_pause_blocks_execution(self):
        c = BotControl()
        c.resume()
        c.pause()
        self.assertEqual(c.state, PAUSED)
        self.assertFalse(c.execution_allowed())

    def test_disable_is_sticky_until_resume(self):
        c = BotControl()
        c.resume()
        c.disable()
        self.assertEqual(c.state, DISABLED)
        self.assertFalse(c.pause())               # pause is a no-op from DISABLED
        self.assertEqual(c.state, DISABLED)
        self.assertFalse(c.execution_allowed())
        c.resume()                                # only resume reactivates
        self.assertEqual(c.state, RUNNING)

    def test_on_change_callback_fires_on_transition_only(self):
        seen = []
        c = BotControl(on_change=seen.append)
        c.resume()
        c.resume()                                # no transition -> no callback
        c.pause()
        self.assertEqual(seen, [RUNNING, PAUSED])


class FakeKeys:
    def __init__(self):
        self.down = set()

    def __call__(self, vk):
        return vk in self.down


class HotkeyTests(unittest.TestCase):
    def setUp(self):
        self.keys = FakeKeys()
        self.control = BotControl()
        self.listener = HotkeyListener(self.control, key_down=self.keys)

    def _press(self, action):
        self.keys.down = set(DEFAULT_BINDINGS[action])

    def test_pause_combo_fires_once_per_press(self):
        self.control.resume()
        self._press('pause')
        self.assertEqual(self.listener.poll_once(), ['pause'])
        self.assertEqual(self.control.state, PAUSED)
        # held down: no repeat
        self.assertEqual(self.listener.poll_once(), [])
        # release and press again
        self.keys.down = set()
        self.listener.poll_once()
        self.control.resume()
        self._press('pause')
        self.assertEqual(self.listener.poll_once(), ['pause'])

    def test_resume_and_disable_combos(self):
        self._press('disable')
        self.listener.poll_once()
        self.assertEqual(self.control.state, DISABLED)
        self.keys.down = set()
        self.listener.poll_once()
        self._press('resume')
        self.listener.poll_once()
        self.assertEqual(self.control.state, RUNNING)

    def test_partial_combo_does_not_fire(self):
        self.control.resume()
        self.keys.down = {DEFAULT_BINDINGS['pause'][0]}   # only Ctrl
        self.assertEqual(self.listener.poll_once(), [])
        self.assertEqual(self.control.state, RUNNING)


if __name__ == '__main__':
    unittest.main()
