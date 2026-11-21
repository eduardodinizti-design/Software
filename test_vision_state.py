"""TRAVA do adaptador de VISÃO (F0, offline): detecções YOLO (mock) -> table_state genérico,
clusterização multi-mesa, e decisão pelo MESMO cérebro. Sem modelo treinado, sem tela —
prova a INTERFACE detecção->cérebro."""
import os
import unittest

import vision_classes as VC
from vision_state import (Detection, extract_cards, legal_from_buttons, cluster_tables,
                          build_table_state, advise_from_vision)

PACK = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'


def D(cls, cx, cy, conf=0.9):
    return Detection(cls, conf, cx, cy, 0.05, 0.08)


class Classes(unittest.TestCase):
    def test_52_cartas(self):
        self.assertEqual(len(VC.CARD_CLASSES), 52)
        self.assertIn('Ad', VC.CARD_CLASSES)
        self.assertTrue(VC.is_card('Kc'))
        self.assertFalse(VC.is_card('btn_fold'))

    def test_class_count_bate(self):
        self.assertEqual(VC.class_count(), len(VC.ALL_CLASSES))


class Extracao(unittest.TestCase):
    def test_hero_vs_board_por_regiao(self):
        dets = [D('Ad', 0.45, 0.85), D('Ac', 0.52, 0.85),          # herói (rodapé central)
                D('9d', 0.40, 0.45), D('7h', 0.50, 0.45), D('2c', 0.60, 0.45)]  # board (centro)
        hero, board = extract_cards(dets)
        self.assertEqual(hero, ['Ad', 'Ac'])                       # ordenado por cx
        self.assertEqual(board, ['9d', '7h', '2c'])

    def test_legal_dos_botoes(self):
        dets = [D('btn_fold', 0.18, 0.95), D('btn_call', 0.50, 0.95),
                D('btn_raise', 0.82, 0.95), D('btn_confirm', 0.82, 0.95)]
        self.assertEqual(legal_from_buttons(dets), {'fold', 'call', 'raise'})   # confirm NÃO entra

    def test_cluster_multimesa(self):
        # 2 mesas tiladas lado a lado (coluna esquerda ~0.2, direita ~0.75)
        dets = [D('Ad', 0.20, 0.85), D('Ac', 0.25, 0.85),
                D('Kd', 0.72, 0.85), D('Kc', 0.78, 0.85)]
        groups = cluster_tables(dets, gap=0.1)
        self.assertEqual(len(groups), 2)
        self.assertEqual(sorted(d.cls for d in groups[0]), ['Ac', 'Ad'])
        self.assertEqual(sorted(d.cls for d in groups[1]), ['Kc', 'Kd'])


class BuildState(unittest.TestCase):
    def _dets(self):
        return [D('Ad', 0.45, 0.85), D('Ac', 0.52, 0.85),          # herói AA
                D('btn_fold', 0.18, 0.95), D('btn_call', 0.50, 0.95), D('btn_raise', 0.82, 0.95)]

    def _seats(self):
        return [dict(key='hero', pos='BTN', stack_bb=20, bet_bb=0),
                dict(key='seat1', pos='SB', stack_bb=18, bet_bb=0.5),
                dict(key='seat2', pos='BB', stack_bb=18, bet_bb=1.0)]

    def test_estado_preflop(self):
        state, hero = build_table_state(self._dets(), seats=self._seats())
        self.assertIsNotNone(state)
        self.assertEqual(hero, ['Ad', 'Ac'])
        self.assertEqual(state['positions']['hero'], 'BTN')
        self.assertEqual(state['street'], 'PREFLOP')
        self.assertAlmostEqual(state['to_call']['to_call_bb'], 1.0)   # BB 1.0 - hero 0
        self.assertEqual(set(state['legal_actions']), {'fold', 'call', 'raise'})
        self.assertEqual(state['source'], 'vision')

    def test_abstem_sem_heroi(self):
        dets = [D('btn_fold', 0.18, 0.95)]                          # sem 2 cartas do herói
        state, reason = build_table_state(dets, seats=self._seats())
        self.assertIsNone(state)
        self.assertEqual(reason, 'HERO_CARDS_UNKNOWN')

    def test_abstem_sem_assentos(self):
        state, reason = build_table_state(self._dets(), seats=[])
        self.assertIsNone(state)
        self.assertEqual(reason, 'SEM_ASSENTOS')

    @unittest.skipUnless(os.path.exists(PACK), 'pack ausente')
    def test_cerebro_decide_AA(self):
        from preflop_advisor import PreflopAdvisor
        adv = (PreflopAdvisor.from_files(PACK, DEEP) if os.path.exists(DEEP)
               else PreflopAdvisor.from_file(PACK))
        r = advise_from_vision(self._dets(), self._seats(), adv, mode='chip_ev', stage='mid')
        self.assertEqual(r.get('status'), 'ADVICE')
        self.assertIn(r.get('recommended'), ('raise', 'all_in', 'bets'))   # AA nunca folda


if __name__ == '__main__':
    unittest.main()
