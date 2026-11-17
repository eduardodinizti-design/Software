"""Prepare an auditable MP/BTN/BB study without inventing solver policies."""
from bisect import bisect_left
import hashlib
import json
import math
from pathlib import Path
import random

from preflop_equity import eval7, parse_card
from strategy.multiway_state import MultiwayState, POSITIONS, act, action_menu, reveal, settle
from strategy.range_catalog import ComboRange, DECK, combo_cards
from strategy.state_contract import StrategyError, digest

SCHEMA = 'software.multiway-pilot-preparation.v1'
SEATS = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB')


def extract_candidates(path, mode, stage, mp_position='LJ'):
    """Exact NVT vectors, with explicit uncertainty about the multiway arrival."""
    if mp_position not in ('LJ', 'HJ', 'UTG+2'):
        raise StrategyError('EXPLICIT_MIDDLE_POSITION_REQUIRED')
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    hands = data['hands']
    if len(hands) != 169 or len(set(hands)) != 169:
        raise StrategyError('NVT_169_UNIQUE_CLASSES_REQUIRED')
    records = []
    for role, hero, spot, villain, selected in (
        ('MP', mp_position, 'open_raise', '', 'raise'),
        ('BTN', 'BTN', 'vs_open', mp_position, 'call'),
        ('BB', 'BB', 'vs_open', mp_position, 'call'),
    ):
        node_id = f'{mode}|{stage}|40|{spot}|{hero}|{villain}|-'
        matches = [n for n in data['nodes'] if n.get('id') == node_id]
        if len(matches) != 1:
            raise StrategyError('ONE_EXACT_NVT_NODE_REQUIRED:' + node_id)
        node = matches[0]
        context = node.get('context', {})
        if any(context.get(k) != v for k, v in dict(mode=mode, stage=stage, stack=40, players=9).items()):
            raise StrategyError('NVT_NODE_ID_AND_CONTEXT_DISAGREE')
        vectors = node['freq']
        if selected not in vectors or any(len(v) != 169 for v in vectors.values()):
            raise StrategyError('NVT_ACTION_VECTOR_MISMATCH')
        for i in range(169):
            values = [v[i] for v in vectors.values()]
            if (any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values)
                    or abs(sum(values) - 1) > .0011):
                raise StrategyError('NVT_ACTION_FREQUENCIES_INVALID')
        frequencies = dict(zip(hands, vectors[selected]))
        combo = ComboRange.from_classes(frequencies, digest([hashlib.sha256(raw).hexdigest(), node_id, selected]))
        previous = node.get('table', {}).get('actions', [])
        callers = [a.get('position') for a in previous if a.get('type') == 'call']
        exact_bb_sequence = role == 'BB' and callers == ['BTN']
        records.append(dict(role=role, source_position=hero, node_id=node_id,
            selected_action=selected, class_frequencies=frequencies,
            combo_range=combo.to_dict(), combo_mass=combo.mass,
            exporter_claimed_validated=node.get('validated'), source=node.get('source'),
            source_context=node.get('context'), source_table=node.get('table'),
            arrival_status=('BTN_CALL_PRESENT_BUT_FULL_PARENT_STILL_REQUIRES_VALIDATION' if exact_bb_sequence
                else 'SINGLE_OPEN_CANDIDATE_NOT_BB_OVERCALL_RANGE' if role == 'BB'
                else 'INDIVIDUAL_NODE_NOT_COMPLETE_THREE_PLAYER_PARENT'),
            exact_hrc_parent_confirmed=False))
    return dict(source_file=Path(path).name, sha256=hashlib.sha256(raw).hexdigest(),
        reference_kind='USER_NVT_REFERENCE_NOT_INDEPENDENT_HRC_CERTIFICATION',
        mode=mode, stage=stage, mp_position=mp_position, ranges=records)


