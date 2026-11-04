import unittest
from visualpilot.agent.nvt_ranges import NvtRangeBook
from visualpilot.lab.scenario_matrix import make_case,BOARDS,CONTEXTS
from visualpilot.lab.multistreet import SearchConfig,solve_postflop


class ScenarioMatrixTests(unittest.TestCase):
    def setUp(self):self.book=NvtRangeBook('tests/fixtures/nvt_position_excerpt.json')

    def test_all_cases_have_real_arrival_and_no_blocked_combos(self):
        for context in CONTEXTS:
            for texture in BOARDS:
                for street in ('flop','turn'):
                    case=make_case(self.book,context,texture,street)
                    self.assertGreater(case['provenance']['hero_arrival_frequency'],0)
                    self.assertTrue(case['range'])
                    dead=set(case['hero']+case['board'])
                    self.assertTrue(all(not set(c)&dead for c in case['range']))
                    self.assertEqual(case['opponent_checked'],case['hero_position']=='ip')

    def test_opponent_range_is_not_accidentally_hero_range(self):
        bb=make_case(self.book,'BB_vs_BTN','paired')
        btn=make_case(self.book,'BTN_vs_BB','paired')
        self.assertEqual(bb['provenance']['opponent']['action'],'raise')
        self.assertEqual(btn['provenance']['opponent']['action'],'call')
        self.assertEqual(btn['provenance']['opponent']['node_id'],'chip_ev|mid|25|vs_open|BB|BTN|-')
        self.assertNotEqual(bb['range'],btn['range'])

    def test_first_actor_on_future_street_matches_position(self):
        def passive(c,b,h,legal,ctx):return {a:float(a==('check' if 'check' in legal else 'call')) for a in legal}
        for ctx in ('BB_vs_BTN','BTN_vs_BB','BB_vs_SB','SB_vs_BB'):
            case=make_case(self.book,ctx,'paired')
            combo=next(iter(case['range']))
            r=solve_postflop(case['hero'],case['board'],{combo:1},10,16,passive,'test',
                SearchConfig(chance_samples=1,fractions=(.5,),include_all_in=False),
                hero_position=case['hero_position'],opponent_checked=case['opponent_checked'])
            first=[d for d in r['decisions'] if len(d['board'])==5 and 'board:' in d['history'][-1 if case['hero_position']=='oop' else -2]]
            self.assertTrue(first)
            if case['hero_position']=='ip':self.assertTrue(all(d['history'][-1]=='villain:check' for d in first))

    def test_observed_check_updates_ip_range_and_not_original(self):
        from visualpilot.lab.scenario_matrix import condition_on_check
        case=make_case(self.book,'BTN_vs_BB','paired')
        combos=list(case['range']);original=dict(case['range'])
        def model(c,b,h,legal,ctx):
            check=1. if c==combos[0] else 0.
            return {a:(check if a=='check' else (1-check)/(len(legal)-1)) for a in legal}
        updated=condition_on_check(case,model,SearchConfig())
        self.assertEqual(updated['range'],{combos[0]:1.})
        self.assertEqual(case['range'],original)
        self.assertGreater(updated['provenance']['observed_check_probability_under_model'],0)
