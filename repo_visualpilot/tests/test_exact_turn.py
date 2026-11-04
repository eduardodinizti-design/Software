import unittest
from dataclasses import replace
from itertools import combinations
from visualpilot.lab.multistreet import solve_postflop, SearchConfig
from visualpilot.lab.postflop import DECK, rank7
from visualpilot.lab.pko import PKOContext


def passive(c,b,h,legal,ctx):
    return {a:float(a==('check' if 'check' in legal else 'call')) for a in legal}


class ExactTurnTests(unittest.TestCase):
    def test_allin_matches_independent_enumeration_with_bounty_and_ties(self):
        hero=('Ah','Jh');board=('Kh','8h','2c','3d');weights={('Ks','Kd'):3,('Ac','Jc'):1}
        win=tie=0.
        for combo,weight in weights.items():
            deck=[c for c in DECK if c not in hero+board+combo]
            for card in deck:
                h=rank7(hero+board+(card,));v=rank7(combo+board+(card,))
                win+=weight/4/44*(h>v);tie+=weight/4/44*(h==v)
        cfg=SearchConfig(fractions=(1,),exact_turn=True)
        ctx=PKOContext(20,10,8,20,.5,2,'test-fixed-conversion')
        result=solve_postflop(hero,board,weights,10,10,passive,'test',cfg,pko=ctx)
        self.assertAlmostEqual(result['comparisons']['bet:10'],(win+.5*tie)*30-10+win*20)
        self.assertTrue(result['exact_under_model'])
        self.assertFalse(result['requires_independent_seed_validation'])

    def test_seed_independence_on_turn(self):
        cfg=SearchConfig(fractions=(.5,),exact_turn=True)
        args=(['Ah','Jh'],['Kh','8h','2c','3d'],{('Ks','Kd'):1,('Ac','Jc'):1},10,10,passive,'test')
        first=solve_postflop(*args,cfg)
        second=solve_postflop(*args,replace(cfg,seed=917))
        self.assertEqual(first['comparisons'],second['comparisons'])
        self.assertEqual(first['chance_trace'],second['chance_trace'])
        self.assertTrue(first['exact_under_model'])

    def test_flop_still_declares_sampling(self):
        result=solve_postflop(['Ah','Kh'],['Qh','Jh','Th'],{('Ks','Kd'):1},10,2,passive,'test',
            SearchConfig(fractions=(1,),chance_samples=1,all_in_samples=20,exact_turn=True))
        self.assertFalse(result['exact_under_model'])
        self.assertTrue(result['requires_independent_seed_validation'])
        turns=[e for e in result['chance_trace'] if len(e['board'])==4]
        self.assertTrue(turns)
        self.assertTrue(all(len(e['branches'])==44 for e in turns))

    def test_invalid_exact_flag_and_budget(self):
        with self.assertRaises(ValueError): SearchConfig(exact_turn=1).validate()
        result=solve_postflop(['Ah','Jh'],['Kh','8h','2c','3d'],{('Ks','Kd'):1},10,10,passive,'test',
            SearchConfig(exact_turn=True,max_nodes=1))
        self.assertEqual(result['status'],'pending');self.assertIsNone(result['chosen'])
