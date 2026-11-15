"""One reproducible HU integration check; owned GUI is not PPPoker validation.

--lab runs synthetic integration and exports an auditable sample hand.
--windows-owned sends real SendInput only to a temporary Tk window owned here.
--observe-pppoker captures the requested HWND without any gameplay input.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import threading
import time
import unittest


def write_json(path,data):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    temporary=Path(str(path)+'.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temporary.replace(path)


def lab(output):
    # These are explicitly synthetic, small policies with invented frequencies.
    # No external solver or actual Windows app is used by this mode.
    from test_hu_operational import HistoryTests
    from strategy.action_tree import Action,apply_action
    from strategy.state_contract import reveal
    suite=unittest.defaultTestLoader.loadTestsFromName('test_hu_operational')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    sample=HistoryTests();sample.setUp()
    try:
        sample.witness()
        state=sample.policy.root
        sample.confirm(state)
        for next_card in ('Ts','2h',None):
            state=apply_action(state,Action('check'));sample.confirm(state)
            if next_card is None:
                state=apply_action(state,Action('check'));sample.confirm(state,payout=True)
            else:
                state=apply_action(state,Action('bet',state.pot_bb/2));sample.confirm(state)
                state=reveal(apply_action(state,Action('call',state.call_cost_bb)),next_card)
                sample.confirm(state)
        hand=sample.j.export_hand('t','h1')
        hand['validation_scope']='SYNTHETIC_PASSIVE_SNAPSHOTS_NOT_A_PLAYED_PPPOKER_HAND'
        hand['complete_to_showdown']=sample.h.current('t')['state'].terminal=='showdown'
        if not hand['complete_to_showdown']:
            raise RuntimeError('LAB_HAND_NOT_CONFIRMED_TO_SHOWDOWN')
        write_json(output/'mao-confirmada-laboratorio.json',hand)
        lines=['HISTORICO CONFIRMADO NO LABORATORIO',
               'Snapshots sinteticos; esta mao NAO foi jogada no PPPoker.',
               'Hero BTN As 5s; vilao BB. Board inicial Kc 8s 3d. Pote 5,5 BB; stacks 22,5/22,5 BB.',
               'A chegada preflop tem testemunho sintetico separado de blinds/open/call; nao e importacao HRC.']
        for event in hand['events']:
            value=event['payload']
            if value['event_type']=='action':
                lines.append('%s: %s; contribuicao MODELO %s BB; intervalo de exibicao %s BB.' %
                    (value['position'],value['action'],value['model_additional_bb'],value['compatible_amount_interval_bb']))
            elif value['event_type']=='board':lines.append('Carta publica confirmada: '+value['card'])
        lines.extend(['Final: showdown, pote 22 BB; cadeia de hashes verificada.',
                      'Precisao de exibicao 0,1 BB. Nao comprova lucro, ranges corretos ou cliques Windows.'])
        (output/'mao-confirmada-laboratorio.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    finally:
        sample.doCleanups()
    return dict(status='PASS' if result.wasSuccessful() else 'FAIL',scope='LINUX_OR_WINDOWS_SYNTHETIC_INTEGRATION',
        tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        pppoker_windows_validated=False)


def windows_owned(output):
    if os.name!='nt':
        return dict(status='NOT_RUN',reason='WINDOWS_REQUIRED',pppoker_windows_validated=False)
    import ctypes
    user32=ctypes.WinDLL('user32',use_last_error=True)
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    user32.GetThreadDpiAwarenessContext.restype=ctypes.c_void_p
    user32.GetAwarenessFromDpiAwarenessContext.argtypes=(ctypes.c_void_p,)
    if user32.GetAwarenessFromDpiAwarenessContext(user32.GetThreadDpiAwarenessContext())!=2:
        return dict(status='FAIL',reason='OWNED_GUI_REQUIRES_PHYSICAL_DPI_CONTEXT',pppoker_windows_validated=False)
    import io
    log=io.StringIO()
    native=unittest.TextTestRunner(stream=log,verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromName('test_capture_windows_native'))
    (output/'captura-janela-propria.txt').write_text(log.getvalue(),encoding='utf-8')
    if not native.wasSuccessful() or native.skipped:
        return dict(status='FAIL',reason='NATIVE_OWNED_CAPTURE_NOT_VALIDATED',pppoker_windows_validated=False)
    import tkinter as tk
    from cursor_input_win import WindowsCursorInput
    from bot_control import BotControl,HotkeyListener
    from hand_journal import HandJournal
    from hu_executor import HUExecutor
    from strategy.action_tree import Action,apply_action
    from strategy.confirmed_history import ConfirmedHistory
    from strategy.operational_profile import OperationalProfile
    from strategy.policy_observer import PolicyObserver
    from strategy.state_contract import BettingState
    from test_hu_operational import make_test_policy,reading,RIVER

    root=tk.Tk();root.title('Software - verificador HU (janela propria, sem PPPoker)')
    root.geometry('700x430+80+70')
    root.deiconify();root.lift();root.focus_force()
    control=BotControl();control.resume()
    listener=HotkeyListener(control);listener.start()
    adapter=WindowsCursorInput()
    journal=HandJournal(output/'historico-janelas-proprias.sqlite3')
    cases=[];world={};closed=threading.Event()
    tk.Label(root,text='Teste de entrada na janela propria\nCtrl+Alt+P pausa; fechar encerra.\nNao toque no mouse durante cada movimento.',font=('Arial',13)).place(x=20,y=10)
    status=tk.Label(root,text='Preparando...');status.place(x=20,y=95)
    buttons={name:tk.Button(root,text=name) for name in ('FOLD','CALL','CHECK','BET','RAISE')}
    entry=tk.Entry(root,font=('Arial',16));confirm=tk.Button(root,text='CONFIRMAR VALOR')
    action_boxes={'FOLD':(20,330,180,60),'CALL':(220,330,180,60),'CHECK':(220,330,180,60),
                  'BET':(450,330,200,60),'RAISE':(450,330,200,60)}
    field_box=(430,170,180,40);confirm_box=(450,330,200,60)

    def redraw():
        for b in buttons.values():b.place_forget()
        entry.place_forget();confirm.place_forget()
        if world.get('panel'):
            entry.place(x=field_box[0],y=field_box[1],width=field_box[2],height=field_box[3])
            confirm.place(x=confirm_box[0],y=confirm_box[1],width=confirm_box[2],height=confirm_box[3])
        elif world and not world['state'].terminal and world['state'].actor==0:
            names=('FOLD','CALL','RAISE') if world['state'].call_required_bb else ('FOLD','CHECK','BET')
            for name in names:
                x,y,w,h=action_boxes[name];buttons[name].place(x=x,y=y,width=w,height=h)
        root.update_idletasks()

    def callback(name):
        world['callbacks'].append(name)
        try:
            state=world['state']
            if name in ('BET','RAISE'):
                world['panel']=True;entry.delete(0,'end');entry.insert(0,'1,000')
            else:
                if name=='CONFIRM':
                    paid=float(entry.get().replace(',','.'))-state.committed[0]
                    kind='all_in' if abs(paid-state.stacks[0])<1e-8 else 'raise' if state.call_required_bb else 'bet'
                    action=Action(kind,paid)
                else:
                    action=Action(name.casefold(),state.call_cost_bb if name=='CALL' else 0)
                world['state']=apply_action(state,action);world['panel']=False
            redraw()
        except Exception as exc:
            world['callback_error']=str(exc)
    for name,b in buttons.items():b.configure(command=lambda name=name:callback(name))
    confirm.configure(command=lambda:callback('CONFIRM'))

    def ui(fn):
        ready=threading.Event();value=[]
        def invoke():
            try:value.append((True,fn()))
            except Exception as exc:value.append((False,exc))
            finally:ready.set()
        if closed.is_set():raise RuntimeError('OWNED_WINDOW_CLOSED')
        root.after(0,invoke)
        if not ready.wait(3):raise RuntimeError('OWNED_UI_READ_TIMEOUT')
        ok,result=value[0]
        if not ok:raise result
        return result

    def scene_ui():
        world['serial']+=1
        state=world['state']
        result,br=reading(state,hand=world['hand_id'],folded=['hero'] if state.terminal=='fold' else (),payout=True)
        result['observation_source']='OWNED_TK_WINDOWS_WIDGET_READBACK_NOT_PPPOKER_OCR'
        for button in br['buttons']:button['box']=list(action_boxes[button['action']])
        at=time.monotonic()
        if not world['panel']:
            world['history'].observe(result,table_id='owned-tk',buttons=br,sample_id=str(world['serial']),captured_at=at)
            if state.actor==0 and not state.terminal:
                result['advice']=world['observer'].advise(table_key='owned-tk',hand_key=world['hand_id'],
                    table_state=result['table_state'],hero_cards=result['hero_cards'],board=state.board,mode='chip_ev',stage='mid')
        s=dict(result=result,buttons=br,hwnd=root.winfo_id(),sample_id=str(world['serial']),captured_at=at,
            source_key='owned-tk',window_signature=(root.winfo_id(),os.getpid(),root.winfo_rootx(),root.winfo_rooty(),root.winfo_width(),root.winfo_height()),
            screen_origin=(root.winfo_rootx(),root.winfo_rooty()),crop_box=(0,0,root.winfo_width(),root.winfo_height()),
            phase='panel' if world['panel'] else 'normal',cards_fresh=True,board_fresh=True,
            source_kind='OWNED_TK_WINDOWS_WIDGET_READBACK_NOT_PPPOKER_OCR')
        if world['panel']:
            try:selected=dict(status='AMOUNT_CONFIRMED',value_bb=float(entry.get().replace(',','.')),quantum_bb=.001,box=list(field_box),unit='BB',semantics='RAISE_TO_BB')
            except ValueError:selected=dict(status='AMOUNT_UNREADABLE')
            s['panel']=dict(status='EXPERIMENTAL_RAISE_PANEL',presets=[],selected=selected,confirm=dict(box=list(confirm_box)))
        return s

    def run():
        try:
            for number,kind in enumerate(('check','call','fold','bet','raise','all_in')):
                if not control.execution_allowed():break
                state=BettingState(RIVER,10.,(30.,30.),actor=1,oop=1)
                state=apply_action(state,Action('bet',5.)) if kind in ('call','fold','raise') else apply_action(state,Action('check'))
                policy=make_test_policy(state,kind)
                profile=OperationalProfile(policy.fingerprint,require_preflop_witness=False,max_snapshot_age_s=3.)
                def setup():
                    world.clear();world.update(state=state,panel=False,serial=0,hand_id='owned-%d-%s'%(number,kind),callbacks=[],
                        history=ConfirmedHistory(policy,profile,journal),observer=PolicyObserver(policy,profile))
                    status.configure(text='Caso %s: input Windows real; estrategia sintetica'%kind);redraw()
                ui(setup)
                read=lambda **kw:ui(scene_ui)
                read();initial=read()
                executor=HUExecutor(policy=policy,profile=profile,journal=journal,input_adapter=adapter,
                    bot_control=control,scene_supplier=read,armed=True,deadline_s=15,effect_timeout_s=3.)
                out=executor.execute(initial)
                case=dict(kind=kind,result=out,callbacks=ui(lambda:list(world['callbacks'])),
                          selected_text=ui(entry.get))
                if out['state']!='DONE':
                    user32.GetForegroundWindow.restype=ctypes.c_void_p
                    user32.GetAncestor.argtypes=(ctypes.c_void_p,ctypes.c_uint)
                    user32.GetAncestor.restype=ctypes.c_void_p
                    case['focus_diagnostics']=ui(lambda:dict(requested=root.winfo_id(),
                        root=user32.GetAncestor(root.winfo_id(),2),foreground=user32.GetForegroundWindow()))
                cases.append(case)
                write_json(output/('mao-janela-propria-%s.json'%kind),journal.export_hand('owned-tk',world['hand_id']))
                if out['state']!='DONE':break
        except Exception as exc:
            cases.append(dict(status='ERROR',reason=str(exc)))
        finally:
            closed.set()
            try:root.after(0,root.destroy)
            except Exception:pass
    worker=threading.Thread(target=run,daemon=True)
    root.protocol('WM_DELETE_WINDOW',lambda:(control.pause(),closed.set(),root.destroy()))
    root.after(300,worker.start)
    try:root.mainloop();worker.join(timeout=5)
    finally:listener.stop();journal.close()
    return dict(status='PASS' if len(cases)==6 and all(c.get('result',{}).get('state')=='DONE' for c in cases) else 'FAIL',
        scope='WINDOWS_GDI_AND_SENDINPUT_OWNED_TK_ONLY',cases=cases,native_owned_capture='PASS',pppoker_windows_validated=False,
        limitation='Widget values are read directly. This does not validate PPPoker capture, card OCR, panel geometry or strategy.')


def observe_pppoker(args,output):
    if os.name!='nt':return dict(status='NOT_RUN',reason='WINDOWS_REQUIRED',pppoker_windows_validated=False)
    from hand_journal import HandJournal
    from hu_runtime import LiveHUScenes
    from position_stabilizer import PositionStabilizer
    from preflop_advisor import PreflopAdvisor
    from strategy.confirmed_history import ConfirmedHistory
    from strategy.operational_profile import OperationalProfile
    from strategy.policy_observer import PolicyObserver
    from strategy.policy_store import CompiledPolicy
    from table_reading.pipeline import configure_ocr
    from window_capture_engine import WindowCaptureEngine
    configure_ocr()
    policy=CompiledPolicy.load(args.policy)
    profile=OperationalProfile.load(args.profile,policy) if args.profile else OperationalProfile(policy.fingerprint)
    advisor=PreflopAdvisor.from_files(args.ranges,args.deep) if args.deep else PreflopAdvisor.from_file(args.ranges)
    journal=HandJournal(output/'observacao.sqlite3')
    history=ConfirmedHistory(policy,profile,journal)
    history.preflop_manifest=[{k:s[k] for k in ('sha256','nodes','validated')} for s in advisor.manifest()['sources']]
    read=LiveHUScenes(engine=WindowCaptureEngine(),hwnd=int(args.observe_pppoker,0),crop_key=args.crop_key,
        advisor=advisor,history=history,policy_observer=PolicyObserver(policy,profile),profile=profile,stabilizer=PositionStabilizer())
    diagnostics=[];identities=set();confirmed=0
    try:
        for _ in range(args.frames):
            try:
                scene=read();r=scene['result'];ts=r.get('table_state') or {};hc=ts.get('confirmed_history') or {}
                h=(r.get('hand') or {}).get('hand_id') or (r.get('hand') or {}).get('hand_number')
                if h:identities.add((scene['source_key'],str(h)))
                confirmed+=hc.get('status')=='CONFIRMED'
                row=dict(sample_id=scene['sample_id'],hand_id=h,hero=r.get('hero_cards'),board=(r.get('board') or {}).get('cards'),
                    history=hc,advice_status=(r.get('advice') or {}).get('status'),
                    policy_reason=((r.get('advice') or {}).get('hu_policy_diagnostic') or {}).get('reason'))
                print(json.dumps(row,ensure_ascii=False));diagnostics.append(row)
            except Exception as exc:
                diagnostics.append(dict(status='READ_ERROR',reason=str(exc)));print(str(exc))
            time.sleep(args.interval)
        for i,(table_id,hand_id) in enumerate(sorted(identities)):
            write_json(output/('mao-pppoker-%d.json'%i),journal.export_hand(table_id,hand_id))
    finally:journal.close()
    write_json(output/'observacao.json',diagnostics)
    return dict(status='OBSERVATION_COMPLETED',scope='PPPOKER_WINDOWS_PASSIVE_NO_INPUT',
        captures=len(diagnostics),confirmed_snapshots=confirmed,pppoker_windows_validated=False,
        limitation='Passive observation does not validate actual clicks or complete strategy coverage.')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument('--lab',action='store_true');modes.add_argument('--windows-owned',action='store_true')
    modes.add_argument('--observe-pppoker',metavar='HWND')
    p.add_argument('--policy');p.add_argument('--profile');p.add_argument('--ranges');p.add_argument('--deep')
    p.add_argument('--crop-key',default='auto');p.add_argument('--frames',type=int,default=60)
    p.add_argument('--interval',type=float,default=.5);p.add_argument('--output')
    args=p.parse_args(argv)
    if args.observe_pppoker and (not args.policy or not args.ranges):p.error('Observacao exige --policy e --ranges')
    if not 1<=args.frames<=600 or not .1<=args.interval<=10:p.error('Use 1..600 capturas e intervalo .1..10 s')
    output=Path(args.output or ('runtime/hu/verificacao-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')))
    output.mkdir(parents=True,exist_ok=True)
    report=dict(schema='software.hu-executor-check.v1',platform=platform.platform(),python=platform.python_version(),
                report_path=str((output/'resultado.json').resolve()))
    try:report.update(lab(output) if args.lab else windows_owned(output) if args.windows_owned else observe_pppoker(args,output))
    except Exception as exc:report.update(status='ERROR',reason=str(exc),pppoker_windows_validated=False)
    write_json(output/'resultado.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['status'] in ('PASS','OBSERVATION_COMPLETED') else 2


if __name__=='__main__':raise SystemExit(main())
