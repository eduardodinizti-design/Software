import unittest
from dataclasses import replace
from visualpilot.lab.pko import PKOContext
from visualpilot.lab.multistreet import solve_postflop, SearchConfig


def passive(c,b,h,legal,ctx):
    selected='check' if 'check' in legal else 'call'
    return {a:float(a==selected) for a in legal}


class PKOLabTests(unittest.TestCase):
    def context(self,hero=20,villain=10):
        return PKOContext(hero,villain,8,20,.5,2,'synthetic-fixed-rate','LAB')

    def test_coverage_cash_and_progressive_are_distinct(self):
        ctx=self.context();ctx.validate(10)
        reward=ctx.reward(.25,True)
        self.assertEqual(reward['expected_cash'],2.5)
        self.assertEqual(reward['expected_bb'],5)
        self.assertEqual(reward['progressive_added_on_win'],10)
        self.assertIsNone(reward['future_progressive_ev'])
        self.assertEqual(ctx.reward(1,False)['expected_bb'],0)
        self.assertEqual(self.context(10,20).reward(1,True)['expected_bb'],0)
        self.assertTrue(self.context(10,10).hero_covers)

    def test_no_bounty_for_fold_tie_or_non_allin(self):
        ctx=self.context()
        hero=['2d','3d'];board='Tc Jc Qc Kc Ac'.split();weights={('4h','5h'):1}
        result=solve_postflop(hero,board,weights,10,10,passive,'test',pko=ctx)
        self.assertTrue(all(abs(v-5)<1e-9 for v in result['comparisons'].values()))
        result=solve_postflop(['As','Ad'],'2c 3d 7h 9s Jc'.split(),{('Ks','Kd'):1},10,10,passive,'test',pko=ctx)
        self.assertEqual(result['comparisons']['bet:10'],40) # pot10 + villain10 + cash equivalent20
        self.assertAlmostEqual(result['comparisons']['bet:3.33'],13.33)
        def folds(c,b,h,legal,ctx): return {a:float(a==('check' if 'check' in legal else 'fold')) for a in legal}
        result=solve_postflop(['As','Ad'],'2c 3d 7h 9s Jc'.split(),{('Ks','Kd'):1},10,10,folds,'test',pko=ctx)
        self.assertEqual(result['comparisons']['bet:10'],10)

    def test_coverage_changes_marginal_call(self):
        # Equity1/4: pot15 facing10 -> chip EV -3.75; converted bounty20 yields +1.25.
        args=(['As','Ad'],'2c 3d 7h 9s Jc'.split(),{('Ks','Kd'):1,('Js','Jd'):3},15,10,passive,'test')
        plain=solve_postflop(*args,facing_bet=10)
        covered=solve_postflop(*args,facing_bet=10,pko=self.context())
        uncovered=solve_postflop(*args,facing_bet=10,pko=self.context(10,20))
        self.assertEqual(plain['chosen'],'fold');self.assertEqual(plain['comparisons']['call'],-3.75)
        self.assertEqual(covered['chosen'],'call');self.assertEqual(covered['comparisons']['call'],1.25)
        self.assertEqual(uncovered['chosen'],'fold')

    def test_allin_on_flop_receives_bounty_once(self):
        result=solve_postflop(['Ah','Kh'],'Qh Jh Th'.split(),{('Ks','Kd'):1},10,10,passive,'test',
            SearchConfig(chance_samples=1,all_in_samples=20),pko=self.context())
        self.assertEqual(result['comparisons']['bet:10'],40)

    def test_missing_conversion_or_inconsistent_coverage_rejected(self):
        for ctx in (replace(self.context(),bb_per_currency=0),replace(self.context(),cash_fraction=2),
                    replace(self.context(),conversion_source=''),self.context(20,20)):
            with self.assertRaises(ValueError): ctx.validate(10)

    def test_nvt_does_not_ignore_live_bounty_context(self):
        from visualpilot.agent.nvt_ranges import NvtRangeBook
        book=NvtRangeBook('tests/fixtures/nvt_range_excerpt.json')
        result=book.recommend({'street':'preflop','hero':['As','Kd'],'board':[]},
            {'mode':'pko_icm','stack':25,'players':9,'bounties':{'BTN':324}})
        self.assertEqual(result['status'],'pending')
        self.assertIn('bounty power',result['reason'])
