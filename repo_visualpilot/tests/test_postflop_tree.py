import copy
import unittest
from visualpilot.lab.range_state import RangeState, condition, normalize_range
from visualpilot.lab.river_tree import solve_river, river_tree

HERO=['As','Ad']
BOARD='2c 3d 7h 9s Jc'.split()
KK=('Ks','Kd'); JJ=('Js','Jd')


def choose(action,legal):
    return {a:float(a==action) for a in legal}


class RangeHistoryTests(unittest.TestCase):
    def test_bayes_and_source_isolation(self):
        original={KK:3,JJ:1};source={'node':'nvt','nested':[1]}
        state=RangeState('hand1',HERO,BOARD[:3],original,source)
        state.observe('a1','bet',{KK:.1,JJ:.9},'fixture-v1')
        self.assertAlmostEqual(state.weights[KK],.25)
        self.assertAlmostEqual(state.weights[JJ],.75)
        self.assertEqual(original,{KK:3,JJ:1})
        source['nested'].append(2)
        snapshot=state.snapshot();snapshot['events'].clear()
        self.assertEqual(state.provenance['nested'],[1]);self.assertEqual(len(state.events),1)

    def test_new_street_blockers_and_duplicate_event(self):
        state=RangeState('hand1',HERO,BOARD[:3],{KK:1,JJ:1},{})
        state.reveal('turn',BOARD[:3]+['Ks'])
        self.assertEqual(state.weights,{JJ:1.})
        before=state.snapshot()
        with self.assertRaises(ValueError): state.reveal('turn',list(state.board)+['4c'])
        with self.assertRaises(ValueError): state.reveal('river',list(state.board)+['Js'])
        self.assertEqual(state.snapshot(),before)

    def test_zero_likelihood_and_incomplete_models_do_not_mutate(self):
        state=RangeState('hand1',HERO,BOARD[:3],{KK:1,JJ:1},{})
        before=state.snapshot()
        for likelihood in ({KK:0,JJ:0},{KK:1},{KK:float('nan'),JJ:1}):
            with self.assertRaises(ValueError): state.observe('a1','bet',likelihood,'model')
            self.assertEqual(state.snapshot(),before)
        with self.assertRaises(ValueError): normalize_range({KK:1,tuple(reversed(KK)):1})


class RiverTreeTests(unittest.TestCase):
    def solve(self,weights,model,**kw):
        return solve_river(HERO,BOARD,weights,10,20,[2],[6],model,'test-v1',**kw)

    def test_hero_never_sees_hidden_combo_when_choosing_response(self):
        def model(combo,board,history,legal):
            return choose('check' if history==('check',) else 'raise:6',legal)
        result=self.solve({KK:1,JJ:1},model)
        decision=next(d for d in result['decisions'] if d['history']==['bet:2','raise:6'])
        self.assertEqual(decision['alternatives'],{'fold':-2,'call':5})
        self.assertEqual(decision['chosen'],'call')
        self.assertEqual(result['ev'],5)

    def test_conditioning_on_raise_changes_decision(self):
        def model(combo,board,history,legal):
            if history==('check',): return choose('check',legal)
            return choose('raise:6' if combo==JJ else 'call',legal)
        result=self.solve({KK:1,JJ:1},model)
        decision=next(d for d in result['decisions'] if d['history']==['bet:2','raise:6'])
        self.assertEqual(decision['chosen'],'fold')
        self.assertEqual(decision['alternatives'],{'fold':-2,'call':-6})
        self.assertEqual(len(decision['range']),1)

    def test_check_raise_bluff_accounting(self):
        def model(combo,board,history,legal):
            if history==('check',): return choose('bet:2',legal)
            if history==('check','bet:2','raise:6'): return choose('fold',legal)
            return choose('call',legal)
        result=self.solve({JJ:1},model)
        self.assertEqual(result['chosen'],'check')
        self.assertEqual(result['ev'],12)
        decision=next(d for d in result['decisions'] if d['history']==['check','bet:2'])
        self.assertEqual(decision['chosen'],'raise:6')

    def test_check_call_and_check_fold(self):
        def model(combo,board,history,legal):
            return choose('bet:2' if history==('check',) else 'call',legal)
        for weights,expected in (({JJ:1},'fold'),({JJ:1,KK:1},'call')):
            result=self.solve(weights,model)
            decision=next(d for d in result['decisions'] if d['history']==['check','bet:2'])
            self.assertEqual(decision['chosen'],expected)

    def test_raise_bounds_allin_and_invalid_models(self):
        tree=river_tree(7,[4],[5,7])
        self.assertNotIn('raise:5',tree.children['bet:4'].children)
        self.assertIn('raise:7',tree.children['bet:4'].children)
        with self.assertRaises(ValueError): river_tree(5,[6],[])
        with self.assertRaises(ValueError): self.solve({KK:1},lambda *args:{'check':.5})
        with self.assertRaises(ValueError): solve_river(HERO,BOARD[:4],{KK:1},10,20,[2],[6],None,'test')

    def test_tie_payoffs_and_reproducible_trace(self):
        def model(combo,board,history,legal): return choose('check' if 'check' in legal else 'call',legal)
        args=(['2d','3d'],'Tc Jc Qc Kc Ac'.split(),{('4h','5h'):1},10,20,[2],[6],model,'test')
        first=solve_river(*args);second=solve_river(*args)
        self.assertEqual(first,second)
        self.assertEqual(first['ev'],5)
        self.assertTrue(all(ev==5 for ev in first['decisions'][-1]['alternatives'].values()))

class RiverChanceTests(unittest.TestCase):
    def test_probability_and_blocker_conditioning(self):
        from visualpilot.lab.river_tree import plan_rivers
        def model(combo,board,history,legal): return choose('check',legal)
        result=plan_rivers(HERO,BOARD[:4],{KK:3,JJ:1},10,20,[],[],model,'test')
        self.assertAlmostEqual(result['probability_sum'],1)
        branch=next(b for b in result['branches'] if b['card']=='Ks')
        self.assertAlmostEqual(branch['probability'],.25/44)
        self.assertEqual(branch['solution']['trace']['inputs']['range'],[[*JJ,1.]])
        self.assertEqual(len(result['branches']),46)

    def test_royal_flush_known_win_all_rivers(self):
        from visualpilot.lab.river_tree import plan_rivers
        def model(combo,board,history,legal): return choose('check',legal)
        result=plan_rivers(['Ah','Kh'],'Qh Jh Th 2c'.split(),{KK:1},10,20,[],[],model,'test')
        self.assertEqual(len(result['branches']),44)
        self.assertAlmostEqual(result['ev_check_to_river'],10)
        self.assertAlmostEqual(result['probability_sum'],1)
