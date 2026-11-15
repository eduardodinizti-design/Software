"""Operational counterexamples. Synthetic scenes are not Windows validation."""
from dataclasses import asdict, replace
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from action_coordinator import DryRunInput
from hand_journal import HandJournal
from hu_executor import HUExecutor, screen_rect
from strategy.action_tree import Action, BetMenu, apply_action, legal_actions
from strategy.confirmed_history import ConfirmedHistory
from strategy.operational_profile import OperationalProfile
from strategy.policy_observer import PolicyObserver
from strategy.policy_store import CompiledPolicy
from strategy.range_catalog import ComboRange
from strategy.state_contract import BettingState, DecisionState, GameContext, reveal
from strategy.strategy_decision import choose


FLOP = ('Kc','8s','3d')
RIVER = FLOP+('Ts','2h')
HERO = ('As','5s')
SEATS = {'hero':'BTN','villain':'BB','small':'SB','s1':'UTG','s2':'UTG+1',
         's3':'UTG+2','s4':'LJ','s5':'HJ','s6':'CO'}


class Clock:
    def __init__(self): self.now=100.
    def __call__(self): return self.now
    def sleep(self,seconds): self.now+=seconds


def make_test_policy(root=None, recommended=None):
    """Small exact legal tree, invented frequencies; never a solved strategy."""
    root = root or BettingState(FLOP,5.5,(22.5,22.5),actor=1,oop=1)
    ctx = GameContext(('BTN','BB'),arrival_id='SYNTHETIC_OPERATIONAL_TEST')
    ranges = (ComboRange((('As5s',1.),),'synthetic-hero'),
              ComboRange((('AhKd',1.),),'synthetic-villain'))
    menu = BetMenu((.5,),2,True)
    nodes,stack = {},[root]
    while stack:
        s = stack.pop()
        if s.terminal or s.key() in nodes: continue
        if s.needs_cards:
            stack.append(reveal(s,'Ts' if len(s.board)==3 else '2h'))
            continue
        actions = legal_actions(s,menu)
        selected = next((a.id for a in actions if s.actor==0 and a.kind==recommended),None)
        p = {a.id:float(a.id==selected) if selected else 1/len(actions) for a in actions}
        nodes[s.key()] = dict(state=s.to_dict(),actions=[a.to_dict() for a in actions],
            combos={ranges[s.actor].weights[0][0]:dict(frequencies=p,action_ev_bb=None)})
        stack.extend(apply_action(s,a) for a in actions)
    return CompiledPolicy(dict(schema='software.hu-policy.v1',context=asdict(ctx),root=root.to_dict(),
        ranges=[r.to_dict() for r in ranges],menu=asdict(menu),nodes=nodes,
        quality=dict(method='synthetic_operational_test',converged=False,windows_validated=False)))


def reading(s,*,hand='h1',hero=HERO,folded=(),payout=False):
    stacks = {'hero':s.stacks[0],'villain':s.stacks[1],**{k:30. for k in SEATS if k not in ('hero','villain')}}
    if payout and s.terminal=='showdown': stacks['hero']+=s.pot_bb
    ts = dict(positions=dict(SEATS),seats={seat:dict(occupied=True,stack_bb=round(value,1),confidence='high',
        **(dict(in_hand=False,in_hand_confidence='high') if seat in folded else {})) for seat,value in stacks.items()},
        pot=dict(pot_bb=round(s.pot_bb,1),confidence='high'),bets=[],bets_complete=True,
        to_call=dict(to_call_bb=round(s.call_cost_bb,1),confidence='high'))
    turn = s.actor==0 and not s.terminal and not s.needs_cards
    buttons = dict(status='EXPERIMENTAL_BUTTON_ROW' if turn else 'NO_BUTTON_ROW',
        buttons=[dict(action=a,box=[i*120,630,100,40]) for i,a in enumerate(
            ['FOLD','CALL','RAISE'] if s.call_required_bb else ['FOLD','CHECK','BET'])] if turn else [])
    return dict(hand=dict(hand_id=hand),hero_cards=list(hero) if hero else None,hero_slots=list(hero) if hero else [None,None],
        observation_source='SYNTHETIC_TEST_SNAPSHOTS',
        board=dict(cards=list(s.board)),table_state=ts,context=dict(mode='chip_ev',stage='mid')),buttons


