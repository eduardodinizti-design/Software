"""Adaptador de teclado (SendInput Unicode). Backend fake registra os eventos;
não toca no Windows. Verifica down+up por char, teclas especiais e limpeza."""
import unittest

from keyboard_input_win import (WindowsKeyboardInput, KEYEVENTF_UNICODE,
                                KEYEVENTF_KEYUP, VK)


class _FakeBackend:
    def __init__(self):
        self.events = []

    def send(self, events):
        self.events.extend(events)
        return len(events)


def _kb(fake):
    return WindowsKeyboardInput(sleep=lambda _s: None, key_s=0, _backend=fake)


class TypeTextTests(unittest.TestCase):
    def test_digita_down_e_up_por_char(self):
        fb = _FakeBackend()
        r = _kb(fb).type_text('Ab')
        self.assertEqual(r, dict(requested=4, accepted=4))
        # A: down (unicode) + up (unicode|keyup), depois b
        self.assertEqual(fb.events, [
            (0, ord('A'), KEYEVENTF_UNICODE), (0, ord('A'), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP),
            (0, ord('b'), KEYEVENTF_UNICODE), (0, ord('b'), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)])

    def test_unicode_acentos(self):
        fb = _FakeBackend()
        _kb(fb).type_text('ç')
        self.assertEqual(fb.events[0], (0, ord('ç'), KEYEVENTF_UNICODE))

    def test_texto_vazio_nao_envia(self):
        fb = _FakeBackend()
        self.assertEqual(_kb(fb).type_text('')['accepted'], 0)
        self.assertEqual(fb.events, [])


class SpecialKeyTests(unittest.TestCase):
    def test_enter(self):
        fb = _FakeBackend()
        _kb(fb).press_key('enter')
        self.assertEqual(fb.events, [(VK['ENTER'], 0, 0), (VK['ENTER'], 0, KEYEVENTF_KEYUP)])

    def test_tecla_desconhecida_levanta(self):
        with self.assertRaises(ValueError):
            _kb(_FakeBackend()).press_key('F13')

    def test_clear_field_backspaces(self):
        fb = _FakeBackend()
        r = _kb(fb).clear_field(3)
        self.assertEqual(r['accepted'], 6)                 # 3 x (down+up)
        self.assertTrue(all(e[0] == VK['BACKSPACE'] for e in fb.events))


if __name__ == '__main__':
    unittest.main()
