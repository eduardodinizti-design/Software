"""Operational HU transaction: fresh decision -> input -> observed effect.

The scene supplier owns capture/OCR and never sends input. This module owns
input, a shared cursor transaction, persistent deduplication and verification.
Reference strategy authority is separate from a solver/Windows certification.
"""
import time
import math
import sqlite3

from cursor_controller import CursorController, Intent, _CURSOR_LOCK, make_intervention_check
from strategy.action_tree import Action, is_legal
from strategy.operational_profile import compatible, interval
from strategy.state_contract import DecisionState, StrategyError, digest
from strategy.strategy_decision import choose


def hand_id(scene):
    hand = (scene.get('result') or {}).get('hand') or {}
    value = hand.get('hand_id') or hand.get('hand_number')
    return str(value) if value is not None else None


def screen_rect(scene, box):
    sx, sy = scene['screen_origin']
    cx, cy, _, _ = scene['crop_box']
    x, y, w, h = box
    return (sx + cx + x, sy + cy + y, w, h)


class _ClaimingInput:
    def __init__(self, adapter, journal, decision_id, clock, guard):
        self.adapter, self.journal, self.decision_id, self.clock = adapter, journal, decision_id, clock
        self.maybe_sent = False
        self.last_input_at = float('inf')
        self.guard = guard

    def __getattr__(self, name):
        return getattr(self.adapter, name)

    def click_once(self, *args, **kwargs):
        # Persist BEFORE mouse-down. A crash after this point is never retried.
        self.journal.settle(self.decision_id, 'INPUT_STARTED', {'stage': 'before_mouse_down'})
        if not self.guard():
            raise StrategyError('HU_GATE_CHANGED_BEFORE_MOUSE_DOWN')
        if len(args)>=2 and args[0] is not None and args[1] is not None:
            x,y = self.adapter.cursor_pos()
            if abs(x-args[0])>8 or abs(y-args[1])>8:
                raise StrategyError('HU_USER_INTERVENTION_BEFORE_MOUSE_DOWN')
        self.maybe_sent = True
        self.last_input_at = self.clock()
        return self.adapter.click_once(*args, **kwargs)


