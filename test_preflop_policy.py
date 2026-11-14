"""Known-input strategy/eligibility contracts; all states and packs synthetic.

No OS input or capture. These tests establish functional coverage, not GTO/ROI.
"""
import copy
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from preflop_advisor import PreflopAdvisor
from preflop_policy import (PreflopPolicy, RuntimePreflopAdvisor, observation,
                            execution_reasons, resolve_decision, size_for)
from preflop_equity import equity_vs_range, hand_to_combos
from tournament_profiles import resolve, cash_call_ev, validate, for_target
from decision_contract import evaluate
from action_coordinator import map_advice_to_action
from test_preflop_advisor import HANDS, pack_with_node, shove_pack


def source():
    p=pack_with_node()
    for node in list(p['nodes']):
        node['context']['stack']=100
        node['validated']=False
        for pos in ('UTG','SB','BB'):
            extra=copy.deepcopy(node);extra.update(id=pos,hero=pos);p['nodes'].append(extra)
    return PreflopAdvisor(p)


def context(depth=200,scenario='unopened',**kw):
    own={'vs_3bet':2.5,'vs_4bet':8.,'vs_5bet':20.}.get(scenario,0.)
    beat={'vs_3bet':8.,'vs_4bet':20.,'vs_5bet':48.}.get(scenario,1.)
    c=dict(scenario=scenario,hero_position='BTN',aggressor='SB' if own else None,
           hero_stack=depth,hero_bet=own,effective_stack_bb=depth,players=9,
           to_call=max(0,beat-own),pot=max(1.5,beat+own),to_beat=beat,
           limpers=[],callers=[],mode='chip_ev',stage='mid',raise_levels=[],
           facing_all_in=False,aggressor_inferred_from_price=False)
    c.update(kw);return c


