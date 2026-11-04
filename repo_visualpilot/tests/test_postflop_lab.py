import unittest
from pathlib import Path
from visualpilot.lab.postflop import expand_range, equity, compare_actions, rank5, range_from_nvt
from visualpilot.agent.nvt_ranges import NvtRangeBook

class PostflopTests(unittest.TestCase):
    def test_hand_categories_and_wheel(self):
        hands = ['Ac Jd 9h 6s 3c','Ac Ad 9h 6s 3c','Ac Ad 9h 9s 3c',
                 'Ac Ad Ah 6s 3c','Ac 2d 3h 4s 5c','Ac Jc 9c 6c 3c',
                 'Ac Ad Ah 6s 6c','Ac Ad Ah As 3c','9c Tc Jc Qc Kc']
        ranks = [rank5(h.split()) for h in hands]
        self.assertEqual([r[0] for r in ranks], list(range(9)))
        self.assertLess(rank5('Ac 2d 3h 4s 5c'.split()), rank5('2c 3d 4h 5s 6c'.split()))

    def test_combinations_and_blockers(self):
        self.assertEqual(len(expand_range({'AA':1,'AKs':1,'AKo':1})),22)
        self.assertEqual(len(expand_range({'AA':1}, ['Ac'])),3)
        self.assertEqual(len(expand_range({'AKs':.5})),4)
        with self.assertRaises(ValueError): expand_range({'AK':1})

    def test_exact_river_split_and_weights(self):
        board = 'Tc Jc Qc Kc Ac'.split()
        self.assertEqual(equity(['2d','3d'],board,{('4h','5h'):1})['equity'],.5)
        r=equity(['As','Ad'],'2c 3d 7h 9s Jc'.split(),{('Ks','Kd'):3,('Js','Jd'):1})
        self.assertEqual(r['equity'],.75)

    def test_ev_and_response_conditioning(self):
        hero=['As','Ad'];board='2c 3d 7h 9s Jc'.split();villain={('Ks','Kd'):3,('Js','Jd'):1}
        r=compare_actions(hero,board,villain,10,20,bets=[5],
                          fold_by_combo={5:{('Ks','Kd'):1,('Js','Jd'):0}})
        bet=next(x for x in r['comparisons'] if x['action']=='bet')
        self.assertEqual(bet['called_equity']['equity'],0)
        self.assertEqual(bet['ev'],6.25)
        self.assertEqual(r['best_under_model']['action'],'check')
        call=compare_actions(hero,board,villain,10,20,to_call=5)
        self.assertEqual(call['best_under_model']['ev'],6.25)

    def test_bad_context_is_rejected(self):
        args=(['As','Ad'],'2c 3d 7h'.split(),{('Ks','Kd'):1},10,20)
        with self.assertRaises(ValueError): compare_actions(*args,bets=[5])
        with self.assertRaises(ValueError): compare_actions(*args,to_call=21)
        with self.assertRaises(ValueError): equity(['As','As'],['2c','3d','7h'],{('Ks','Kd'):1})
        with self.assertRaises(ValueError): equity(['As','Ad'],['2c','3d','7h'],{('As','Kd'):1})

    def test_monte_carlo_reproducible(self):
        args=(['As','Ad'],['2c','3d','7h'],{('Ks','Kd'):1})
        self.assertEqual(equity(*args,samples=100),equity(*args,samples=100))

    def test_real_nvt_range_import(self):
        book=NvtRangeBook(Path(__file__).parent/'fixtures/nvt_range_excerpt.json')
        node=next(n for n in book.nodes.values() if n['spot']=='open_raise')
        combos,trace=range_from_nvt(book,node['id'],'raise',['As','Kd','2c'])
        self.assertTrue(combos)
        self.assertEqual(trace['node_id'],node['id'])
        self.assertTrue(all(not set(c)&{'As','Kd','2c'} for c in combos))
