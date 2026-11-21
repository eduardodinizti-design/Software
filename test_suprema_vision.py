"""TRAVA da integração de VISÃO da Suprema: detecções YOLO (mock) + OCR REAL dos stacks numa
captura -> table_state completo -> MESMO cérebro decide. Gated em tesseract+captura+pack."""
import os
import unittest

from vision_yolo.vision_state import Detection
from vision_yolo.classes import NAME_TO_ID
from vision_yolo.suprema_vision import read_table, advise_from_vision

_TESS = any(os.path.exists(p) for p in (
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Users\tacao\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'))
_CAP = r'C:\Meus Projetos\Aplicativos\_repo_software\research\suprema_cocos\raise_c_01.png'
_PACK = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
_DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'


def _box(cx, cy, w=0.07, h=0.05):
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


class MockDetector:
    """Simula o YOLO: hero AA + dealer(low_right) + botoes fold/call/raise."""
    def detect(self, image, conf=0.25):
        D = Detection
        return [
            D(NAME_TO_ID['As'], 0.9, _box(0.645, 0.805)),   # hero (bottom-center)
            D(NAME_TO_ID['Ad'], 0.9, _box(0.725, 0.805)),
            D(NAME_TO_ID['dealer_button'], 0.9, _box(0.80, 0.68, 0.04, 0.03)),  # -> low_right
            D(NAME_TO_ID['btn_fold'], 0.9, _box(0.185, 0.95, 0.2, 0.05)),
            D(NAME_TO_ID['btn_call'], 0.9, _box(0.500, 0.95, 0.2, 0.05)),
            D(NAME_TO_ID['btn_raise'], 0.9, _box(0.815, 0.95, 0.2, 0.05)),
        ]


@unittest.skipUnless(_TESS and os.path.exists(_CAP), 'tesseract ou captura ausente')
class SupremaVision(unittest.TestCase):

    def test_le_tabela_completa(self):
        state, hero = read_table(_CAP, MockDetector())
        self.assertIsNotNone(state, 'abstido: %r' % (hero,))
        self.assertEqual(hero, ['As', 'Ad'])                      # cartas (YOLO)
        self.assertEqual(state['positions']['hero'], 'SB')        # dealer=low_right -> hero=SB
        self.assertEqual(set(state['legal_actions']), {'fold', 'call', 'raise'})   # ações (YOLO)
        self.assertAlmostEqual(state['seats']['hero']['stack_bb'], 112.6, delta=1)  # stack (OCR)
        self.assertEqual(state['street'], 'PREFLOP')
        self.assertEqual(state['source'], 'vision')
        # outros assentos lidos pelo OCR
        self.assertGreaterEqual(len(state['positions']), 4)

    @unittest.skipUnless(os.path.exists(_PACK), 'pack ausente')
    def test_cerebro_decide_AA(self):
        from preflop_advisor import PreflopAdvisor
        adv = (PreflopAdvisor.from_files(_PACK, _DEEP) if os.path.exists(_DEEP)
               else PreflopAdvisor.from_file(_PACK))
        r = advise_from_vision(_CAP, MockDetector(), adv, mode='chip_ev', stage='mid')
        self.assertEqual(r.get('status'), 'ADVICE')
        self.assertIn(r.get('recommended'), ('raise', 'all_in', 'bets'))   # AA nunca folda


if __name__ == '__main__':
    unittest.main()
