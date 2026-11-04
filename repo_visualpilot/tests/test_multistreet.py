import unittest
from visualpilot.lab.multistreet import SearchConfig, sizes, solve_postflop
from visualpilot.lab.river_tree import solve_river

HERO=['As','Ad'];RIVER='2c 3d 7h 9s Jc'.split();WEIGHTS={('Ks','Kd'):1,('Js','Jd'):1}


def passive(combo,board,history,legal,context):
    action='check' if 'check' in legal else 'call'
    return {a:float(a==action) for a in legal}


class MultiStreetTests(unittest.TestCase):
    def test_river_matches_independent_previous_tree(self):
        config=SearchConfig(fractions=(.2,),include_all_in=False,chance_samples=0)
        new=solve_postflop(HERO,RIVER,WEIGHTS,10,20,passive,'test',config)
        old=solve_river(HERO,RIVER,WEIGHTS,10,20,[2],[6],lambda c,b,h,l:passive(c,b,h,l,{}),'test')
        self.assertEqual(new['comparisons'],old['decisions'][-1]['alternatives'])
        self.assertEqual(new['ev'],old['ev'])

    def test_future_betting_changes_turn_value(self):
        # Known royal flush: bet2 turn + bet2.8 river vs calling opponent adds4.8, not just2.
        config=SearchConfig(fractions=(.2,),include_all_in=False,chance_samples=0)
        result=solve_postflop(['Ah','Kh'],'Qh Jh Th 2c'.split(),{('Ks','Kd'):1},10,20,passive,'test',config)
        self.assertAlmostEqual(result['comparisons']['bet:2'],14.8)
        self.assertAlmostEqual(result['comparisons']['check'],12.)
        self.assertTrue(result['exact_under_model'])

    def test_flop_tracks_investment_across_three_streets(self):
        config=SearchConfig(fractions=(.2,),include_all_in=False,chance_samples=1)
        result=solve_postflop(['Ah','Kh'],'Qh Jh Th'.split(),{('Ks','Kd'):1},10,20,passive,'test',config)
        self.assertAlmostEqual(result['comparisons']['bet:2'],18.72)
        self.assertEqual(result['chosen'],'bet:2')
        self.assertEqual({len(d['board']) for d in result['decisions']},{3,4,5})
        self.assertTrue(all(d['stack']>=0 for d in result['decisions']))

    def test_allin_prevents_future_betting(self):
        result=solve_postflop(['Ah','Kh'],'Qh Jh Th'.split(),{('Ks','Kd'):1},10,2,passive,'test',
            SearchConfig(fractions=(1,),chance_samples=1,all_in_samples=20))
        self.assertAlmostEqual(result['comparisons']['bet:2'],12)
        self.assertTrue(all(d['stack']>0 for d in result['decisions']))

    def test_sizes_caps_dedup_and_budget_no_advice(self):
        self.assertEqual(sizes(10,3,SearchConfig()),([3],[3]))
        result=solve_postflop(HERO,RIVER,WEIGHTS,10,20,passive,'test',SearchConfig(max_nodes=1))
        self.assertEqual(result['status'],'pending');self.assertIsNone(result['chosen'])
        self.assertNotIn('comparisons',result)

    def test_ip_future_actor_order_and_current_checked_to(self):
        result=solve_postflop(['Ah','Kh'],'Qh Jh Th 2c'.split(),{('Ks','Kd'):1},10,20,passive,'test',
            SearchConfig(fractions=(.2,),include_all_in=False,chance_samples=1),hero_position='ip',opponent_checked=True)
        future=[d for d in result['decisions'] if len(d['board'])==5]
        self.assertTrue(future)
        self.assertTrue(all(d['history'][-1]=='villain:check' for d in future))
        with self.assertRaises(ValueError): solve_postflop(HERO,RIVER,WEIGHTS,10,20,passive,'test',hero_position='ip')

    def test_reproducible_and_invalid_models(self):
        config=SearchConfig(fractions=(.2,),include_all_in=False,chance_samples=2)
        args=(HERO,RIVER[:4],WEIGHTS,10,20,passive,'test',config)
        a=solve_postflop(*args);b=solve_postflop(*args)
        for key in ('comparisons','chance_trace','input_sha256','response_sha256'): self.assertEqual(a[key],b[key])
        with self.assertRaises(ValueError): solve_postflop(HERO,RIVER,WEIGHTS,10,20,lambda *args:{'check':.5},'bad')
        with self.assertRaises(ValueError): solve_postflop(HERO,RIVER,WEIGHTS,10,20,passive,'test',SearchConfig(chance_samples=-1))

    def test_seed_validation_and_budget_guard(self):
        from visualpilot.lab.multistreet import compare_seeds
        config=SearchConfig(fractions=(.2,),include_all_in=False,chance_samples=1)
        result=compare_seeds(['Ah','Kh'],'Qh Jh Th'.split(),{('Ks','Kd'):1},10,20,passive,'test',config)
        self.assertEqual(result['chosen'],'bet:2')
        self.assertEqual(result['status'],'experimental')
        result=compare_seeds(HERO,RIVER,WEIGHTS,10,20,passive,'test',SearchConfig(max_nodes=1))
        self.assertEqual(result['status'],'pending');self.assertIsNone(result['chosen'])
        with self.assertRaises(ValueError): compare_seeds(HERO,RIVER,WEIGHTS,10,20,passive,'test',seeds=(1,1,1))

    def test_size_sensitive_model_river_matches_prior_solver(self):
        from visualpilot.lab.opponent_models import size_sensitive_model
        model=size_sensitive_model(.6)
        config=SearchConfig(fractions=(.2,.5),include_all_in=True,chance_samples=0)
        bets,raises=sizes(10,20,config)
        def adapter(c,b,history,legal):
            h=tuple(('hero:' if i%2==0 else 'villain:')+a for i,a in enumerate(history))
            return model(c,b,h,legal,{'pot':10,'stack':20})
        new=solve_postflop(HERO,RIVER,WEIGHTS,10,20,model,'synthetic-test',config)
        old=solve_river(HERO,RIVER,WEIGHTS,10,20,bets,raises,adapter,'synthetic-test')
        self.assertEqual(new['comparisons'],old['decisions'][-1]['alternatives'])
        self.assertTrue(new['exact_under_model'])

    def test_facing_bet_pot_convention_and_future_street(self):
        config=SearchConfig(fractions=(.2,),include_all_in=False,chance_samples=0)
        result=solve_postflop(HERO,RIVER,WEIGHTS,12,20,passive,'test',config,facing_bet=2)
        self.assertEqual(result['comparisons']['fold'],0)
        self.assertEqual(result['comparisons']['call'],5)
        # Royal flush turn: call2 reaches pot14, then bet2.8 river. NetEV=14+2.8-2.
        result=solve_postflop(['Ah','Kh'],'Qh Jh Th 2c'.split(),{('Ks','Kd'):1},12,20,passive,'test',config,facing_bet=2)
        self.assertAlmostEqual(result['comparisons']['call'],14.8)
        self.assertTrue(any(a.startswith('raise:') for a in result['comparisons']))
        with self.assertRaises(ValueError): solve_postflop(HERO,RIVER,WEIGHTS,12,20,passive,'test',facing_bet=13)

    def test_ip_facing_bet_does_not_require_opponent_check(self):
        result=solve_postflop(HERO,RIVER,WEIGHTS,12,20,passive,'test',hero_position='ip',facing_bet=2)
        self.assertEqual(result['comparisons']['fold'],0)
        self.assertEqual(result['comparisons']['call'],5)
