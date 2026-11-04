import random
import unittest
from collections import Counter
from dataclasses import replace
from visualpilot.lab.chance_sampling import sample_indices
from visualpilot.lab.multistreet import SearchConfig, solve_postflop


class ChanceSamplingTests(unittest.TestCase):
    def test_equal_strata_cover_uniform_distribution(self):
        for seed in range(50):
            self.assertEqual(sample_indices([1,1,1,1],4,random.Random(seed),'stratified'),[0,1,2,3])

    def test_weighted_probability_and_zero_mass(self):
        counts=Counter()
        for seed in range(1000):
            counts.update(sample_indices([.2,0,.3,.5],3,random.Random(seed),'stratified'))
        self.assertEqual(counts[1],0)
        class MaxRandom:
            def random(self): return 1-2**-53
        self.assertEqual(sample_indices([1,0],6,MaxRandom(),'stratified'),[0]*6)
        for i,p in ((0,.2),(2,.3),(3,.5)): self.assertAlmostEqual(counts[i]/3000,p,delta=.025)

    def test_default_matches_legacy_choices(self):
        weights=[1,2,3,0,9]
        self.assertEqual(sample_indices(weights,30,random.Random(42)),
                         random.Random(42).choices(range(5),weights=weights,k=30))
        for weights in ([0,0],[1,-1],[float('nan')],[]):
            with self.assertRaises(ValueError):sample_indices(weights,3,random.Random(1))

    def test_exact_turn_ignores_sampling_method(self):
        def passive(c,b,h,legal,ctx):return {a:float(a==('check' if 'check' in legal else 'call')) for a in legal}
        args=(['Ah','Jh'],['Kh','8h','2c','3d'],{('Ks','Kd'):1,('Ac','Jc'):1},10,10,passive,'test')
        config=SearchConfig(exact_turn=True,fractions=(.5,))
        a=solve_postflop(*args,config)
        b=solve_postflop(*args,replace(config,chance_method='stratified'))
        self.assertEqual(a['comparisons'],b['comparisons'])
        self.assertTrue(b['exact_under_model'])

    def test_stratified_flop_respects_blockers_and_declares_sampling(self):
        def passive(c,b,h,legal,ctx):return {a:float(a==('check' if 'check' in legal else 'call')) for a in legal}
        result=solve_postflop(['Ah','Kh'],['Qh','Jh','Th'],{('Ks','Kd'):1},10,2,passive,'test',
            SearchConfig(chance_method='stratified',chance_samples=3,all_in_samples=20))
        self.assertTrue(result['requires_independent_seed_validation'])
        self.assertFalse(result['exact_under_model'])
        for node in result['chance_trace']:
            self.assertAlmostEqual(sum(b['weight'] for b in node['branches']),1)
            self.assertTrue(all(b['card'] not in node['board']+['Ah','Kh','Ks','Kd'] for b in node['branches']))