class ThreePlayerSampler:
    """Product prior conditioned on ALL collisions; never resample just one seat."""
    def __init__(self, ranges, board):
        if len(ranges) != 3:
            raise StrategyError('THREE_RANGES_REQUIRED')
        self.board = MultiwayState(tuple(board)).board
        self.ranges = tuple(r.without(self.board) for r in ranges)
        self.cumulative = []
        for r in self.ranges:
            total, cum = 0., []
            for _, w in r.weights:
                total += w
                cum.append(total)
            self.cumulative.append(cum)
        # A bounded memory DFS proves at least one joint deal exists.
        def compatible(index, used):
            if index == 3:
                return True
            return any(not used.intersection(combo_cards(k))
                and compatible(index + 1, used.union(combo_cards(k)))
                for k, _ in self.ranges[index].weights)
        if not compatible(0, set(self.board)):
            raise StrategyError('NO_COMPATIBLE_THREE_PLAYER_DEAL')

    def sample(self, rng):
        for _ in range(100000):
            hands = []
            for r, cum in zip(self.ranges, self.cumulative):
                i = min(len(cum) - 1, bisect_left(cum, rng.random() * cum[-1]))
                hands.append(combo_cards(r.weights[i][0]))
            private = tuple(c for hand in hands for c in hand)
            if len(set(private)) == 6:
                break
        else:
            raise StrategyError('JOINT_REJECTION_BUDGET_EXHAUSTED_NO_BIASED_FALLBACK')
        dead = set(self.board + private)
        runout = tuple(rng.sample([c for c in DECK if c not in dead], 5 - len(self.board)))
        return tuple(hands), runout


def checkdown_equity(reference, board, samples=5000, seed=20261116):
    """Range-average chip showdown shares. NOT action EV, PKO utility, or strategy."""
    if type(samples) is not int or samples < 2:
        raise StrategyError('AT_LEAST_TWO_EQUITY_SAMPLES_REQUIRED')
    sampler = ThreePlayerSampler([ComboRange.from_dict(r['combo_range']) for r in reference['ranges']], board)
    rng, sums, squares = random.Random(seed), [0.] * 3, [0.] * 3
    for _ in range(samples):
        hands, runout = sampler.sample(rng)
        scores = [eval7([parse_card(c) for c in hand + tuple(board) + runout]) for hand in hands]
        best = max(scores)
        winners = [i for i, score in enumerate(scores) if score == best]
        for i in winners:
            share = 1 / len(winners)
            sums[i] += share
            squares[i] += share * share
    rows = []
    for i, role in enumerate(POSITIONS):
        mean = sums[i] / samples
        variance = max(0., (squares[i] - samples * mean * mean) / (samples - 1))
        se = math.sqrt(variance / samples)
        rows.append(dict(role=role, showdown_share=mean, standard_error=se,
            approximate_95pct_interval=[max(0., mean - 1.96 * se), min(1., mean + 1.96 * se)]))
    return dict(kind='MONTE_CARLO_CHECKDOWN_CHIP_EQUITY_DIAGNOSTIC_NOT_POLICY',
        samples=samples, seed=seed, board=list(board), roles=rows,
        reference_sha256=reference['sha256'], bunching_modelled=False,
        pkobounty_utility_calculated=False, optimal_actions_calculated=False)


