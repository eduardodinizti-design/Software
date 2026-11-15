"""Confirmed HU history from consecutive passive observations and legal paths.

Amounts retain the reader's rounding interval. A compatible compiled amount is
a MODEL value, never reported as exact observed chips. More than one semantic
path, OCR failures, stale/duplicate captures and gaps remain explicit.
"""
from collections import deque
from dataclasses import asdict, replace
import copy
import time

from strategy.action_tree import Action, apply_action, is_legal
from strategy.line_policy import LinePolicy
from strategy.operational_profile import compatible, interval
from strategy.state_contract import BettingState, DecisionState, StrategyError, digest, reveal


def _number(field, key):
    if not isinstance(field, dict) or field.get('confidence') != 'high':
        return None
    value = field.get(key)
    return value if compatible(value, value) else None


class ConfirmedHistory:
    def __init__(self, policy, profile, journal=None, *, clock=time.monotonic):
        profile.check_policy(policy)
        self.policy, self.profile, self.journal, self.clock = policy, profile, journal, clock
        self._hands = {}
        self.preflop_manifest = None

    def _entry(self, table_id, hand_id):
        previous = self._hands.get(table_id)
        if previous is not None and previous['hand_id'] != str(hand_id):
            if self.journal:
                self.journal.close_hand(table_id, previous['hand_id'])
            previous = None
        if previous is None:
            previous = dict(hand_id=str(hand_id), preflop=deque(maxlen=128), state=None,
                            line=None, revision=0, last_sample=None, candidate=None, repeats=0,
                            last_seen=None, trace=[], status='PENDING', reason='WAITING_FOR_ROOT')
            previous['candidate_evidence'] = []
            previous['reported_gaps'] = set()
            if self.journal:
                saved = self.journal.last_state(table_id, hand_id)
                previous['reported_gaps'] = {e['event_id'] for e in self.journal.events(table_id,hand_id)
                                              if e['payload'].get('event_type')=='observation_gap'}
                if saved and saved.get('policy_sha256') == self.policy.fingerprint:
                    if saved.get('profile_sha256') != self.profile.fingerprint:
                        raise StrategyError('JOURNAL_OPERATIONAL_PROFILE_CHANGED')
                    self.journal.export_hand(table_id, hand_id)  # verify the chain before trusting it
                    line = LinePolicy(self.policy)
                    state = BettingState.from_dict(saved['state'])
                    for text in state.history[len(self.policy.root.history):]:
                        if text.startswith('BOARD:'):
                            if line is not None:
                                try:
                                    line.reveal(text.split(':', 1)[1])
                                except StrategyError:
                                    line = None
                        else:
                            actor, kind, paid = text.split(':')
                            if line is not None and int(actor) != line.state.actor:
                                raise StrategyError('JOURNAL_ACTOR_SEQUENCE_CORRUPTED')
                            if line is not None:
                                try:
                                    line.observe(Action(kind, float(paid)))
                                except StrategyError:
                                    line = None
                    if line is not None and line.state.key() != state.key():
                        raise StrategyError('JOURNAL_MODEL_STATE_CORRUPTED')
                    previous.update(state=state, line=line, hero=tuple(saved['hero']),
                                    roles=tuple(saved['roles']), witness=saved['witness'],
                                    positions=saved.get('positions'),outside_stacks=saved.get('outside_stacks',{}),
                                    revision=saved['revision'], status='CONFIRMED')
        self._hands[table_id] = previous
        return previous

    def _snapshot(self, result, buttons, sample_id, captured_at):
        state = result.get('table_state') or {}
        hero = result.get('hero_cards')
        board = (result.get('board') or {}).get('cards')
        if not isinstance(board, list):
            board = list(board or ())
        positions = state.get('positions') or {}
        seats = state.get('seats') or {}
        stacks = {seat: _number(value, 'stack_bb') for seat, value in seats.items() if value.get('occupied')}
        pot = _number(state.get('pot'), 'pot_bb')
        bets = {b.get('seat'): b.get('bet_bb') for b in state.get('bets', ())
                if _number(b, 'bet_bb') is not None}
        row = (buttons or {}).get('status')
        actions = {b.get('action') for b in (buttons or {}).get('buttons', ()) if b.get('action')}
        if row not in ('EXPERIMENTAL_BUTTON_ROW', 'NO_BUTTON_ROW', 'PRESELECTION_ROW'):
            raise StrategyError('HISTORY_ACTION_ROW_UNREADABLE')
        if row == 'EXPERIMENTAL_BUTTON_ROW' and not ({'CHECK', 'CALL'} & actions):
            raise StrategyError('HISTORY_PRICE_BUTTON_UNREADABLE')
        if pot is None or not positions or any(v is None for v in stacks.values()):
            raise StrategyError('HISTORY_REQUIRES_CONFIDENT_POT_STACKS_POSITIONS')
        if not stacks or set(stacks) != set(positions):
            raise StrategyError('HISTORY_PARTICIPANTS_PARTIALLY_READ')
        price = _number(state.get('to_call'), 'to_call_bb')
        if row == 'EXPERIMENTAL_BUTTON_ROW' and price is None:
            raise StrategyError('HISTORY_PRICE_UNREADABLE')
        if not self.profile.pot_includes_bets:
            if state.get('bets_complete') is not True:
                raise StrategyError('HISTORY_UNSETTLED_POT_NEEDS_COMPLETE_BET_READ')
            pot += sum(bets.values())
        return dict(sample_id=str(sample_id), captured_at=captured_at, board=tuple(board),
                    hero=tuple(hero or ()), positions=dict(positions), stacks=stacks, pot=pot,
                    bets=bets, bets_complete=state.get('bets_complete', False), price=price,
                    hero_turn=row == 'EXPERIMENTAL_BUTTON_ROW', actions=actions,
                    folded={s for s, value in seats.items() if value.get('in_hand') is False
                            and value.get('in_hand_confidence') == 'high'},
                    mode=(result.get('context') or {}).get('mode'),
                    stage=(result.get('context') or {}).get('stage'))

    def _actors(self, snap):
        if snap['positions'].get('hero') != self.policy.context.positions[0]:
            raise StrategyError('HISTORY_HERO_POSITION_MISMATCH')
        villains = [s for s, p in snap['positions'].items() if p == self.policy.context.positions[1] and s != 'hero']
        if len(villains) != 1:
            raise StrategyError('HISTORY_VILLAIN_POSITION_MISSING')
        return ('hero', villains[0])

    def _witness(self, entry, snap):
        if not self.profile.require_preflop_witness:
            return dict(kind='EXPLICIT_TEST_ROOT', scope='controlled test only; preflop not observed')
        recipe = self.profile.recipe(self.policy)
        roles = self._actors(snap)
        if len(snap['positions']) != self.policy.context.dealt_players:
            raise StrategyError('HISTORY_ORIGINAL_DEALT_PLAYERS_UNCONFIRMED')
        # Baseline posts and opener are separately OBSERVED, not reconstructed
        # from a range name. Other callers/limpers/all-ins cannot disappear.
        for i, base in enumerate(entry['preflop']):
            if base['positions'] != snap['positions'] or base['hero'] != snap['hero']:
                continue
            if not base['bets_complete'] or not compatible(base['pot'], recipe['forced_pot_bb'], self.profile.quantum_bb):
                continue
            posted = {s: recipe['posts'].get(p, 0.0) for s, p in base['positions'].items()}
            if any(not compatible(base['bets'].get(s, 0), v, self.profile.quantum_bb) for s, v in posted.items()):
                continue
            if any(s not in roles and base['stacks'][s] + posted[s] < recipe['open_to_bb'] + self.profile.quantum_bb
                   and s not in snap['folded'] for s in base['stacks']):
                continue  # rounding can hide a tiny outside all-in: require an explicit fold
            opener = roles[self.profile.preflop_aggressor]
            caller = roles[1 - self.profile.preflop_aggressor]
            for opened in list(entry['preflop'])[i + 1:]:
                if opened['positions'] != base['positions'] or not opened['bets_complete']:
                    continue
                if not compatible(opened['bets'].get(opener), recipe['open_to_bb'], self.profile.quantum_bb):
                    continue
                if not compatible(opened['bets'].get(caller, 0), posted[caller], self.profile.quantum_bb):
                    continue
                expected_open_pot = base['pot'] + recipe['open_to_bb'] - posted[opener]
                if not compatible(opened['pot'], expected_open_pot, self.profile.quantum_bb * 2):
                    continue
                if opened['hero'] != base['hero']:
                    continue
                if any(not compatible(opened['bets'].get(s,0), recipe['open_to_bb'] if s==opener else posted[s], self.profile.quantum_bb)
                       for s in posted):
                    continue
                if any(not compatible(opened['stacks'].get(s), base['stacks'][s]-(recipe['open_to_bb']-posted[s] if s==opener else 0),
                                      self.profile.quantum_bb*2) for s in posted):
                    continue
                good = True
                for seat, initial in base['stacks'].items():
                    paid = recipe['open_to_bb'] - posted[seat] if seat in roles else 0
                    if not compatible(snap['stacks'].get(seat), initial - paid, self.profile.quantum_bb * 2):
                        good = False
                if good:
                    return dict(kind='OBSERVED_SRP_BASELINE_OPEN_AND_FLOP_CONSERVATION',
                                baseline_sample=base['sample_id'], opener_sample=opened['sample_id'],
                                recipe=recipe, active_seats=list(roles),
                                evidence=[{k:frame[k] for k in ('sample_id','captured_at','positions','stacks','pot','bets','bets_complete')}
                                          for frame in (base,opened,snap)],
                                amount_precision_bb=self.profile.quantum_bb,
                                note='Other players did not match the observed open; positive-stack conservation plus flop excludes them.')
        raise StrategyError('HISTORY_PREFLOP_ARRIVAL_NOT_CONFIRMED')

    def _matches(self, state, snap, roles):
        if set(state.board[:3]) != set(snap['board'][:3]) or state.board[3:] != snap['board'][3:]:
            return False
        q = self.profile.quantum_bb
        if state.terminal == 'showdown':
            gains = [snap['stacks'].get(s, -1) - state.stacks[i] for i, s in enumerate(roles)]
            # HU has a winner or an equal split (uncalled excess was already
            # refunded). Arbitrary allocations would falsely fit missed bets.
            outcomes = ((state.pot_bb,0.),(0.,state.pot_bb),(state.pot_bb/2,state.pot_bb/2))
            pot_compatible = compatible(snap['pot'],0.,q) or compatible(snap['pot'],state.pot_bb,q)
            return (not snap['hero_turn'] and pot_compatible
                    and any(all(abs(g-p)<=q+1e-8 for g,p in zip(gains,outcome)) for outcome in outcomes))
        if not compatible(snap['pot'], state.pot_bb, q):
            return False
        if any(not compatible(snap['stacks'].get(s), state.stacks[i], q) for i, s in enumerate(roles)):
            return False
        if state.terminal == 'fold':
            return roles[1 - state.winner] in snap['folded'] and not snap['hero_turn']
        if state.terminal:
            return False
        if state.needs_cards:
            return False  # wait for the actual next card before confirming a closed round
        if snap['hero_turn'] != (state.actor == 0):
            return False
        if state.actor == 0:
            if state.call_required_bb > 1e-8:
                if 'CALL' not in snap['actions'] or not compatible(snap['price'], state.call_cost_bb, q):
                    return False
            elif 'CHECK' not in snap['actions']:
                return False
        for i, s in enumerate(roles):
            if s in snap['bets'] and not compatible(snap['bets'][s], state.committed[i], q):
                return False
        return True

    def _paths(self, start, snap, roles):
        queue = deque([(start, (), 0)])
        matches, visited, count = [], set(), 0
        while queue:
            state, events, actions = queue.popleft()
            count += 1
            if count > self.profile.max_search_nodes:
                raise StrategyError('HISTORY_SEARCH_BUDGET_EXHAUSTED')
            signature = (state.key(), events)
            if signature in visited:
                continue
            visited.add(signature)
            if self._matches(state, snap, roles):
                matches.append((state, events))
            if state.terminal or actions >= self.profile.max_path_actions:
                continue
            if state.needs_cards:
                if len(snap['board']) > len(state.board):
                    c = snap['board'][len(state.board)]
                    if c not in state.board:
                        queue.append((reveal(state, c), events + (('board', c),), actions))
                continue
            if len(state.board) > len(snap['board']):
                continue
            try:
                choices = list(self.policy.actions(state))
            except StrategyError:
                choices = [Action('check')] if state.call_required_bb <= 1e-8 else [Action('fold'), Action('call', state.call_cost_bb)]
            a = state.actor
            if roles[a] in snap['stacks']:
                delta = state.stacks[a] - snap['stacks'][roles[a]]
                kind = 'raise' if state.call_required_bb > 1e-8 else 'bet'
                amounts = [delta]
                if len(snap['board']) == len(state.board):
                    q = self.profile.quantum_bb
                    low = max(delta-q/2, snap['pot']-q/2-state.pot_bb)
                    high = min(delta+q/2, snap['pot']+q/2-state.pot_bb)
                    if 0 < low <= high:
                        amounts.append((low+high)/2)
                for paid in amounts:
                    if paid <= state.call_required_bb + 1e-8:
                        continue
                    if any(abs(c.amount_bb-paid) <= self.profile.quantum_bb/2 + 1e-8 for c in choices if c.amount_bb):
                        continue
                    literal = Action('all_in' if abs(paid-state.stacks[a]) < 1e-8 else kind, paid)
                    if is_legal(state, literal):
                        choices.append(literal)
            for action in choices:
                if action.kind == 'fold' and roles[state.actor] not in snap['folded']:
                    continue
                # Positive chip changes are required for chip-committing branches.
                payout_possible = any(snap['stacks'].get(s, state.stacks[i]) > state.stacks[i] + self.profile.quantum_bb/2 for i,s in enumerate(roles))
                if not payout_possible and action.amount_bb and snap['stacks'].get(roles[state.actor], state.stacks[state.actor]) > state.stacks[state.actor] - action.amount_bb + self.profile.quantum_bb / 2 + 1e-8:
                    continue
                if is_legal(state, action):
                    child = apply_action(state, action)
                    queue.append((child, events + (('action', str(state.actor), action.kind, str(action.amount_bb)),), actions + 1))
        return matches

    def observe(self, result, *, table_id, buttons, sample_id, captured_at=None):
        now = self.clock()
        captured_at = now if captured_at is None else captured_at
        ts = result.setdefault('table_state', {})
        ts.pop('strategy_state', None)
        ts.pop('confirmed_history', None)
        hand = result.get('hand') or {}
        hand_id = hand.get('hand_id') or hand.get('hand_number')
        if hand_id is None:
            out = dict(status='PENDING', reason='HISTORY_HAND_ID_UNREADABLE')
            ts['confirmed_history'] = out
            return out
        entry = None
        try:
            entry = self._entry(str(table_id), hand_id)
            if now - captured_at > self.profile.max_snapshot_age_s or captured_at > now + .001:
                raise StrategyError('HISTORY_STALE_CAPTURE')
            if str(sample_id) == entry['last_sample']:
                raise StrategyError('HISTORY_DUPLICATE_CAPTURE')
            entry['last_sample'] = str(sample_id)
            snap = self._snapshot(result, buttons, sample_id, captured_at)
            if snap['mode'] != self.policy.context.mode or snap['stage'] != self.policy.context.stage:
                raise StrategyError('HISTORY_TOURNAMENT_CONTEXT_MISMATCH')
            if not snap['board']:
                board = result.get('board') or {}
                if board.get('status') in ('BOARD_INCOMPLETE', 'BOARD_DUPLICATE_REJECTED') or (board.get('status') == 'BOARD_PARTIAL_OR_OBSTRUCTED' and board.get('reason') != 'FIRST_CARD_ANCHOR_MISSING'):
                    raise StrategyError('HISTORY_BOARD_PRESENT_BUT_UNREADABLE')
                if entry['state'] is not None:
                    raise StrategyError('HISTORY_BOARD_REGRESSED_WITHOUT_NEW_HAND')
                entry['preflop'].append(snap)
                out = dict(status='OBSERVING_PREFLOP', reason='COLLECTING_ARRIVAL_WITNESS')
                ts['confirmed_history'] = out
                return out
            roles = self._actors(snap)
            if not snap['hero'] and entry['state'] is not None and 'hero' in snap['folded']:
                snap['hero'] = entry['hero']  # explicit fold, same fresh hand ID; never a new decision
            if len(snap['hero']) != 2:
                raise StrategyError('HISTORY_HERO_CARDS_UNCONFIRMED')
            if entry['state'] is None:
                root = self.policy.root
                if set(snap['board'][:3]) != set(root.board[:3]) or snap['board'][3:len(root.board)] != root.board[3:]:
                    raise StrategyError('HISTORY_POLICY_ROOT_BOARD_MISS')
                witness = self._witness(entry, snap)
                start = self.policy.root
            else:
                witness = entry.get('witness')
                start = entry['state']
                if snap['hero'] != entry['hero']:
                    raise StrategyError('HISTORY_HERO_CARDS_CHANGED_IN_SAME_HAND')
                if roles != entry['roles']:
                    raise StrategyError('HISTORY_SEAT_MAPPING_CHANGED_IN_SAME_HAND')
                if entry.get('positions') is not None and snap['positions'] != entry['positions']:
                    raise StrategyError('HISTORY_POSITIONS_CHANGED_IN_SAME_HAND')
                if any(not compatible(snap['stacks'].get(seat),value,self.profile.quantum_bb*2)
                       for seat,value in entry.get('outside_stacks',{}).items()):
                    raise StrategyError('HISTORY_HU_OUTSIDE_PLAYER_CHIP_CHANGE')
            matches = self._paths(start, snap, roles)
            if not matches:
                raise StrategyError('HISTORY_GAP_OR_ACTION_OUTSIDE_MODEL')
            if len(matches) != 1:
                raise StrategyError('HISTORY_AMBIGUOUS_LEGAL_PATHS')
            state, events = matches[0]
            candidate = digest([state.key(), events])
            unchanged = entry['state'] is not None and not events and entry['status'] == 'CONFIRMED'
            if entry['candidate'] != candidate:
                entry['candidate_evidence'] = []
            evidence = {k:snap[k] for k in ('sample_id','captured_at','pot','stacks','bets')}
            entry['candidate_evidence'].append(evidence)
            entry['candidate_evidence'] = entry['candidate_evidence'][-self.profile.confirmations:]
            entry['repeats'] = self.profile.confirmations if unchanged else entry['repeats'] + 1 if entry['candidate'] == candidate else 1
            entry['candidate'] = candidate
            if entry['repeats'] < self.profile.confirmations:
                out = dict(status='PENDING', reason='HISTORY_WAITING_FOR_INDEPENDENT_CAPTURE', candidates=1)
                ts['confirmed_history'] = out
                return out
            if entry['state'] is None:
                entry['line'] = LinePolicy(self.policy)
                entry['hero'], entry['roles'], entry['witness'] = snap['hero'], roles, witness
                entry['positions'] = snap['positions']
                entry['outside_stacks'] = {s:v for s,v in snap['stacks'].items() if s not in roles}
                if self.journal:
                    self.journal.append(table_id, hand_id, 'root:' + digest([self.policy.root.key(), witness]),
                        dict(event_type='root_confirmed', policy_sha256=self.policy.fingerprint,
                             observation_source=result.get('observation_source','UNSPECIFIED_PASSIVE_SOURCE'),
                             actual_preflop_sources=self.preflop_manifest,
                             range_alignment='DECLARED_POLICY_PRIORS_NOT_PROVEN_FROM_LIVE_NVT_DECISIONS',
                             witness=witness, root=self.policy.root.to_dict(),
                             confirmed_captures=entry['candidate_evidence'],
                             money_precision_bb=self.profile.quantum_bb))
            previous = start
            line = copy.copy(entry['line']) if events and entry['line'] is not None else entry['line']
            if events and line is not None:
                line.trace = list(line.trace)
            for event in events:
                if event[0] == 'board':
                    next_state = reveal(previous, event[1])
                    payload = dict(event_type='board', card=event[1])
                    if line is not None:
                        try:
                            line.reveal(event[1])
                        except StrategyError:
                            line = None
                else:
                    _, actor, kind, amount = event
                    action = Action(kind, float(amount))
                    next_state = apply_action(previous, action)
                    payload = dict(event_type='action', actor=int(actor), position=self.policy.context.positions[int(actor)],
                                   action=kind, model_additional_bb=action.amount_bb,
                                   compatible_amount_interval_bb=interval(action.amount_bb, self.profile.quantum_bb),
                                   exact_observed_chips=False)
                    if line is not None:
                        try:
                            line.observe(action)
                        except StrategyError:
                            line = None
                event_id = digest([previous.key(), event, next_state.key()])
                if self.journal:
                    self.journal.append(table_id, hand_id, event_id, payload)
                entry['trace'].append(dict(payload, event_id=event_id))
                previous = next_state
            newly_confirmed = bool(events) or entry['state'] is None
            if newly_confirmed:
                entry['revision'] += 1
            entry['state'], entry['last_seen'], entry['line'] = state, snap, line
            entry['candidate'], entry['repeats'] = None, 0
            entry['status'], entry['reason'] = 'CONFIRMED', None
            if self.journal and newly_confirmed:
                self.journal.append(table_id, hand_id, 'state:' + state.key(),
                    dict(event_type='state_confirmed', policy_sha256=self.policy.fingerprint,
                         profile_sha256=self.profile.fingerprint,
                         state=state.to_dict(), hero=list(entry['hero']), roles=list(roles),
                         positions=entry.get('positions'),outside_stacks=entry.get('outside_stacks'),
                         witness=witness, revision=entry['revision']))
                self.journal.append(table_id, hand_id, 'evidence:' + digest([state.key(), snap['sample_id']]),
                    dict(event_type='observation_evidence', model_state_sha256=state.key(),
                         observation_source=result.get('observation_source','UNSPECIFIED_PASSIVE_SOURCE'),
                         sample_id=snap['sample_id'], captured_at=snap['captured_at'],
                         displayed_pot_bb=snap['pot'], displayed_stacks_bb=snap['stacks'],
                         displayed_bets_bb=snap['bets'], display_quantum_bb=self.profile.quantum_bb,
                         independent_captures=entry['candidate_evidence']))
            out = dict(status='CONFIRMED', events=len(events), revision=entry['revision'],
                       model_state=state.to_dict(), amount_precision_bb=self.profile.quantum_bb,
                       ranges_status='CONDITIONED' if line is not None else 'RESPONSE_MODEL_MISSING',
                       range_scope='COMPILED_REFERENCE_PRIORS',
                       source='UNIQUE_LEGAL_PATH_AND_REPEATED_PASSIVE_OBSERVATIONS')
            ts = result['table_state']
            ts['active_seats'] = [s for s in roles if s not in snap['folded']]
            if state.actor == 0 and not state.terminal and not state.needs_cards:
                d = DecisionState(self.policy.context, state, snap['hero'], str(table_id), str(hand_id), entry['revision'])
                payload = asdict(d)
                payload['range_sha256'] = [r.fingerprint for r in self.policy.ranges]
                payload['posterior_sha256'] = [r.fingerprint for r in entry['line'].ranges] if entry['line'] else None
                payload['observation_precision_bb'] = self.profile.quantum_bb
                payload['history_confirmation'] = out['source']
                payload['profile_sha256'] = self.profile.fingerprint
                ts['strategy_state'] = payload
            ts['confirmed_history'] = out
            if self.journal and state.terminal:
                self.journal.close_hand(table_id,hand_id)
            return out
        except (StrategyError, ValueError, TypeError, KeyError) as exc:
            if entry is not None:
                entry['candidate'], entry['repeats'] = None, 0
                entry['status'], entry['reason'] = 'PENDING', str(exc)
            result.get('table_state', {}).pop('strategy_state', None)
            out = dict(status='PENDING', reason=str(exc), revision=entry['revision'] if entry else 0)
            ts['confirmed_history'] = out
            if entry is not None and self.journal:
                state_key = entry['state'].key() if entry['state'] is not None else None
                gap_id = 'gap:' + digest([state_key,str(exc)])
                if gap_id not in entry['reported_gaps']:
                    self.journal.append(table_id,hand_id,gap_id,
                        dict(event_type='observation_gap',reason=str(exc),sample_id=str(sample_id),
                             captured_at=captured_at,last_confirmed_state_sha256=state_key))
                    entry['reported_gaps'].add(gap_id)
            return out

    def current(self, table_id):
        return self._hands.get(str(table_id))