class JournalTests(unittest.TestCase):
    def test_restart_does_not_repeat_unknown_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'nested'/'history.sqlite3'
            j=HandJournal(path)
            self.assertTrue(j.claim('t','h','d',{}))
            j.settle('d','INPUT_STARTED',{})
            j.close()
            j=HandJournal(path)
            self.addCleanup(j.close)
            self.assertFalse(j.claim('t','h','d',{}))
            j.settle('d','UNKNOWN_RESULT',{})
            self.assertFalse(j.claim('t','h','d',{}))

    def test_two_connections_only_one_retry_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'j.db'
            j1,j2=HandJournal(path),HandJournal(path)
            self.addCleanup(j1.close);self.addCleanup(j2.close)
            j1.claim('t','h','d',{});j1.settle('d','CANCELLED_BEFORE_INPUT',{})
            barrier=threading.Barrier(2);results=[]
            def claim(j):
                barrier.wait();results.append(j.claim('t','h','d',{}))
            threads=[threading.Thread(target=claim,args=(j,)) for j in (j1,j2)]
            for t in threads:t.start()
            for t in threads:t.join()
            self.assertEqual(sorted(results),[False,True])

    def test_export_detects_tampering_and_id_collision(self):
        j=HandJournal(':memory:');self.addCleanup(j.close)
        j.append('t','h','a',{'event_type':'action','action':'check'})
        j.append('t','h','b',{'event_type':'board','card':'Ts'})
        self.assertTrue(j.export_hand('t','h')['chain_valid'])
        with self.assertRaises(ValueError):j.append('t','h','a',{'action':'bet'})
        j.db.execute("UPDATE events SET payload='{}' WHERE event_id='a'");j.db.commit()
        with self.assertRaisesRegex(ValueError,'CHAIN_BROKEN'):j.export_hand('t','h')

    def test_export_includes_unknown_input_instead_of_calling_the_hand_complete(self):
        j=HandJournal(':memory:');self.addCleanup(j.close)
        j.append('t','h','g',dict(event_type='observation_gap',reason='MISSING_CAPTURE'))
        j.claim('t','h','d',{});j.settle('d','UNKNOWN_RESULT',dict(reason='EFFECT_NOT_OBSERVED'))
        out=j.export_hand('t','h')
        self.assertTrue(out['unresolved_input']);self.assertTrue(out['completeness']['has_observation_gaps'])
        self.assertIsNone(out['completeness']['last_confirmed_terminal'])
        self.assertEqual(out['execution_claims'][0]['state'],'UNKNOWN_RESULT')


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock();self.policy=make_test_policy();self.profile=OperationalProfile(self.policy.fingerprint,require_preflop_witness=False)
        self.j=HandJournal(':memory:');self.addCleanup(self.j.close)
        self.h=ConfirmedHistory(self.policy,self.profile,self.j,clock=self.clock)
        self.serial=0

    def observe(self,s,**kw):
        result,buttons=reading(s,**kw);self.serial+=1
        status=self.h.observe(result,table_id='t',buttons=buttons,sample_id=str(self.serial),captured_at=self.clock())
        return result,buttons,status

    def confirm(self,s,**kw):
        self.observe(s,**kw)
        return self.observe(s,**kw)

    def test_needs_two_real_capture_ids_and_produces_strategy_state_without_injection(self):
        _,_,out=self.observe(self.policy.root)
        self.assertEqual(out['status'],'PENDING')
        result,buttons,out=self.confirm(apply_action(self.policy.root,Action('check')))
        self.assertEqual(out['status'],'CONFIRMED')
        self.assertIn('strategy_state',result['table_state'])
        advice=PolicyObserver(self.policy,self.profile).advise(table_key='t',hand_key='h1',
            table_state=result['table_state'],hero_cards=HERO,board=FLOP,mode='chip_ev',stage='mid')
        self.assertEqual(advice['status'],'ADVICE')
        self.assertEqual(advice['operational']['source_authority'],'COMPILED_HU_REFERENCE')

    def test_unchanged_scene_does_not_oscillate_pending(self):
        s=apply_action(self.policy.root,Action('check'));self.confirm(s)
        for _ in range(4):self.assertEqual(self.observe(s)[2]['status'],'CONFIRMED')

    def test_repeated_pixels_from_same_capture_do_not_count_twice(self):
        result,b=reading(self.policy.root)
        for _ in range(2):out=self.h.observe(result,table_id='t',buttons=b,sample_id='same',captured_at=self.clock())
        self.assertEqual(out['reason'],'HISTORY_DUPLICATE_CAPTURE')
        self.assertNotIn('strategy_state',result['table_state'])

    def test_stale_and_future_snapshot_not_used(self):
        result,b=reading(self.policy.root)
        for at in (self.clock()-5,self.clock()+1):
            out=self.h.observe(result,table_id='t',buttons=b,sample_id=str(at),captured_at=at)
            self.assertEqual(out['reason'],'HISTORY_STALE_CAPTURE')

    def test_multi_street_history_reconstructs_bet_call_and_real_next_card(self):
        s=apply_action(self.policy.root,Action('check'));self.confirm(s)
        s=apply_action(s,Action('bet',s.pot_bb/2));self.confirm(s)
        s=reveal(apply_action(s,Action('call',s.call_cost_bb)),'Ts');self.confirm(s)
        s=apply_action(s,Action('check'));result,_,out=self.confirm(s)
        self.assertEqual(out['status'],'CONFIRMED')
        hand=self.j.export_hand('t','h1')
        actions=[e['payload'] for e in hand['events'] if e['payload']['event_type']=='action']
        self.assertEqual([a['action'] for a in actions],['check','bet','call','check'])
        self.assertTrue(any(e['payload'].get('card')=='Ts' for e in hand['events']))
        self.assertTrue(all(a['exact_observed_chips'] is False for a in actions))
        self.assertEqual(result['table_state']['strategy_state']['revision'],4)

    def test_missing_intermediate_action_can_be_confirmed_only_when_unique(self):
        self.confirm(self.policy.root)
        s=apply_action(self.policy.root,Action('check'))
        s=apply_action(s,Action('bet',s.pot_bb/2))
        self.assertEqual(self.confirm(s)[2]['events'],2)

    def test_unknown_ocr_is_not_a_zero_price(self):
        s=apply_action(self.policy.root,Action('check'));self.confirm(s)
        result,b=reading(s);result['table_state']['to_call']['confidence']='abstain'
        out=self.h.observe(result,table_id='t',buttons=b,sample_id='bad',captured_at=self.clock())
        self.assertEqual(out['reason'],'HISTORY_PRICE_UNREADABLE')

    def test_hidden_hand_id_is_pending_without_crashing_or_reusing_strategy(self):
        s=apply_action(self.policy.root,Action('check'));self.confirm(s)
        result,b=reading(s);result['hand']={}
        result['table_state']['strategy_state']={'old':'must be removed'}
        out=self.h.observe(result,table_id='t',buttons=b,sample_id='occluded',captured_at=self.clock())
        self.assertEqual(out['reason'],'HISTORY_HAND_ID_UNREADABLE')
        self.assertNotIn('strategy_state',result['table_state'])

    def test_new_hand_does_not_inherit_an_old_timeline(self):
        s=apply_action(self.policy.root,Action('check'));self.confirm(s)
        result,b,out=self.observe(s,hand='new')
        self.assertEqual(out['status'],'PENDING');self.assertNotIn('strategy_state',result['table_state'])
        self.assertEqual(self.h.current('t')['revision'],0)

    def test_corrupted_cards_and_multiway_pot_not_matched_to_hu(self):
        self.confirm(self.policy.root)
        bad=replace(self.policy.root,pot_bb=8.)
        self.assertEqual(self.confirm(bad)[2]['status'],'PENDING')
        self.assertEqual(self.confirm(self.policy.root,hero=('Qs','Js'))[2]['reason'],'HISTORY_HERO_CARDS_CHANGED_IN_SAME_HAND')

    def test_restart_recovers_confirmed_public_state_and_posterior(self):
        s=apply_action(self.policy.root,Action('check'));self.confirm(s)
        s=apply_action(s,Action('bet',s.pot_bb/2));self.confirm(s)
        self.h=ConfirmedHistory(self.policy,self.profile,self.j,clock=self.clock)
        result,b,out=self.confirm(s)
        self.assertEqual(out['status'],'CONFIRMED')
        self.assertEqual(self.h.current('t')['line'].state.key(),s.key())
        self.assertEqual(len([e for e in self.j.events('t','h1') if e['payload']['event_type']=='action']),2)

    def witness(self,*,outside_short=False):
        self.profile=replace(self.profile,require_preflop_witness=True)
        self.h=ConfirmedHistory(self.policy,self.profile,self.j,clock=self.clock)
        base,b=reading(self.policy.root)
        base['board']['cards']=[]
        ts=base['table_state'];ts['pot']['pot_bb']=1.5
        ts['seats']['hero']['stack_bb']=25.;ts['seats']['villain']['stack_bb']=24.
        ts['bets']=[dict(seat='small',bet_bb=.5,confidence='high'),dict(seat='villain',bet_bb=1.,confidence='high')]
        if outside_short:ts['seats']['s1']['stack_bb']=1.
        self.h.observe(base,table_id='t',buttons=b,sample_id='base',captured_at=self.clock())
        opened=copy.deepcopy(base);opened['table_state']['seats']['hero']['stack_bb']=22.5
        opened['table_state']['pot']['pot_bb']=4.;opened['table_state']['bets'].append(dict(seat='hero',bet_bb=2.5,confidence='high'))
        self.h.observe(opened,table_id='t',buttons=b,sample_id='open',captured_at=self.clock())
        return base

    def test_root_requires_observed_preflop_not_just_position_and_money(self):
        self.profile=replace(self.profile,require_preflop_witness=True)
        self.h=ConfirmedHistory(self.policy,self.profile,self.j,clock=self.clock)
        self.assertEqual(self.confirm(self.policy.root)[2]['reason'],'HISTORY_PREFLOP_ARRIVAL_NOT_CONFIRMED')
        self.witness()
        out=self.confirm(self.policy.root)[2]
        self.assertEqual(out['status'],'CONFIRMED')
        self.assertEqual(self.h.current('t')['witness']['kind'],'OBSERVED_SRP_BASELINE_OPEN_AND_FLOP_CONSERVATION')

    def test_outside_short_allin_cannot_be_discarded_as_a_fold(self):
        self.witness(outside_short=True)
        for _ in range(2):
            result,b=reading(self.policy.root);result['table_state']['seats']['s1']['stack_bb']=1.
            self.serial+=1;out=self.h.observe(result,table_id='t',buttons=b,sample_id=str(self.serial),captured_at=self.clock())
        self.assertEqual(out['reason'],'HISTORY_PREFLOP_ARRIVAL_NOT_CONFIRMED')

    def test_off_tree_bet_is_saved_without_inventing_a_response_range(self):
        self.confirm(self.policy.root)
        s=apply_action(self.policy.root,Action('bet',2.3))
        result,b,out=self.confirm(s)
        self.assertEqual(out['status'],'CONFIRMED')
        self.assertEqual(out['ranges_status'],'RESPONSE_MODEL_MISSING')
        advice=PolicyObserver(self.policy,self.profile).advise(table_key='t',hand_key='h1',
            table_state=result['table_state'],hero_cards=HERO,board=s.board,mode='chip_ev',stage='mid')
        self.assertEqual(advice['status'],'POLICY_MISS')
        self.assertIn('RESPONSE_MODEL_MISSING',advice['reason'])
        actions=[e['payload'] for e in self.j.events('t','h1') if e['payload']['event_type']=='action']
        self.assertEqual(actions[-1]['action'],'bet');self.assertFalse(actions[-1]['exact_observed_chips'])

    def test_restart_with_different_profile_cannot_trust_old_arrival(self):
        self.confirm(self.policy.root)
        changed=replace(self.profile,quantum_bb=.2)
        self.h=ConfirmedHistory(self.policy,changed,self.j,clock=self.clock)
        for _ in range(2):
            self.assertEqual(self.observe(self.policy.root)[2]['reason'],'JOURNAL_OPERATIONAL_PROFILE_CHANGED')

    def test_other_live_player_stack_change_invalidates_hu_assumption(self):
        self.confirm(self.policy.root)
        result,b=reading(self.policy.root)
        result['table_state']['seats']['s1']['stack_bb']=28.
        out=self.h.observe(result,table_id='t',buttons=b,sample_id='third-player',captured_at=self.clock())
        self.assertEqual(out['reason'],'HISTORY_HU_OUTSIDE_PLAYER_CHIP_CHANGE')

    def test_showdown_payout_does_not_explain_arbitrary_missed_bets(self):
        root=BettingState(RIVER,10.,(30.,30.),actor=1,oop=1)
        self.policy=make_test_policy(root);self.profile=OperationalProfile(self.policy.fingerprint,require_preflop_witness=False)
        self.h=ConfirmedHistory(self.policy,self.profile,self.j,clock=self.clock)
        self.confirm(root)
        checked=apply_action(root,Action('check'));self.confirm(checked)
        terminal=apply_action(checked,Action('check'))
        out=self.confirm(terminal,payout=True)[2]
        self.assertEqual(out['status'],'CONFIRMED',out)
        self.assertEqual(self.h.current('t')['state'].terminal,'showdown')