def replay_cases(board=('As', '7d', '2c')):
    """Confirmed synthetic rule examples, never labels for profitable play."""
    cases = {
        'mp_cbet_btn_call_bb_checkraise_mp_call_btn_fold': [
            ('check', None), ('bet', 2.5), ('call', None), ('raise', 10.),
            ('call', None), ('fold', None), ('board', '8h'),
            ('check', None), ('bet', 10.), ('call', None), ('board', 'Qc'),
            ('check', None), ('bet', 12.), ('call', None)],
        'btn_stab_bb_call_mp_fold': [
            ('check', None), ('check', None), ('bet', 2.5), ('call', None),
            ('fold', None), ('board', '8h'), ('check', None), ('check', None),
            ('board', 'Qc'), ('check', None), ('check', None)],
        'bb_donk_mp_raise_btn_call_bb_fold': [
            ('bet', 2.5), ('raise', 8.), ('call', None), ('fold', None),
            ('board', '8h'), ('check', None), ('check', None),
            ('board', 'Qc'), ('check', None), ('check', None)],
        'three_way_all_in_and_side_pot': [
            ('bet', 37.), ('raise', 38.), ('call', None),
            ('board', '8h'), ('board', 'Qc')],
        'mp_checkraise_btn_stab_bb_call': [
            ('check', None), ('check', None), ('bet', 2.5), ('call', None),
            ('raise', 10.), ('fold', None), ('call', None),
            ('board', '8h'), ('check', None), ('check', None),
            ('board', 'Qc'), ('check', None), ('check', None)],
    }
    results = []
    hands = (('Ah', 'Kd'), ('Ks', 'Qd'), ('7s', '7c'))
    for name, actions in cases.items():
        state, history = MultiwayState(tuple(board)), []
        for kind, amount in actions:
            before = state.to_dict()
            menu = action_menu(state)
            state = reveal(state, amount) if kind == 'board' else act(state, kind, amount)
            history.append(dict(actor=None if kind == 'board' else POSITIONS[MultiwayState(**before).actor],
                action=kind, to_bb=amount if kind != 'board' else None,
                next_card=amount if kind == 'board' else None, before=before,
                legal_candidate_menu=menu, after=state.to_dict()))
        results.append(dict(name=name, status='SYNTHETIC_RULE_REPLAY_NOT_SOLVER_POLICY',
            history=history, showdown=settle(state, hands),
            optimality_claimed=False, action_frequencies=None))
    return results


def make_plan(chip_reference, pko_reference, board=('As', '7d', '2c')):
    if any(ref.get('mp_position') != 'LJ' for ref in (chip_reference, pko_reference)):
        raise StrategyError('THIS_PILOT_REQUIRES_EXPLICIT_LJ_NOT_ANOTHER_MP_ALIAS')
    root = MultiwayState(tuple(board))
    return dict(schema=SCHEMA, status='PREPARED_NOT_SOLVED_NOT_OPERATIONAL',
        board=list(root.board), roles=list(POSITIONS), action_order=['BB', 'MP', 'BTN'],
        source_seats=list(SEATS), mp_source_position='LJ',
        mp_definition='MP means LJ (seat index 3 in this nine-seat pilot), not an automatic MP alias.',
        stacks_before_posts_bb=[40.] * 9,
        preflop_line=['UTG fold', 'UTG+1 fold', 'UTG+2 fold', 'LJ raise TO 2 BB',
            'HJ fold', 'CO fold', 'BTN call TO 2 BB', 'SB fold', 'BB call TO 2 BB'],
        posts=dict(sb_bb=.5, bb_bb=1., big_blind_ante_bb=1.), root=root.to_dict(),
        root_pot_bb=root.pot_bb, stack_timing='BEFORE_ALL_POSTS',
        candidate_references=dict(chip_ev=chip_reference, pko=pko_reference),
        solver=dict(selected='HRC_PRO_DEDICATED_MULTIWAY_POSTFLOP',
            access='USER_WINDOWS_INSTALLATION_NOT_AVAILABLE_IN_THIS_EXECUTOR',
            executed=False, full_policy_export_verified=False,
            source='https://www.holdemresources.net/docs/postflop/'),
        menu=dict(bet_fractions=[1/3, 1/2, 2/3, 1.], raise_fractions=[1.],
            all_in=True, max_bets_per_street=3, forced_checkdown=False,
            preset_fractions_are_candidates_not_recommendations=True),
        pko_economy=dict(status='AWAITING_EXPLICIT_ECONOMY', bounties=None,
            instant_fraction=None, remaining_players=None, starting_stacks=None,
            prize_structure=None, future_bounty_model=None),
        required_before_solving=[
            'Confirm the nine-seat LJ definition of MP, raise-to 2 BB, BBA1 and stack timing.',
            'Use a real HRC parent with MP open, BTN call, SB fold and BB overcall, preserving folded ranges.',
            'Enter and preserve the explicit PKO economy and all players stacks/bounties.',
            'Record installed HRC version, settings, tree size and postflop abstraction for EACH street.',
            'Pilot HQ+ Strict per street, or document changed abstraction; LQ river is not precise river policy.',
            'Verify the installed HRC export on a real saved pilot before promising a full-tree JSON adapter.'],
        solved_flops=0, executable_policies=0, real_pppoker_validated=False)