class DeepPolicyTests(unittest.TestCase):
    def setUp(self):self.policy=PreflopPolicy(source())

    def test_all_depths_and_169_classes_produce_declared_decisions(self):
        for depth in (50,60,80,200,5000):
            for scenario in ('unopened','limped','open','open_with_callers','vs_3bet','vs_4bet','vs_5bet'):
                c=context(depth,scenario)
                if scenario=='limped':c['limpers']=['HJ','CO']
                if scenario=='open_with_callers':c.update(aggressor='UTG',callers=['LJ','CO'],to_call=2.5,to_beat=2.5)
                for hand in HANDS:
                    cards=[hand[0]+'s',hand[1]+('s' if hand.endswith('s') else 'h')]
                    a=self.policy.decide(cards,c)
                    self.assertEqual(a['status'],'ADVICE',(depth,scenario,hand,a))
                    self.assertFalse(execution_reasons(a,cards),(depth,scenario,hand,a))
                    self.assertFalse(a['solver_validated'])

    def test_deep_open_is_not_a_stack_sized_shove(self):
        for depth in (50,60,80,200,5000,100000):
            a=self.policy.decide(['As','Ad'],context(depth))
            self.assertEqual(a['recommended'],'raise');self.assertEqual(a['sizing']['size_bb'],2.5)
            self.assertFalse(a['sizing']['all_in']);self.assertFalse(a['validated'])

    def test_four_and_five_bets_are_non_allin_actions_deep(self):
        a=self.policy.decide(['As','Ad'],context(200,'vs_3bet'))
        self.assertEqual(a['recommended'],'four_bet');self.assertFalse(a['sizing']['all_in'])
        a=self.policy.decide(['As','Ad'],context(200,'vs_4bet'))
        self.assertEqual(a['recommended'],'five_bet');self.assertEqual(a['sizing']['size_bb'],40)
        self.assertFalse(a['sizing']['all_in']);self.assertEqual(map_advice_to_action('five_bet')[0],'RAISE')
        a=self.policy.decide(['As','Ad'],context(5000,'vs_5bet'))
        self.assertEqual(a['recommended'],'six_bet');self.assertLess(a['sizing']['size_bb'],5000)

    def test_overlimp_is_distinct_from_iso_and_fold(self):
        c=context(80,'limped',limpers=['HJ','CO'])
        aa=self.policy.decide(['As','Ad'],c);pair=self.policy.decide(['2s','2h'],c);junk=self.policy.decide(['7s','2h'],c)
        self.assertEqual(aa['recommended'],'raise');self.assertEqual(aa['sizing']['size_bb'],4)
        self.assertEqual(pair['recommended'],'call');self.assertEqual(junk['recommended'],'fold')

    def test_reference_call_has_distinct_authority(self):
        a=self.policy.decide(['2s','2h'],context(200,'limped',limpers=['HJ','CO']))
        r=evaluate(a,action='CALL',hero_cards=['2s','2h'])
        self.assertTrue(r['execution_allowed']);self.assertEqual(r['authority'],'PREFLOP_POLICY')
        self.assertFalse(r['source_validated'])

    def test_missing_observation_is_not_treated_as_a_depth_limit(self):
        self.assertEqual(self.policy.decide(None,context(5000))['status'],'ABSTAIN')
        a=self.policy.decide(['As','Ad'],context(5000,to_call=None))
        self.assertTrue(execution_reasons(a,['As','Ad']))

    def test_stable_sampling_and_price_changes_have_distinct_context(self):
        a=self.policy.decide(['As','Ad'],context())
        a['mix']=[dict(action='call',frequency=.5),dict(action='raise',frequency=.5)]
        self.assertEqual(resolve_decision(a,['table','hand']),resolve_decision(a,['table','hand']))
        b=copy.deepcopy(a);b['policy_context']['to_call']=3
        self.assertNotEqual(resolve_decision(a,['table','hand'])['sampling']['roll'],resolve_decision(b,['table','hand'])['sampling']['roll'])

    def test_source_file_hash_is_retained(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'pack.json';p.write_text(json.dumps(pack_with_node()))
            s=PreflopAdvisor.from_file(p);a=PreflopPolicy(s).decide(['As','Ad'],context())
        self.assertEqual(a['source_nodes'][0]['source_sha256'],s.manifest()['sources'][0]['sha256'])

    def test_confirmed_hero_threebet_tracks_later_fourbet_without_hand_reuse(self):
        rt=RuntimePreflopAdvisor(source());a=self.policy.decide(['As','Ad'],context(200,'open',aggressor='SB',to_beat=2.5,to_call=2.5))
        rt.record_confirmation('T','H',a,{'confirmed':True})
        own=a['sizing']['size_bb']
        state=dict(positions={'hero':'BTN','v':'SB'},seats={'hero':dict(occupied=True,stack_bb=200),'v':dict(occupied=True,stack_bb=170)},
            bets=[dict(seat='hero',bet_bb=own),dict(seat='v',bet_bb=30.)],pot={'pot_bb':40.},to_call={'to_call_bb':30-own},
            decision_table_id='T',decision_hand_id='H')
        r=rt.advise_from_reading(state,['As','Ad'])
        self.assertEqual(r['policy_context']['scenario'],'vs_4bet');self.assertEqual(r['recommended'],'five_bet')
        state['decision_hand_id']='NEW'
        self.assertNotIn('raise_depth_source',rt.advise_from_reading(state,['As','Ad'])['policy_context'])

    def test_unknown_aggressor_is_not_fabricated_as_utg(self):
        s=dict(positions={'hero':'BB','v':'BTN'},seats={'hero':dict(occupied=True,stack_bb=200),'v':dict(occupied=True,stack_bb=200)},
               bets=[dict(seat='hero',bet_bb=1.)],to_call={'to_call_bb':7.},pot={'pot_bb':9.})
        self.assertIsNone(observation(s)['aggressor'])

    def test_source_shove_relabelled_as_raise_is_not_source_validated(self):
        p=shove_pack('open_shove',['AA'],'BTN',(),15,'all_in')
        a=PreflopPolicy(PreflopAdvisor(p)).decide(['As','Ad'],context(300,effective_stack_bb=15))
        self.assertEqual(a['recommended'],'raise');self.assertFalse(a['validated'])
        self.assertEqual(a['derived_rule'],'source_action_reinterpreted_v2')

    def test_exact_deep_shove_tree_is_not_rewritten_by_a_25bb_threshold(self):
        for depth in (80,200,5000):
            p=shove_pack('vs_3bet',['AA'],'BTN',('SB',),depth,'all_in')
            a=PreflopPolicy(PreflopAdvisor(p)).decide(['As','Ad'],context(depth,'vs_3bet'))
            self.assertEqual(a['recommended'],'all_in');self.assertTrue(a['sizing']['all_in'])
            self.assertFalse(execution_reasons(a,['As','Ad']))


class OperatorIntegrationTests(unittest.TestCase):
    def test_same_hand_can_open_then_fourbet_and_threebet_then_fivebet(self):
        # Real operator/policy/sequencer; fake screen/input and no host mouse.
        import numpy as np
        import operar_mesa as op
        from table_reading.automatic_table_crops import TableCrop
        from test_raise_sequencer import World,WInput,_ra_of,_rp_of
        from raise_sequencer import RaiseSequencer
        from shadow_mode import ShadowMonitor
        class Clock:
            now=0.
            def __call__(self):return self.now
            def sleep(self,s):self.now+=s
        for first,second,expected in [('unopened','vs_3bet',['raise','four_bet']),('open','vs_4bet',['three_bet','five_bet']),('pending_reading','pending_reading',[None,None])]:
            with self.subTest(first=first),ExitStack() as stack:
                clock=Clock();world=World();inp=WInput(world);ra=_ra_of(world);rp=_rp_of(world)
                prop=TableCrop((0,0,753,1334),'COMPLETE_CANDIDATE',[],'SIMULATED')
                frame=np.zeros((1334,753,3),np.uint8);calls=[]
                def observe(crop,advisor,**kw):
                    if calls:world.clicks=0
                    scenario=second if calls else first
                    own={'unopened':0.,'open':0.,'vs_3bet':2.5,'vs_4bet':7.5}.get(scenario,0.)
                    beat={'unopened':1.,'open':2.5,'vs_3bet':8.,'vs_4bet':22.5}.get(scenario,1.)
                    st=dict(positions={'hero':'BTN','v':'SB'},
                            seats={'hero':dict(occupied=True,stack_bb=200),'v':dict(occupied=True,stack_bb=200)},
                            bets=[dict(seat='hero',bet_bb=own),dict(seat='v',bet_bb=beat)],
                            pot={'pot_bb':own+beat+1},to_call={'to_call_bb':beat-own},
                            decision_table_id=kw['table_key'],decision_hand_id='LAB-HAND')
                    if scenario=='pending_reading':st['positions']['hero']=None
                    a=advisor.advise_from_reading(st,['As','Ad']);calls.append(a.get('recommended'))
                    return dict(is_table=True,hero_cards=['As','Ad'],hand={'hand_id':'LAB-HAND'},board={'cards':[]},table_state=st,advice=a)
                def seq(**kw):
                    kw.update(read_actions=ra,read_panel=rp,read_hand=lambda c:{'hand_id':'LAB-HAND'},
                              detect=lambda *a,**k:[prop],sleep=clock.sleep,clock=clock)
                    return RaiseSequencer(**kw)
                patches={'configure_ocr':lambda:None,'WindowCaptureEngine':lambda:type('Engine',(),{'capture_frame':lambda self,**kw:(frame,{'status':'SUCCESS'})})(),
                    'discover_pppoker':lambda:{'windows':[dict(hwnd=1,x=0,y=0,w=753,h=1334,title='LAB MTT NLH')]},
                    'detect_table_crops':lambda *a,**k:[prop],'detect_tournament_end':lambda c:{'status':'NONE'},
                    'read_action_buttons':ra,'read_hand_id':lambda c:{'hand_id':'LAB-HAND'},'advise_table':observe,
                    'WindowsCursorInput':lambda:inp,'RaiseSequencer':seq,'ShadowMonitor':lambda **kw:ShadowMonitor(path=None,**kw)}
                for key,value in patches.items():stack.enter_context(patch.object(op,key,value))
                stack.enter_context(patch.object(op.PreflopAdvisor,'from_file',return_value=RuntimePreflopAdvisor(source())))
                stack.enter_context(patch.object(op.time,'sleep'));stack.enter_context(redirect_stdout(io.StringIO()))
                if hasattr(op,'_activate_target'):stack.enter_context(patch.object(op,'_activate_target',return_value=True))
                if hasattr(op,'_target_is_active'):stack.enter_context(patch.object(op,'_target_is_active',return_value=True))
                # Clone's extra feedback is isolated to a temporary runtime.
                with tempfile.TemporaryDirectory() as d:
                    try:
                        from clone_app import settings
                    except ImportError:settings=None
                    if settings:stack.enter_context(patch.object(settings,'DATA',Path(d)))
                    self.assertEqual(op.main(['--hwnd','1','--ranges','LAB','--arm','--auto-arm','--no-hotkeys','--frames','2']),0)
                self.assertEqual(calls,expected);self.assertEqual(len(inp.clicks),6 if any(expected) else 0)


class TournamentProfileTests(unittest.TestCase):
    def test_global_pko_head_is_not_reused_for_an_unconfirmed_target(self):
        p=resolve(kind='pko',bounty_bb=100,cash_fraction=.5)
        self.assertEqual(p['immediate_cash_bb'],50)
        self.assertIsNone(for_target(p,seat='A')['immediate_cash_bb'])

    def test_fresh_target_heads_scale_independently(self):
        p=resolve(kind='pko',cash_fraction=.5,bounty_bb_per_unit=.1)
        a=for_target(p,units=100,fresh=True,seat='A',unit='currency')
        b=for_target(p,units=200,fresh=True,seat='B',unit='currency')
        self.assertEqual((a['immediate_cash_bb'],b['immediate_cash_bb']),(5,10))
        self.assertIsNone(for_target(p,units=200,fresh=False,seat='B')['immediate_cash_bb'])

    def test_native_bb_head_does_not_get_currency_conversion_again(self):
        p=resolve(kind='pko',cash_fraction=.5,bounty_bb_per_unit=999)
        self.assertEqual(for_target(p,units=20,fresh=True,seat='A',unit='bb')['immediate_cash_bb'],10)

    def test_currency_head_without_conversion_remains_unknown(self):
        p=resolve(kind='pko',cash_fraction=.5)
        self.assertIsNone(for_target(p,units=200,fresh=True,seat='A',unit='currency')['immediate_cash_bb'])

    def test_fixed_ko_head_stays_a_declared_constant(self):
        p=resolve(kind='ko',bounty_bb=20)
        self.assertEqual(for_target(p,seat='A')['immediate_cash_bb'],20)

    def test_live_reader_prices_only_a_fresh_high_confidence_target(self):
        import numpy as np
        import table_advisor as ta
        from unittest.mock import Mock
        source_pack=shove_pack('open_shove',HANDS,'SB',(),10,'all_in')
        advisor=RuntimePreflopAdvisor(PreflopAdvisor(source_pack));cache=Mock()
        state=dict(positions={'hero':'BB','v':'SB'},
                   seats={'hero':dict(occupied=True,stack_bb=200),'v':dict(occupied=True,stack_bb=0)},
                   bets=[dict(seat='hero',bet_bb=1),dict(seat='v',bet_bb=11)],
                   pot={'pot_bb':12},to_call={'to_call_bb':10},dealer={'seat':'v'})
        detail=dict(equity=.4,win_probability=.35,tie_probability=.1,iterations=1600,seed=0,method='synthetic_contract')
        with ExitStack() as st:
            card_reader='read_hero_card_slots' if hasattr(ta,'read_hero_card_slots') else 'read_hero_cards'
            for name,value in {'read_table_state':state,'read_hand_id':{'hand_id':'LAB'},
                               card_reader:['7s','2h'],'read_board':{'cards':[],'status':'BOARD_PARTIAL_OR_OBSTRUCTED','reason':'FIRST_CARD_ANCHOR_MISSING'},
                               'read_tournament':{'name':'PKO'}}.items():
                st.enter_context(patch.object(ta,name,return_value=value))
            read=st.enter_context(patch('table_reading.bounty.read_seat_bounties'))
            st.enter_context(patch('preflop_policy.equity_vs_range',return_value=detail))
            read.return_value={'v':dict(value=200,unit='currency',confidence='high')}
            first=ta.advise_table(np.zeros((700,400,3),np.uint8),advisor,tournament_type='pko',
                                 bounty_bb=999,bounty_cash_fraction=.5,bounty_bb_per_unit=.1,read_cache=cache)
            self.assertEqual(first['advice']['tournament_profile']['immediate_cash_bb'],10)
            read.return_value={'v':dict(value=400,unit='currency',confidence='medium')}
            second=ta.advise_table(np.zeros((700,400,3),np.uint8),advisor,tournament_type='pko',
                                  bounty_bb=999,bounty_cash_fraction=.5,bounty_bb_per_unit=.1,read_cache=cache)
            self.assertIsNone(second['advice']['tournament_profile']['immediate_cash_bb'])
            cache.bounties.assert_not_called()

    def test_freezeout_and_progressive_bounty_are_independent(self):
        p=resolve(kind='pko',entry='freezeout',bounty_bb=20,cash_fraction=.5)
        self.assertEqual((p['kind'],p['entry_type'],p['mode']),('pko','freezeout','pko'))
        self.assertEqual(p['immediate_cash_bb'],10);self.assertFalse(p['future_progressive_value_included'])

    def test_fixed_ko_gets_full_cash_and_regular_prior(self):
        p=resolve(kind='ko',entry='reentry',bounty_bb=20,cash_fraction=.5)
        self.assertEqual(p['immediate_cash_bb'],20);self.assertEqual(p['mode'],'chip_ev')

    def test_mystery_activation_is_not_invented_from_itm(self):
        t={'name':'Mystery KO','in_money':True}
        self.assertIsNone(resolve(t,kind='mystery',bounty_bb=20)['immediate_cash_bb'])
        self.assertEqual(resolve(t,kind='mystery',bounty_bb=20,bounty_active=False)['immediate_cash_bb'],0)
        self.assertEqual(resolve(t,kind='mystery',bounty_bb=20,bounty_active=True)['immediate_cash_bb'],20)

    def test_unknown_bounty_and_unknown_fraction_are_explicit(self):
        self.assertEqual(resolve({'name':'Bounty Hunter'})['kind'],'unknown_bounty')
        self.assertIsNone(resolve(kind='pko',bounty_bb=20)['immediate_cash_bb'])

    def test_phase_routes_to_pko_icm(self):
        self.assertEqual(resolve(kind='pko',stage='bubble')['mode'],'pko_icm')
        self.assertEqual(resolve(kind='regular',stage='bubble')['mode'],'icm')

    def test_bad_configuration_fails_early(self):
        for kwargs in ({'bounty_bb':-1},{'cash_fraction':1.1},{'bounty_bb':float('nan')},{'kind':'plo'},{'bounty_active':'yes'}):
            with self.assertRaises(ValueError):validate(**kwargs)

    def test_bounty_cash_can_change_a_terminal_decision_only_when_covered(self):
        ko=resolve(kind='ko',bounty_bb=20);pko=resolve(kind='pko',bounty_bb=20,cash_fraction=.5)
        args=dict(equity=.4,win_probability=.35,pot_bb=10,to_call_bb=10,heads_up=True,covers_target=True)
        self.assertEqual(cash_call_ev(profile=ko,**args)['call_ev_bb'],5)
        self.assertEqual(cash_call_ev(profile=pko,**args)['call_ev_bb'],1.5)
        args['covers_target']=False
        self.assertEqual(cash_call_ev(profile=ko,**args)['call_ev_bb'],-2)
        args.update(covers_target=True,heads_up=False)
        self.assertFalse(cash_call_ev(profile=ko,**args)['bounty_applied'])

    def test_tie_equity_does_not_collect_a_bounty(self):
        detail=equity_vs_range(['2c','3d'],[(c,1.) for c in hand_to_combos('AA')],board=['As','Ks','Qs','Js','Ts'],iters=20,return_details=True)
        self.assertEqual(detail['equity'],.5);self.assertEqual(detail['win_probability'],0)
        e=cash_call_ev(equity=.5,win_probability=0,pot_bb=1010,to_call_bb=1000,
            profile=resolve(kind='ko',bounty_bb=100),heads_up=True,covers_target=True)
        self.assertEqual(e['call_ev_bb'],5);self.assertEqual(e['immediate_bounty_ev_bb'],0)

    def test_allin_runtime_uses_bounty_model_not_only_metadata(self):
        source_pack=shove_pack('open_shove',HANDS,'SB',(),10,'all_in')
        policy=PreflopPolicy(PreflopAdvisor(source_pack))
        d=dict(equity=.4,win_probability=.35,tie_probability=.1,iterations=1600,seed=0,method='synthetic_contract')
        c=context(200,'open',hero_position='BB',aggressor='SB',hero_bet=1,to_call=10,to_beat=11,pot=12,players=2,
                  facing_all_in=True,heads_up_confirmed=True,covers_target=True)
        with patch('preflop_policy.equity_vs_range',return_value=d):
            c['tournament_profile']=resolve(kind='regular');r=policy.decide(['7s','2h'],c)
            c['tournament_profile']=resolve(kind='ko',bounty_bb=20);k=policy.decide(['7s','2h'],c)
        self.assertEqual(r['recommended'],'fold');self.assertEqual(k['recommended'],'call')
        self.assertTrue(k['call_evaluation']['bounty_applied'])


if __name__=='__main__':unittest.main()
