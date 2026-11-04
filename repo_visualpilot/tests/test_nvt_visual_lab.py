from collections import Counter
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from visualpilot.lab.nvt_engine import NvtVisualLaboratory,choose_mix,CASES
from visualpilot.lab.server import LaboratorySession

class NvtVisualLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=NvtVisualLaboratory(Path(__file__).parent/'fixtures/nvt_range_excerpt.json')

    def test_real_ocr_queries_nvt_for_all_five_preflop_scenarios(self):
        for index in range(5):
            with self.subTest(index=index):
                event,_=self.engine.run(index)
                self.assertEqual(event['reading']['hero'],CASES[index][1])
                self.assertEqual(event['reading']['board'],[])
                self.assertEqual(event['range_decision']['status'],'found')
                self.assertEqual(event['state']['players'],9)
                self.assertEqual(event['range_decision']['provenance']['engine_commit'],'ea758d9')
                self.assertEqual(event['execution']['status'],'blocked' if index==3 else 'applied')
                if index==3:
                    self.assertEqual(event['range_decision']['mix'],[dict(action='raise',frequency=1)])
                    self.assertIn('sizing',event['decision']['reason'])
                if index==1:self.assertEqual(event['execution']['sizing_bb'],1.)

    def test_hidden_cards_cannot_choose_from_reference_hero(self):
        event,_=self.engine.run(1,True)
        self.assertEqual(event['reading']['hero'],[])
        self.assertEqual(event['range_decision']['status'],'pending')
        self.assertEqual(event['execution']['status'],'blocked')

    def test_manual_grade_is_not_an_unsized_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            session=LaboratorySession(folder,self.engine);session.control('manual')
            event=session.observe(3,False)
            grade=session.answer(event['token'],'raise')
            self.assertTrue(grade['grade']['correct'])
            self.assertFalse(grade['executed'])
            self.assertEqual(session.apply(event['token'],'human','raise')['status'],'blocked')
            session.control('paused')
            self.assertEqual(session.answer(event['token'],'raise')['status'],'blocked')

    def test_weighted_selection_is_reproducible_without_mutating_mix(self):
        result=dict(status='found',mix=[dict(action='fold',frequency=.5),dict(action='call',frequency=.5)])
        before=deepcopy(result)
        counts=Counter(choose_mix(result,str(i))['action'] for i in range(1000))
        self.assertGreater(counts['call'],400);self.assertLess(counts['call'],600)
        self.assertEqual(choose_mix(result,'fixed'),choose_mix(result,'fixed'))
        self.assertEqual(result,before)
        self.assertIsNone(choose_mix(dict(status='pending'),'fixed'))
