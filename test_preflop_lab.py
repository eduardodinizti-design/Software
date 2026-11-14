"""Independent analytic poker/payoff checks and known-input lab contracts."""
import unittest
import numpy as np
from preflop_equity import eval7,parse_card
from preflop_lab.cards import card_id,card_text,evaluate,deal,hand_class,range_weights
from preflop_lab.payouts import settle,bounty_awards
from preflop_lab.engine import actions,solve,fit_future,validate


class ExactCardsTests(unittest.TestCase):
    def test_ranking_matches_independent_scalar_on_6000_legal_hands(self):
        rng=np.random.default_rng(42)
        hands=np.asarray([rng.choice(52,7,replace=False) for _ in range(6000)])
        scores=evaluate(hands)
        reference=[eval7([parse_card(card_text(c)) for c in row]) for row in hands]
        order=sorted(range(len(reference)),key=lambda i:reference[i])
        self.assertTrue((np.diff(scores[order])>=0).all())
        for a,b in zip(order,order[1:]):self.assertEqual(reference[a]==reference[b],scores[a]==scores[b])

    def test_common_royal_board_and_quads_are_ties(self):
        for board in ('As Ks Qs Js Ts','2c 2d 2h 2s Ac'):
            cards=[[card_id(c) for c in pair.split()+board.split()] for pair in ('Kc Qd','Jc 9d')]
            scores=evaluate(cards);self.assertEqual(scores[0],scores[1])

    def test_collision_correct_joint_conditioning_is_not_sequential_normalization(self):
        holes,board,_=deal(['As','Kh'],[{'22':1,'33':1},{'22':1}],10000,73)
        probability=sum(hand_class(pair)=='22' for pair in holes[:,1])/len(holes)
        # Exact count: 6 disjoint 22/22 ordered deals versus 36 33/22 deals.
        self.assertAlmostEqual(probability,1/7,delta=.015)
        all_cards=np.concatenate((holes.reshape(len(holes),-1),board),axis=1)
        self.assertFalse((np.diff(np.sort(all_cards,axis=1),axis=1)==0).any())

    def test_a_restricted_range_does_not_leak_23_into_22(self):
        holes,_,_=deal(['As','Kh'],[{'22':1}],2000,13)
        self.assertTrue(all(hand_class(p)=='22' for p in holes[:,1]))

    def test_empty_and_blocked_ranges_fail_without_sampling_forever(self):
        for weights in ({},{'AA':0},{'bogus':1},{'AA':float('nan')}):
            with self.assertRaises(ValueError):range_weights(weights)
        with self.assertRaises(ValueError):deal(['As','Ah'],[{'AA':1},{'AA':1}],100,1)

    def test_duplicate_cards_are_rejected(self):
        with self.assertRaises(ValueError):evaluate([[0,0,1,2,3]])


class SidePotTests(unittest.TestCase):
    def test_threeway_royal_returns_one_third(self):
        got=settle([[20,20,20]],[[1,1,1]],[[9,9,9]],3.)
        np.testing.assert_allclose(got,[[21,21,21]])

    def test_short_best_hand_only_wins_main_pot(self):
        np.testing.assert_allclose(settle([[20,100,100]],[[1,1,1]],[[9,8,7]]),[[60,160,0]])

    def test_folded_money_remains_in_pot(self):
        np.testing.assert_allclose(settle([[100,100,20]],[[1,0,1]],[[8,9,7]]),[[220,0,0]])

    def test_uncalled_excess_is_returned(self):
        np.testing.assert_allclose(settle([[100,20]],[[1,1]],[[1,9]]),[[80,40]])

    def test_short_bust_prize_goes_to_eligible_winner(self):
        paid=np.array([[100,20]]);active=np.ones((1,2),bool);ranks=np.array([[9,1]])
        award=settle(paid,active,ranks)
        np.testing.assert_allclose(bounty_awards(paid,active,ranks,award,[100,20],[0,10]),[[10,0]])

    def test_a_tie_is_not_an_elimination(self):
        paid=np.array([[100,100]]);active=np.ones((1,2),bool);ranks=np.array([[9,9]])
        award=settle(paid,active,ranks)
        np.testing.assert_allclose(bounty_awards(paid,active,ranks,award,[100,100],[20,20]),[[0,0]])

    def test_tied_eliminators_share_declared_head(self):
        paid=np.array([[100,100,30]]);active=np.ones((1,3),bool);ranks=np.array([[9,9,1]])
        award=settle(paid,active,ranks)
        np.testing.assert_allclose(bounty_awards(paid,active,ranks,award,[100,100,30],[0,0,10]),[[5,5,0]])

    def test_random_valid_allin_pots_conserve_chips(self):
        rng=np.random.default_rng(19)
        paid=rng.integers(1,500,(1000,6));ranks=rng.integers(0,10,(1000,6))
        result=settle(paid,np.ones_like(paid,bool),ranks,3.5)
        np.testing.assert_allclose(result.sum(axis=1),paid.sum(axis=1)+3.5)


def case():
    return dict(id='analytic_AA_vs_KK_allin',pot_bb=10.,last_full_raise_bb=10.,include_shove=False,
                players=[dict(position='BTN',role='hero',stack_bb=10.,bet_bb=0.),
                         dict(position='BB',role='raiser',stack_bb=0.,bet_bb=10.,range={'KK':1.},response={'call':{'KK':1.},'raise':{}})])


class CalculationTests(unittest.TestCase):
    def test_actual_terminal_call_has_positive_heldout_ev(self):
        r=solve(case(),['As','Ah'],train_samples=512,evaluation_samples=8000,seed=31)
        self.assertEqual(r['recommended'],'call');self.assertEqual(r['selected_by'],'training_deals_only')
        self.assertGreater(r['ev_bb'],5.5);self.assertLess(r['ev_bb'],7.2)
        self.assertFalse(r['solver_validated'])

    def test_training_does_not_condition_on_hidden_cards_or_runouts(self):
        # All four samples have the SAME public node. It gets ONE policy choice.
        keys=np.tile(np.array([[20,60,1,1]]),(4,1))
        policy,values=fit_future(np.array([100.,100.,-100.,-100.]),[(np.arange(4),keys,np.full(4,-20.))],min_observations=2)
        self.assertEqual(len(policy),1);self.assertTrue(next(iter(policy.values())))
        np.testing.assert_allclose(values,[100,100,-100,-100])

    def test_minimum_raise_and_explicit_allin(self):
        c=case();c['players'][0]['stack_bb']=200;c.update(raise_sizes_bb=[11,19,20,30],include_shove=True)
        aa=actions(c);targets=[a['raise_to_bb'] for a in aa]
        self.assertNotIn(11,targets);self.assertNotIn(19,targets);self.assertIn(20,targets)
        self.assertEqual(aa[-1]['raise_to_bb'],200);self.assertTrue(aa[-1]['all_in'])

    def test_unmodeled_payout_icm_is_explicitly_rejected_by_lab_only(self):
        c=case();c['mode']='icm'
        with self.assertRaises(ValueError):validate(c)


if __name__=='__main__':unittest.main()
