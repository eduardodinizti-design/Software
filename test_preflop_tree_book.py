"""External tree contract tests with explicitly synthetic node/EV fixtures."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from preflop_advisor import PreflopAdvisor
from preflop_policy import PreflopPolicy,resolve_decision,execution_reasons
from preflop_tree_book import TreeBook
from test_preflop_advisor import HANDS,pack_with_node


def fixture():
    acts=[dict(kind='fold',label='Fold',to=0.),dict(kind='call',label='Call',to=7.5),
          dict(kind='raise',label='Raise 18.75',to=18.75),dict(kind='raise',label='Raise 22.5',to=22.5)]
    freq=[0.]*(4*169)
    for i,h in enumerate(HANDS):
        if h=='AA':freq[2*169+i]=.4;freq[3*169+i]=.6
        else:freq[i]=1.
    return dict(id='CO_vs_SB_3bet_50',config=dict(stack=50.,realization='balanced',rake_pct=0.),
                status=dict(iteration=100,published_iteration=100,accuracy_iteration=100,state='done',multiway_equity_model='coupled_deck_v1'),path=[1,0,2,0],locks=[],
                node=dict(kind='action',actor_pos='CO',positions=['CO','BTN','SB','BB'],
                          invested=[2.5,0.,7.5,1.],pot=11.,low_reach=False,strategy_note=None,
                          actions=acts,strategy=freq,reach=[1.]*169),
                hand_order=HANDS,action_values=dict(path=[1,0,2,0],actor='CO',units='original bb relative to folding here',hands=[
                    dict(hand=h,actions=[dict(label=a['label'],ev_bb=([0.,1.,2.,2.01][j] if h=='AA' else [0.,-1.,-2.,-3.][j])) for j,a in enumerate(acts)]) for h in HANDS]))


def context():
    return dict(scenario='vs_3bet',hero_position='CO',aggressor='SB',hero_stack=47.5,
                hero_bet=2.5,effective_stack_bb=50.,players=4,to_call=5.,to_beat=7.5,pot=11.,
                limpers=[],callers=[],mode='chip_ev',stage='mid')


class ContextualTreeTests(unittest.TestCase):
    def setUp(self):
        self.raw=fixture();self.book=TreeBook([TreeBook.decode(self.raw,'abc','test.json')])
        self.policy=PreflopPolicy(PreflopAdvisor(pack_with_node()),tree_book=self.book)

    def test_real_context_routes_to_specific_tree_with_honest_origin(self):
        a=self.policy.decide(['As','Ah'],context())
        self.assertEqual(a['origin'],'CONTEXTUAL_TREE_REFERENCE')
        self.assertEqual(a['recommended'],'four_bet');self.assertEqual(a['sizing']['size_bb'],22.5)
        self.assertFalse(a['solver_validated']);self.assertFalse(a['validated'])
        self.assertEqual(a['tree_evaluation']['selected_reference_ev_bb'],2.01)
        self.assertFalse(execution_reasons(a,['As','Ah']))

    def test_same_action_two_sizes_remain_distinct_in_frequency_sampling(self):
        a=self.policy.decide(['As','Ah'],context());seen=set()
        for hand_id in range(50):
            resolved=resolve_decision(a,['T',hand_id]);seen.add(resolved['sizing']['size_bb'])
        self.assertEqual(seen,{18.75,22.5})

    def test_another_aggressor_does_not_reuse_this_tree(self):
        c=context();c['aggressor']='BB'
        self.assertIsNone(self.book.lookup(['As','Ah'],c))

    def test_terminal_allin_does_not_reuse_a_nonterminal_tree(self):
        self.assertIsNone(self.book.lookup(['As','Ah'],dict(context(),facing_all_in=True)))

    def test_source_shove_is_not_projected_into_a_5000bb_shove(self):
        raw=fixture();raw['node']['actions'][3].update(kind='jam',label='All-in 50',to=50.)
        for row in raw['action_values']['hands']:row['actions'][3]['label']='All-in 50'
        book=TreeBook([TreeBook.decode(raw,'abc','test.json')])
        c=context();c.update(hero_stack=4997.5,effective_stack_bb=5000.)
        a=PreflopPolicy(PreflopAdvisor(pack_with_node()),tree_book=book).decide(['As','Ah'],c)
        self.assertEqual(a['recommended'],'four_bet');self.assertFalse(a['sizing']['all_in'])
        self.assertLess(a['sizing']['size_bb'],100.)

    def test_unsupported_mode_does_not_claim_ordinary_chip_tree_is_pko(self):
        c=context();c.update(mode='pko',tournament_profile=dict(kind='pko'))
        self.assertIsNone(self.book.lookup(['As','Ah'],c))

    def test_depth_difference_remains_a_reference_without_freezing(self):
        c=context();c.update(hero_stack=497.5,effective_stack_bb=500.,players=9)
        a=self.policy.decide(['As','Ah'],c)
        self.assertFalse(execution_reasons(a,['As','Ah']))
        self.assertTrue(any(r['field']=='effective_stack_bb' for r in a['reference_reasons']))
        self.assertFalse(a['sizing']['all_in'])

    def test_unsupported_hero_arrival_hand_leaves_base_policy_available(self):
        raw=fixture();raw['node']['reach'][HANDS.index('AA')]=0
        book=TreeBook([TreeBook.decode(raw,'abc','test.json')])
        self.assertIsNone(book.lookup(['As','Ah'],context()))
        a=PreflopPolicy(PreflopAdvisor(pack_with_node()),tree_book=book).decide(['As','Ah'],context())
        self.assertEqual(a['status'],'ADVICE')

    def test_nan_ev_and_wrong_ev_node_are_rejected(self):
        for change in ('nan','path'):
            raw=fixture()
            if change=='nan':raw['action_values']['hands'][0]['actions'][0]['ev_bb']=float('nan')
            else:raw['action_values']['path']=[999]
            with self.assertRaises(ValueError):TreeBook.decode(raw,'abc','test.json')

    def test_missing_ev_stays_none(self):
        raw=fixture();raw['action_values']=None
        record=TreeBook.decode(raw,'abc','test.json')
        self.assertIsNone(record['hands']['AA'][2]['reference_ev_bb'])

    def test_unrecognized_ev_unit_is_not_silently_converted_to_bb(self):
        raw=fixture();raw['action_values']['units']='USD prize EV'
        with self.assertRaises(ValueError):TreeBook.decode(raw,'abc','test.json')

    def test_interrupted_calculation_is_available_for_study_and_leaves_live_nvt_available(self):
        raw=fixture();raw['status'].update(state='stopped',accuracy_iteration=None)
        book=TreeBook([TreeBook.decode(raw,'abc','test.json')])
        self.assertIsNone(book.lookup(['As','Ah'],context()))
        self.assertIsNotNone(book.lookup(['As','Ah'],dict(context(),reference_tree_study=True)))
        a=PreflopPolicy(PreflopAdvisor(pack_with_node()),tree_book=book).decide(['As','Ah'],context())
        self.assertEqual(a['status'],'ADVICE')

    def test_invalid_optional_file_is_reported_without_breaking_nvt(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'broken.json').write_text('{')
            book=TreeBook.from_directory(d)
        self.assertFalse(book.records);self.assertEqual(len(book.errors),1)
        a=PreflopPolicy(PreflopAdvisor(pack_with_node()),tree_book=book).decide(['As','Ah'],context())
        self.assertEqual(a['status'],'ADVICE')


if __name__=='__main__':unittest.main()