class World(DryRunInput):
    """Owned, stateful fake GUI. Input advances its state; reads never do."""
    def __init__(self,policy,profile,journal,clock,*,respond=True,wrong_amount=False):
        super().__init__(bounds=(0,0,1366,768),pos=(5,5))
        self.policy,self.profile,self.journal,self.clock=policy,profile,journal,clock
        self.state=policy.root;self.respond=respond;self.wrong_amount=wrong_amount
        self.panel=False;self.selected=1.;self.serial=0;self.sent=False;self.focus=True
        self.mutation=None;self.same_effect_capture=False
    def is_foreground(self,hwnd):return self.focus
    def activate_window(self,hwnd):return self.focus
    def write_amount(self,text,cancel_check=None):
        if cancel_check and cancel_check():return dict(ok=False)
        self.selected=float(text.replace(',','.'))+(1 if self.wrong_amount else 0)
        return dict(ok=True)
    def scene(self,*,panel=False):
        self.serial+=1
        result,b=reading(self.state,folded=['hero'] if self.state.terminal=='fold' else (),payout=True)
        if not self.sent:
            d=DecisionState(self.policy.context,self.state,HERO,'t','h1',1)
            ts=result['table_state'];ts['strategy_state']=asdict(d)
            ts['confirmed_history']=dict(status='CONFIRMED',model_state=self.state.to_dict(),revision=1)
            result['advice']=choose(self.policy,d)
            result['advice']['operational']=dict(profile_sha256=self.profile.fingerprint)
        else:
            result['table_state']['confirmed_history']=dict(status='CONFIRMED',model_state=self.state.to_dict(),revision=2)
        s=dict(result=result,buttons=b,hwnd=123,sample_id=str(self.serial),captured_at=self.clock(),
            source_key='t',window_signature=(123,9,1,(0,0,360,700),(281,49),(0,0,360,700)),
            screen_origin=(281,49),crop_box=(0,0,360,700),phase='normal',
            cards_fresh=True,board_fresh=True,source_kind='SYNTHETIC_OWNED_GUI')
        if self.panel:
            s['phase']='panel';s['panel']=dict(status='EXPERIMENTAL_RAISE_PANEL',presets=[],
                selected=dict(status='AMOUNT_CONFIRMED',value_bb=self.selected,quantum_bb=.001,box=[260,290,70,30],unit='BB',semantics='RAISE_TO_BB'),
                confirm=dict(box=[240,630,100,40]))
        if self.same_effect_capture and self.sent:s['sample_id']='same-effect'
        if self.mutation:self.mutation(s)
        return s
    def click_once(self,x=None,y=None,**kw):
        out=super().click_once(x,y,**kw)
        if not self.respond:return out
        if not self.panel:
            a=next(a for a in self.policy.actions(self.state) if a.id==choose(self.policy,DecisionState(self.policy.context,self.state,HERO,'t','h1',1))['action_id'])
            if a.kind in ('bet','raise','all_in'):self.panel=True
            else:self.state=apply_action(self.state,a);self.sent=True
        elif y>=650:
            a=next(a for a in self.policy.actions(self.state) if a.id==choose(self.policy,DecisionState(self.policy.context,self.state,HERO,'t','h1',1))['action_id'])
            self.state=apply_action(self.state,a);self.sent=True;self.panel=False
        return out


