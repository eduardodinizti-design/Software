from pathlib import Path
import unittest
from visualpilot.agent.nvt_ranges import NvtRangeBook,nearest_spread,POSITIONS
from visualpilot.agent.strategy import RangeCoachStrategy

class NvtPreflopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.book=NvtRangeBook(Path(__file__).parent/'fixtures/nvt_range_excerpt.json')
    def state(self):return dict(hero=['As','Ks'],board=[],street='preflop')
    def context(self):return dict(mode='chip_ev',stack=25,players=9,position='BB',spot='vs_open',vs=['BTN'])
    def test_actual_export_AKs_is_three_bet_and_no_sizing_invented(self):
        result=RangeCoachStrategy(None,nvt_ranges=self.book).theoretical_action(self.state(),self.context())
        self.assertEqual(result['mix'],[dict(action='three_bet',frequency=1)])
        self.assertEqual(result['ev']['three_bet'],5.7936)
        self.assertEqual(result['sizing_status'],'not_exported')
        self.assertEqual(result['provenance']['engine_commit'],'ea758d9')
    def test_no_postflop_missing_position_or_approximate_stack(self):
        for reading,context in [(dict(self.state(),street='flop',board=['2h','3h','4h']),self.context()),
            (self.state(),dict(self.context(),position=None)),(self.state(),dict(self.context(),stack=26))]:
            self.assertEqual(self.book.recommend(reading,context)['status'],'pending')
    def test_documented_zero_ev_is_unknown_not_an_acceptable_shove(self):
        context=dict(mode='icm',stack=8,stage='pre_itm',players=9,position='UTG+2',spot='open_shove',vs=[],spread='iguais')
        reading=dict(hero=['Ah','5d'],board=[],street='preflop')
        result=self.book.recommend(reading,context)
        self.assertEqual(result['mix'],[dict(action='fold',frequency=1)])
        self.assertEqual(result['raw_ev']['all_in'],0)
        self.assertIsNone(result['ev']['all_in'])
        grade=self.book.grade(reading,context,'all_in')
        self.assertFalse(grade['correct']);self.assertIsNone(grade['ev_loss'])
        self.assertEqual(self.book.recommend(reading,dict(context,stage=None))['status'],'pending')
    def test_spread_requires_complete_stacks(self):
        self.assertEqual(nearest_spread(dict.fromkeys(POSITIONS,25)),'iguais')
        with self.assertRaises(ValueError):nearest_spread({'BTN':25})