class HUExecutor:
    def __init__(self, *, policy, profile, journal, input_adapter, bot_control,
                 scene_supplier, armed=False, clock=time.monotonic, sleep=time.sleep,
                 deadline_s=8.0, effect_timeout_s=2.5):
        profile.check_policy(policy)
        self.policy, self.profile, self.journal = policy, profile, journal
        self.input, self.bot, self.read = input_adapter, bot_control, scene_supplier
        self.armed, self.clock, self.sleep = bool(armed), clock, sleep
        self.deadline_s, self.effect_timeout_s = deadline_s, effect_timeout_s
        self.stages = []

    def _running(self):
        return self.bot is not None and self.bot.execution_allowed()

    def _fresh(self, scene):
        now = self.clock()
        at = (scene or {}).get('captured_at', -1e9)
        if not isinstance(at, (float, int)) or not math.isfinite(at) or not -.001 <= now-at <= self.profile.max_snapshot_age_s:
            raise StrategyError('HU_STALE_OR_MISSING_CAPTURE')
        if not scene.get('source_key') or not scene.get('sample_id'):
            raise StrategyError('HU_CAPTURE_IDENTITY_MISSING')

    def _decision(self, scene):
        self._fresh(scene)
        result = scene['result']
        state = result.get('table_state') or {}
        payload = state.get('strategy_state')
        advice = result.get('advice') or {}
        if payload is None or advice.get('status') != 'ADVICE' or advice.get('phase') != 'postflop':
            raise StrategyError('HU_CONFIRMED_DECISION_MISSING')
        if advice.get('policy_sha256') != self.policy.fingerprint:
            raise StrategyError('HU_POLICY_IDENTITY_CHANGED')
        op = advice.get('operational') or {}
        if op.get('profile_sha256') != self.profile.fingerprint:
            raise StrategyError('HU_OPERATIONAL_AUTHORITY_MISSING')
        if (state.get('confirmed_history') or {}).get('status') != 'CONFIRMED':
            raise StrategyError('HU_HISTORY_NOT_CONFIRMED')
        d = DecisionState.from_dict(payload)
        expected_advice = choose(self.policy,d)
        if advice.get('selection_id') != d.selection_id() or advice.get('action_id') != expected_advice['action_id']:
            raise StrategyError('HU_SELECTION_CHANGED_FROM_COMPILED_POLICY')
        if hand_id(scene) != str(d.hand_id):
            raise StrategyError('HU_CURRENT_HAND_MISMATCH')
        if self.policy.node_key(d.betting) != advice.get('node_id'):
            raise StrategyError('HU_DECISION_NODE_MISMATCH')
        chosen = next((a for a in self.policy.actions(d.betting) if a.id == advice.get('action_id')), None)
        if chosen is None or chosen.kind != advice.get('recommended') or not is_legal(d.betting, chosen):
            raise StrategyError('HU_ACTION_NOT_IN_POLICY_OR_ILLEGAL')
        if abs((advice.get('sizing') or {}).get('size_bb', -1) - chosen.amount_bb) > 1e-8:
            raise StrategyError('HU_ADVICE_SIZE_CHANGED')
        if scene.get('buttons', {}).get('status') != 'EXPERIMENTAL_BUTTON_ROW':
            raise StrategyError('HU_NO_CURRENT_ACTION_ROW')
        return d, chosen

    def _same(self, scene, initial, d, *, panel=False):
        self._fresh(scene)
        if scene['source_key'] != initial['source_key'] or tuple(scene['window_signature']) != tuple(initial['window_signature']):
            raise StrategyError('HU_WINDOW_PROCESS_OR_GEOMETRY_CHANGED')
        if not self.input.is_foreground(scene['hwnd']):
            raise StrategyError('HU_TARGET_NOT_FOREGROUND')
        observed_hand = hand_id(scene)
        if observed_hand is not None and observed_hand != str(d.hand_id):
            raise StrategyError('HU_HAND_CHANGED')
        if panel:
            # Bounded modal lease. Do not falsely label a hidden ID as re-read.
            # Fresh private/public cards and the same live panel are mandatory.
            result = scene.get('result') or {}
            if (not scene.get('cards_fresh') or set(result.get('hero_cards') or ()) != set(d.hero_cards)
                    or not scene.get('board_fresh')):
                raise StrategyError('HU_PANEL_CARD_IDENTITY_UNREADABLE')
            board = tuple((result.get('board') or {}).get('cards') or ())
            if set(board[:3]) != set(d.betting.board[:3]) or board[3:] != d.betting.board[3:]:
                raise StrategyError('HU_BOARD_CHANGED_WITH_PANEL_OPEN')
            if (scene.get('panel') or {}).get('status') != 'EXPERIMENTAL_RAISE_PANEL':
                raise StrategyError('HU_PANEL_DISAPPEARED')
            scene['hand_identity_evidence'] = 'FRESH_ID' if observed_hand else 'BOUNDED_PANEL_LEASE_WITH_FRESH_CARDS'
        else:
            current, _ = self._decision(scene)
            if current.selection_id() != d.selection_id():
                raise StrategyError('HU_PUBLIC_STATE_OR_PRICE_CHANGED')

    def _button(self, scene, action):
        key = action.kind.upper()
        if key == 'ALL_IN':
            key = 'RAISE' if action.kind == 'all_in' else key
        buttons = scene.get('buttons', {}).get('buttons') or []
        aliases = (key, 'BET') if key == 'RAISE' else (key, 'RAISE') if key == 'BET' else (key,)
        button = next((b for a in aliases for b in buttons if b.get('action') == a), None)
        if button is None:
            raise StrategyError('HU_ACTION_BUTTON_MISSING:' + key)
        return button

    def _step(self, name, target, *, initial, decision, panel, deadline, adapter, verifier):
        signature = digest([initial['source_key'], decision.selection_id(), name])
        started = self.clock()
        validations = []

        def validate(intent, now):
            try:
                current = self.read(panel=panel)
                self._same(current, initial, decision, panel=panel)
                box = target(current)
                validations.append(dict(sample_id=current['sample_id'],captured_at=current['captured_at'],
                    identity_evidence=current.get('hand_identity_evidence','FRESH_ID_AND_CONFIRMED_PUBLIC_STATE'),
                    selected_amount=(current.get('panel') or {}).get('selected')))
                return dict(ok=True, identity=signature, target_rect=screen_rect(current, box))
            except (StrategyError, KeyError, TypeError, ValueError) as exc:
                return dict(ok=False, reasons=[str(exc)])

        intervention = make_intervention_check(adapter)

        def cancel(intent, now, expected_pos):
            if not adapter.is_foreground(initial['hwnd']):
                return 'HU_FOCUS_LOST'
            return intervention(intent, now, expected_pos)

        intent = Intent(id=signature, action='HU_' + name, source_key=signature,
                        target_rect=(0, 0, 1, 1), deadline=deadline, hand=decision.hand_id,
                        snapshot_id=initial['sample_id'])
        controller = CursorController(input_adapter=adapter, validator=validate,
                                      verifier=verifier, bot_control=self.bot, clock=self.clock,
                                      sleep=self.sleep, cancel_check=cancel)
        out = controller.execute(intent)
        self.stages.append(dict(step=name, state=out['state'], reasons=out.get('reasons', []),
                                elapsed_ms=(self.clock()-started)*1000,validations=validations,
                                controller_log=out.get('log',[])))
        if out['state'] != 'DONE':
            raise StrategyError('HU_%s_%s:%s' % (name, out['state'], ','.join(out.get('reasons', ()))))

    def _effect(self, before, after, d, action):
        if not after or after.get('sample_id') == before['sample_id'] or after.get('phase') == 'panel':
            return None
        if after.get('source_key') != before['source_key'] or hand_id(after) != str(d.hand_id):
            return None
        if tuple(after.get('window_signature', ())) != tuple(before.get('window_signature', ())):
            return None
        try:
            self._fresh(after)
        except StrategyError:
            return None
        result = after.get('result') or {}
        ts = result.get('table_state') or {}
        history = ts.get('confirmed_history') or {}
        model = history.get('model_state') or {}
        prefix = tuple(model.get('history') or ())
        previous = d.betting.history
        expected = '0:' + action.id
        if (history.get('status') == 'CONFIRMED' and prefix[:len(previous)] == previous
                and len(prefix) > len(previous) and prefix[len(previous)] == expected):
            return dict(kind='CONFIRMED_HISTORY_TRANSITION', sample_id=after['sample_id'],
                        revision=history.get('revision'), public_history=list(prefix))
        # Independent chip evidence can establish our own input even if the
        # opponent chose a size outside the stored policy. No future range is invented.
        if action.amount_bb <= 0:
            return None
        b = before['result']['table_state']
        fields = [b.get('pot') or {}, ts.get('pot') or {},
                  (b.get('seats') or {}).get('hero') or {}, (ts.get('seats') or {}).get('hero') or {}]
        if any(f.get('confidence') != 'high' for f in fields):
            return None
        p0, p1 = fields[0].get('pot_bb'), fields[1].get('pot_bb')
        s0, s1 = fields[2].get('stack_bb'), fields[3].get('stack_bb')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (p0,p1,s0,s1)):
            return None
        cost = s0-s1
        q = self.profile.quantum_bb
        if not compatible(cost, action.amount_bb, q*2) or p1-p0 < cost-q:
            return None
        changed_board = (result.get('board') or {}).get('cards') != list(d.betting.board)
        row_gone = after.get('buttons', {}).get('status') in ('NO_BUTTON_ROW', 'PRESELECTION_ROW')
        if not changed_board and not row_gone:
            return None
        return dict(kind='STACK_DROP_AND_POT_GROWTH', sample_id=after['sample_id'],
                    observed_hero_cost_interval_bb=interval(cost,q*2),
                    observed_pot_growth_bb=p1-p0, full_opponent_sequence_confirmed=False)

    def execute(self, initial):
        self.stages = []
        claimed, adapter, decision_id = False, None, None
        try:
            d, action = self._decision(initial)
            decision_id = digest([initial['source_key'], d.selection_id(), action.id, self.policy.fingerprint])
            plan = dict(action=action.kind, additional_bb=action.amount_bb,
                        raise_to_bb=d.betting.committed[0]+action.amount_bb,
                        decision_id=decision_id, authority='COMPILED_HU_REFERENCE',
                        strategy_certified_for_windows=False,basis_capture_id=initial['sample_id'],
                        model_state_sha256=d.betting.key(),profile_sha256=self.profile.fingerprint)
            if not self.armed:
                return dict(state='DRY_RUN', acted=False, confirmed=False, dry_run=True, plan=plan)
            if not self._running():
                raise StrategyError('HU_BOT_NOT_RUNNING')
            if self.journal is None:
                raise StrategyError('HU_DURABLE_JOURNAL_REQUIRED')
            claimed = self.journal.claim(d.table_id,d.hand_id,decision_id,plan)
            if not claimed:
                raise StrategyError('HU_DECISION_ALREADY_RESERVED_OR_SENT')
            advice = initial['result']['advice']
            payload = initial['result']['table_state']['strategy_state']
            self.journal.append(d.table_id,d.hand_id,'decision:'+decision_id,
                dict(event_type='decision_evidence',selection_id=d.selection_id(),
                     model_state_sha256=d.betting.key(),policy_sha256=self.policy.fingerprint,
                     profile_sha256=self.profile.fingerprint,hero_cards=list(d.hero_cards),
                     selected_action=action.id,candidates=advice.get('candidates'),
                     prior_range_sha256=payload.get('range_sha256'),
                     posterior_sha256=payload.get('posterior_sha256'),
                     authority='COMPILED_HU_REFERENCE',strategy_certified_for_windows=False))
            deadline = self.clock()+self.deadline_s
            adapter = _ClaimingInput(self.input,self.journal,decision_id,self.clock,
                lambda:self._running() and self.clock()<deadline and self.input.is_foreground(initial['hwnd']))
            acquired = _CURSOR_LOCK.acquire(timeout=2)
            if not acquired:
                raise StrategyError('HU_CURSOR_TRANSACTION_BUSY')
            try:
                if not self._running():
                    raise StrategyError('HU_BOT_NOT_RUNNING')
                if not adapter.activate_window(initial['hwnd']):
                    raise StrategyError('HU_CANNOT_FOCUS_TARGET_WINDOW')
                self._same(self.read(panel=False),initial,d,panel=False)
                evidence = []
                evidence_samples = set()

                def verify_effect(intent, now):
                    until = min(deadline, self.clock()+self.effect_timeout_s)
                    while self.clock() < until:
                        after = self.read(panel=False)
                        proof = self._effect(initial,after,d,action) if after.get('captured_at', 0) >= adapter.last_input_at else None
                        if proof:
                            if proof['sample_id'] in evidence_samples:
                                self.sleep(.05)
                                continue
                            evidence_samples.add(proof['sample_id'])
                            evidence.append(proof)
                            if proof['kind']=='CONFIRMED_HISTORY_TRANSITION' or len(evidence)>=self.profile.confirmations:
                                return dict(confirmed=True)
                        else:
                            evidence.clear()
                            evidence_samples.clear()
                        self.sleep(.05)
                    return dict(confirmed=False)

                if action.kind in ('fold','check','call'):
                    self._step('ACTION',lambda s:self._button(s,action)['box'],initial=initial,
                               decision=d,panel=False,deadline=deadline,adapter=adapter,verifier=verify_effect)
                else:
                    self._step('OPEN',lambda s:self._button(s,action)['box'],initial=initial,
                               decision=d,panel=False,deadline=deadline,adapter=adapter,
                               verifier=lambda i,n:dict(confirmed=(self.read(panel=True).get('panel') or {}).get('status')=='EXPERIMENTAL_RAISE_PANEL'))
                    panel_scene = self.read(panel=True)
                    self._same(panel_scene,initial,d,panel=True)
                    target = d.betting.committed[0]+action.amount_bb

                    def preset_target(scene):
                        presets = scene['panel'].get('presets') or []
                        fraction = action.amount_bb/d.betting.pot_bb if action.kind=='bet' else (action.amount_bb-d.betting.call_required_bb)/(d.betting.pot_bb+d.betting.call_required_bb)
                        p = next((p for p in presets if (action.kind=='all_in' and p.get('basis')=='all_in')
                                  or (action.kind!='all_in' and p.get('basis')=='pot' and abs(p.get('fraction',-1)-fraction)<.005)),None)
                        if p is None:
                            raise StrategyError('HU_NO_MATCHING_POT_PRESET')
                        return p['box']

                    try:
                        preset_target(panel_scene)
                        use_preset = True
                    except StrategyError:
                        use_preset = False
                    if use_preset:
                        self._step('PRESET',preset_target,initial=initial,decision=d,panel=True,
                                   deadline=deadline,adapter=adapter,verifier=lambda i,n:dict(confirmed=True))
                    else:
                        def field(scene):
                            selected = scene['panel'].get('selected') or {}
                            if selected.get('status')!='AMOUNT_CONFIRMED':
                                raise StrategyError('HU_AMOUNT_FIELD_UNREADABLE')
                            return selected['box']
                        self._step('AMOUNT_FIELD',field,initial=initial,decision=d,panel=True,
                                   deadline=deadline,adapter=adapter,verifier=lambda i,n:dict(confirmed=True))
                        text = ('%.*f' % (self.profile.amount_decimals,target)).replace('.',self.profile.decimal_separator)
                        typed = adapter.write_amount(text,cancel_check=lambda:not self._running() or self.clock()>=deadline or not adapter.is_foreground(initial['hwnd']))
                        if not typed.get('ok'):
                            raise StrategyError('HU_AMOUNT_ENTRY_NOT_ACCEPTED')

                    def confirm(scene):
                        selected = scene['panel'].get('selected') or {}
                        value, quantum = selected.get('value_bb'), selected.get('quantum_bb')
                        if selected.get('status')!='AMOUNT_CONFIRMED' or quantum is None:
                            raise StrategyError('HU_SELECTED_AMOUNT_UNREADABLE')
                        if selected.get('unit')!='BB' or selected.get('semantics')!='RAISE_TO_BB':
                            raise StrategyError('HU_SELECTED_AMOUNT_UNIT_OR_SEMANTICS_UNKNOWN')
                        if quantum/2 > self.profile.max_size_error_bb+1e-8 or not compatible(value,target,quantum):
                            raise StrategyError('HU_SELECTED_AMOUNT_DIFFERS_FROM_PLAN')
                        return scene['panel']['confirm']['box']
                    # Keyboard/preset events enter a GUI queue. Accepted input
                    # does not mean that its displayed value has updated yet.
                    # Poll read-only; never retype or repeat a click on a timeout.
                    until = min(deadline,self.clock()+1.0)
                    amount_ready = False
                    amount_error = None
                    while self.clock()<until:
                        if not self._running():
                            raise StrategyError('HU_BOT_NOT_RUNNING')
                        current = self.read(panel=True)
                        self._same(current,initial,d,panel=True)
                        try:
                            confirm(current)
                            amount_ready = True
                            break
                        except StrategyError as exc:
                            amount_error = str(exc)
                        self.sleep(.02)
                    if not amount_ready:
                        raise StrategyError(amount_error or 'HU_SELECTED_AMOUNT_UPDATE_TIMEOUT')
                    self._step('CONFIRM',confirm,initial=initial,decision=d,panel=True,
                               deadline=deadline,adapter=adapter,verifier=verify_effect)
                self.journal.append(d.table_id,d.hand_id,'execution:'+decision_id,
                    dict(event_type='execution_confirmed',plan=plan,evidence=evidence,
                         source_kind=initial.get('source_kind', 'UNSPECIFIED'),
                         input_backend=type(self.input).__name__,
                         strategy_certified_for_windows=False))
                self.journal.settle(decision_id,'CONFIRMED',dict(plan=plan,evidence=evidence))
                return dict(state='DONE',acted=True,confirmed=True,dry_run=False,plan=plan,
                            stages=self.stages,evidence=evidence)
            finally:
                _CURSOR_LOCK.release()
        except (StrategyError,ValueError,KeyError,TypeError,RuntimeError,OSError,sqlite3.Error) as exc:
            maybe_sent = bool(adapter and adapter.maybe_sent)
            status = 'UNKNOWN_RESULT' if maybe_sent else 'CANCELLED_BEFORE_INPUT'
            if claimed:
                try:
                    self.journal.settle(decision_id,status,dict(reason=str(exc),stages=self.stages))
                except (sqlite3.Error, ValueError, OSError) as write_error:
                    return dict(state='UNKNOWN_RESULT', acted=maybe_sent, confirmed=False,
                                reason='JOURNAL_FINALIZATION_FAILED:' + str(write_error),
                                original_reason=str(exc), stages=self.stages)
            return dict(state=status,acted=maybe_sent,
                        confirmed=False,dry_run=not self.armed,reason=str(exc),stages=self.stages)