class ExecutorTests(unittest.TestCase):
    def rig(self,kind,*,armed=True,respond=True,wrong_amount=False):
        base=BettingState(RIVER,10.,(30.,30.),actor=1,oop=1)
        root=apply_action(base,Action('bet',5.)) if kind in ('call','fold','raise') else apply_action(base,Action('check'))
        p=make_test_policy(root,kind);profile=OperationalProfile(p.fingerprint,require_preflop_witness=False)
        j=HandJournal(':memory:');self.addCleanup(j.close);clock=Clock()
        w=World(p,profile,j,clock,respond=respond,wrong_amount=wrong_amount)
        bot=type('Control',(),{'running':True,'execution_allowed':lambda s:s.running})()
        ex=HUExecutor(policy=p,profile=profile,journal=j,input_adapter=w,bot_control=bot,
                      scene_supplier=w.scene,armed=armed,clock=clock,sleep=clock.sleep,effect_timeout_s=.25)
        return ex,w,bot

    def test_check_call_fold_bet_raise_and_allin_confirm_effect(self):
        for kind in ('check','call','fold','bet','raise','all_in'):
            with self.subTest(kind=kind):
                ex,w,_=self.rig(kind);out=ex.execute(w.scene())
                self.assertEqual(out['state'],'DONE',out)
                self.assertTrue(out['confirmed'])
                self.assertEqual(len(w.clicks),3 if kind in ('bet','raise','all_in') else 1)
                self.assertEqual(out['evidence'][0]['kind'],'CONFIRMED_HISTORY_TRANSITION')

    def test_dry_run_does_not_focus_move_type_or_click(self):
        ex,w,_=self.rig('bet',armed=False)
        out=ex.execute(w.scene());self.assertEqual(out['state'],'DRY_RUN')
        self.assertEqual(w.moves,[]);self.assertEqual(w.clicks,[])

    def test_sendinput_acknowledgement_is_not_an_observed_action(self):
        ex,w,_=self.rig('call',respond=False)
        initial=w.scene();out=ex.execute(initial)
        self.assertEqual(out['state'],'UNKNOWN_RESULT')
        self.assertFalse(out['confirmed']);self.assertEqual(len(w.clicks),1)
        self.assertEqual(ex.execute(initial)['state'],'CANCELLED_BEFORE_INPUT')
        self.assertEqual(len(w.clicks),1)

    def test_wrong_selected_amount_never_confirms_bet(self):
        ex,w,_=self.rig('raise',wrong_amount=True)
        out=ex.execute(w.scene())
        self.assertEqual(out['state'],'UNKNOWN_RESULT')
        self.assertIn('HU_SELECTED_AMOUNT_DIFFERS',out['reason'])
        self.assertFalse(w.sent);self.assertEqual(len(w.clicks),2)

    def test_paused_does_not_send_input(self):
        ex,w,bot=self.rig('bet');bot.running=False
        self.assertEqual(ex.execute(w.scene())['state'],'CANCELLED_BEFORE_INPUT')
        self.assertFalse(w.clicks)

    def test_new_hand_at_arrival_is_rejected(self):
        ex,w,_=self.rig('call');initial=w.scene()
        w.mutation=lambda s:s['result']['hand'].update(hand_id='other')
        self.assertIn('HAND_CHANGED',ex.execute(initial)['reason']);self.assertFalse(w.clicks)

    def test_focus_loss_during_movement_cancels(self):
        ex,w,_=self.rig('call');initial=w.scene()
        move=w.move_to
        def stolen(*a,**kw):
            result=move(*a,**kw);w.focus=False;return result
        w.move_to=stolen
        self.assertEqual(ex.execute(initial)['state'],'CANCELLED_BEFORE_INPUT');self.assertFalse(w.clicks)

    def test_geometry_changed_before_mouse_down(self):
        ex,w,_=self.rig('call');initial=w.scene()
        w.mutation=lambda s:s.update(window_signature=('other',))
        self.assertIn('GEOMETRY_CHANGED',ex.execute(initial)['reason']);self.assertFalse(w.clicks)

    def test_hidden_panel_id_requires_fresh_cards_and_same_board(self):
        ex,w,_=self.rig('bet')
        def mutation(s):
            if s['phase']=='panel':s['result']['hand']={};s['cards_fresh']=False
        w.mutation=mutation
        out=ex.execute(w.scene())
        self.assertIn('PANEL_CARD_IDENTITY',out['reason']);self.assertEqual(len(w.clicks),1)

    def test_external_advice_cannot_replace_policy_selection(self):
        ex,w,_=self.rig('bet');initial=w.scene()
        initial['result']['advice'].update(recommended='check',action_id='check:0',sizing=dict(size_bb=0.))
        self.assertIn('SELECTION_CHANGED',ex.execute(initial)['reason']);self.assertFalse(w.clicks)

    def test_physical_coordinates_include_client_origin_and_crop_not_window_chrome(self):
        self.assertEqual(screen_rect(dict(screen_origin=(-1200,49),crop_box=(300,5,360,700)),(10,630,100,40)),(-890,684,100,40))

    def test_journal_input_claim_precedes_the_actual_callback(self):
        ex,w,_=self.rig('call');click=w.click_once
        def inspect(*a,**kw):
            row=ex.journal.db.execute('SELECT state FROM claims').fetchone()
            self.assertEqual(row[0],'INPUT_STARTED');return click(*a,**kw)
        w.click_once=inspect
        self.assertEqual(ex.execute(w.scene())['state'],'DONE')

    def test_pause_during_durable_reservation_is_checked_again_before_mouse_down(self):
        ex,w,bot=self.rig('call');settle=ex.journal.settle
        def paused(decision,state,details):
            settle(decision,state,details)
            if state=='INPUT_STARTED':bot.running=False
        ex.journal.settle=paused
        out=ex.execute(w.scene())
        self.assertEqual(out['state'],'CANCELLED_BEFORE_INPUT');self.assertFalse(w.clicks)

    def test_duplicate_effect_capture_cannot_confirm_money_twice(self):
        ex,w,_=self.rig('bet');w.same_effect_capture=True
        def mutation(s):
            if w.sent:s['result']['table_state'].pop('confirmed_history',None)
        w.mutation=mutation
        out=ex.execute(w.scene())
        self.assertEqual(out['state'],'UNKNOWN_RESULT');self.assertFalse(out['confirmed'])

    def test_two_fresh_money_observations_confirm_own_action_even_if_opponent_model_is_missing(self):
        ex,w,_=self.rig('bet')
        def mutation(s):
            if w.sent:s['result']['table_state'].pop('confirmed_history',None)
        w.mutation=mutation
        out=ex.execute(w.scene())
        self.assertEqual(out['state'],'DONE',out)
        self.assertEqual(len(out['evidence']),2)
        self.assertEqual(out['evidence'][0]['kind'],'STACK_DROP_AND_POT_GROWTH')
        self.assertFalse(out['evidence'][0]['full_opponent_sequence_confirmed'])

    def test_natural_movement_interruption_preserves_manual_control(self):
        ex,w,_=self.rig('call');initial=w.scene();move=w.move_to
        def moved(*a,**kw):
            result=move(*a,**kw);w.pos=(0,0);return result
        w.move_to=moved
        out=ex.execute(initial)
        self.assertIn('USER_INTERVENTION',out['reason']);self.assertFalse(w.clicks)

    def test_model_may_allow_another_call_on_another_street(self):
        ex,w,_=self.rig('call');d=DecisionState(w.policy.context,w.state,HERO,'t','h1')
        different=replace(w.state,history=w.state.history+('0:call:5','BOARD:2h'))
        self.assertNotEqual(d.selection_id(),replace(d,betting=different).selection_id())


class LiveIntegrationTests(unittest.TestCase):
    def test_advisor_produces_timeline_without_an_external_strategy_state(self):
        import numpy as np
        import table_advisor
        p=make_test_policy();profile=OperationalProfile(p.fingerprint,require_preflop_witness=False)
        clock=Clock();h=ConfirmedHistory(p,profile,clock=clock)
        root=apply_action(p.root,Action('check'));raw,b=reading(root)
        crop=np.zeros((700,360,3),dtype=np.uint8)
        advisor=type('Unused',(),{'advise_from_reading':lambda *a,**kw:(_ for _ in ()).throw(AssertionError('legacy used'))})()
        for i in range(2):
            with patch('table_advisor.read_table_state',return_value=copy.deepcopy(raw['table_state'])), \
                 patch('table_advisor.read_hand_id',return_value=raw['hand']), \
                 patch('table_advisor.read_hero_card_slots',return_value=list(HERO)), \
                 patch('table_advisor.read_board',return_value=raw['board']), \
                 patch('table_advisor.read_tournament',return_value={}), \
                 patch('table_reading.table_state.read_fold_tags',return_value={}):
                out=table_advisor.advise_table(crop,advisor,mode='chip_ev',stage='mid',table_key='t',
                    history=h,buttons_result=b,sample_id=str(i),captured_at=clock(),
                    postflop_policy=PolicyObserver(p,profile))
        self.assertEqual(out['advice']['status'],'ADVICE')
        self.assertIn('operational',out['advice'])

    def test_runtime_uses_process_creation_time_and_physical_client_geometry(self):
        from hu_runtime import table_identity,scene_from_result
        result,b=reading(make_test_policy().root)
        meta=dict(hwnd=321,pid=9,process_created=100.,client_rect=(0,0,360,700),screen_origin=(-500,49),status='SUCCESS',dpi_effective=True)
        key=table_identity(meta,'0x0');other=table_identity(dict(meta,process_created=101.),'0x0')
        self.assertNotEqual(key,other)
        scene=scene_from_result(result,b,meta,(0,0,360,700),key,'capture-1',100.)
        self.assertEqual(screen_rect(scene,(10,630,100,40)),(-490,679,100,40))

    def test_private_card_memory_is_bound_to_a_fresh_same_hand_id(self):
        import numpy as np
        from table_advisor import advise_table
        p=make_test_policy();profile=OperationalProfile(p.fingerprint,require_preflop_witness=False)
        h=ConfirmedHistory(p,profile);state=apply_action(p.root,Action('check'))
        for i in range(2):
            raw,b=reading(state);h.observe(raw,table_id='t',buttons=b,sample_id=str(i))
        raw,b=reading(state)
        with patch('table_advisor.read_table_state',side_effect=lambda *a:copy.deepcopy(raw['table_state'])), \
             patch('table_advisor.read_hand_id',side_effect=[{'hand_id':'h1'},{'hand_id':'new'}]), \
             patch('table_advisor.read_hero_card_slots',return_value=[None,None]), \
             patch('table_advisor.read_board',return_value=raw['board']), \
             patch('table_advisor.read_tournament',return_value={}), \
             patch('table_reading.table_state.read_fold_tags',return_value={}):
            same=advise_table(np.zeros((700,360,3),dtype=np.uint8),None,history=h,table_key='t',
                mode='chip_ev',stage='mid',buttons_result=b,sample_id='same-hand',observation_only=True)
            new=advise_table(np.zeros((700,360,3),dtype=np.uint8),None,history=h,table_key='t',
                mode='chip_ev',stage='mid',buttons_result=b,sample_id='new-hand',observation_only=True)
        self.assertEqual(same['hero_cards'],list(HERO));self.assertEqual(same['hero_slots'],[None,None])
        self.assertIsNone(new['hero_cards'])

    def test_live_supplier_skips_lobby_and_keeps_only_a_bounded_panel_crop_lease(self):
        import numpy as np
        from types import SimpleNamespace
        from hu_runtime import LiveHUScenes
        from strategy.state_contract import StrategyError
        p=make_test_policy();profile=OperationalProfile(p.fingerprint)
        result,b=reading(p.root)
        frame=np.zeros((700,660,3),dtype=np.uint8);frame[:,300:]=100
        meta=dict(hwnd=321,pid=9,process_created=100.,client_rect=(0,0,660,700),screen_origin=(-1000,50),status='SUCCESS',dpi_effective=True)
        engine=type('Capture',(),{'capture_frame':lambda s,**kw:(frame,dict(meta))})()
        proposals=[SimpleNamespace(box=(0,0,280,700)),SimpleNamespace(box=(300,0,360,700))]
        supplier=LiveHUScenes(engine=engine,hwnd=321,crop_key='auto',advisor=None,history=None,
            policy_observer=None,profile=profile)
        with patch('hu_runtime.detect_table_crops',return_value=proposals), \
             patch('hu_runtime.find_buyin_badges',side_effect=lambda crop:['badge'] if crop[0,0,0]==0 else []), \
             patch('hu_runtime.read_action_buttons',return_value=b), \
             patch('hu_runtime.advise_table',return_value=result), \
             patch('hu_runtime.read_hero_card_slots',return_value=list(HERO)), \
             patch('hu_runtime.read_hand_id',return_value=result['hand']), \
             patch('hu_runtime.read_board',return_value=result['board']), \
             patch('hu_runtime.read_raise_panel',return_value=dict(status='EXPERIMENTAL_RAISE_PANEL',confirm=dict(box=[10,10,10,10]))), \
             patch('hu_runtime.read_selected_amount',return_value=dict(status='AMOUNT_CONFIRMED',value_bb=2.,unit='BB')):
            normal=supplier();supplier.bind(normal)
            self.assertTrue(normal['source_key'].endswith('3x0'))
            self.assertEqual(screen_rect(normal,(10,630,100,40)),(-690,680,100,40))
            with patch('hu_runtime.detect_table_crops',side_effect=AssertionError('felt hidden by modal')):
                panel=supplier(panel=True)
            self.assertEqual(panel['phase'],'panel')
            self.assertNotEqual(normal['sample_id'],panel['sample_id'])
            meta['process_created']=101.
            with self.assertRaisesRegex(StrategyError,'LEASE_GEOMETRY_CHANGED'):supplier(panel=True)


class KeyboardEntryTests(unittest.TestCase):
    def test_cancel_before_typing_sends_no_keyboard_input(self):
        from cursor_input_win import WindowsCursorInput
        calls=[]
        backend=type('Backend',(),{'keyboard':lambda s,events:calls.append(events) or len(events)})()
        out=WindowsCursorInput(_backend=backend).write_amount('12,345',cancel_check=lambda:True)
        self.assertFalse(out['ok']);self.assertEqual(calls,[])

    def test_partial_select_all_never_types_the_amount_and_releases_ctrl(self):
        from cursor_input_win import WindowsCursorInput
        calls=[]
        def keyboard(s,events):calls.append(events);return 1
        backend=type('Backend',(),{'keyboard':keyboard})()
        out=WindowsCursorInput(_backend=backend).write_amount('12,345')
        self.assertFalse(out['ok']);self.assertEqual(len(calls),2)
        self.assertEqual(calls[-1],[(0x11,0,2)])

    def test_numeric_entry_uses_unicode_and_does_not_press_enter(self):
        from cursor_input_win import WindowsCursorInput
        calls=[]
        backend=type('Backend',(),{'keyboard':lambda s,events:calls.append(events) or len(events)})()
        out=WindowsCursorInput(_backend=backend).write_amount('12,345')
        self.assertTrue(out['ok'])
        codes=[scan for events in calls for vk,scan,flags in events if flags==4]
        self.assertEqual(''.join(map(chr,codes)),'12,345')
        self.assertFalse(any(vk==13 for events in calls for vk,scan,flags in events))

    def test_non_numeric_text_does_not_reach_keyboard(self):
        from cursor_input_win import WindowsCursorInput,CursorInputError
        backend=type('Backend',(),{'keyboard':lambda s,events:(_ for _ in ()).throw(AssertionError('unexpected input'))})()
        with self.assertRaises(CursorInputError):WindowsCursorInput(_backend=backend).write_amount('12;raise')


if __name__=='__main__':unittest.main()
