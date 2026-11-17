"""User-authorized loose BB benchmark, NOT a solved squeeze/call strategy.

The denominator is the 1,326 unblocked physical starting combinations. The
postflop arrival uses ONLY the call weights. Squeeze sizes, shove splits,
bounty values and EVs are deliberately not fabricated here.
"""
import copy
from fractions import Fraction
import math

from preflop_equity import hand_to_combos
from strategy.range_catalog import ComboRange
from strategy.state_contract import StrategyError, digest

PRESET = 'bb10c50-lab-v1'
SCHEMA = 'software.multiway-bb-defense-assumption.v1'
AUTHORITY = 'USER_AUTHORIZED_LAB_ASSUMPTION_NOT_SOLVER_NOT_POPULATION_MEASUREMENT'
RANKS = 'AKQJT98765432'
SQUEEZE_GROUPS = (
    (Fraction(1), 'AA KK QQ JJ TT AKs AQs AKo KQs'),
    (Fraction(3, 4), 'AQo AJs KJs QJs A5s A4s'),
    (Fraction(1, 2), '99 ATs KTs JTs A3s A2s K9s QTs Q9s J9s T9s 98s 87s 76s 65s 54s A9s A8s A7s A6s'),
    (Fraction(1, 4), '88 AJo KQo K8s Q8s J8s T8s 97s 86s'),
)
CALL_OFFSUIT = frozenset(('AQo AJo ATo A9o A8o A7o A6o A5o A4o A3o A2o '
    'KQo KJo KTo K9o K8o K7o QJo QTo Q9o Q8o Q7o '
    'JTo J9o J8o J7o T9o T8o 98o 87o 76o 65o 54o').split())


def hand_classes():
    return tuple(r+r for r in RANKS) + tuple(a+b+k for i, a in enumerate(RANKS)
        for b in RANKS[i+1:] for k in ('s', 'o'))


def build_defense():
    squeeze = {h:Fraction(0) for h in hand_classes()}
    for probability, hands in SQUEEZE_GROUPS:
        for h in hands.split():
            if squeeze[h]:
                raise StrategyError('DUPLICATE_BB_SQUEEZE_GROUP')
            squeeze[h] = probability
    rows, masses = [], {a:Fraction(0) for a in ('squeeze', 'call', 'fold')}
    for h in hand_classes():
        available = 1-squeeze[h]
        use_call = h.endswith('s') or (len(h) == 2 and h[0] in '98765432') or h in CALL_OFFSUIT
        call = available if use_call else Fraction(0)
        if h == 'J7o':
            # Simple volume boundary, chosen for bookkeeping, NOT measured EV.
            call = Fraction(4, 5)
        freq = dict(squeeze=squeeze[h], call=call, fold=1-squeeze[h]-call)
        combos = len(hand_to_combos(h))
        for action, p in freq.items():
            if not 0 <= p <= 1:
                raise StrategyError('INVALID_BB_DEFENSE_PARTITION')
            masses[action] += combos*p
        rows.append(dict(hand=h, physical_combos=combos,
            frequencies={a:float(p) for a, p in freq.items()}))
    value = dict(schema=SCHEMA, preset=PRESET,
        authority=AUTHORITY,
        context=dict(mp_position='LJ', dealt_players=9, initial_stacks_bb=[40., 40., 40.],
            stack_timing='BEFORE_POSTS', open_to_bb=2., big_blind_ante_bb=1.,
            line=['MP open', 'BTN call', 'SB fold', 'BB decision']),
        denominator=dict(kind='UNBLOCKED_STARTING_COMBINATIONS', combinations=1326),
        requested_approximate_percent=dict(squeeze=10., call=50., fold=40.),
        effective_combo_mass={a:float(v) for a, v in masses.items()},
        exact_mass_fractions={a:[v.numerator, v.denominator] for a, v in masses.items()},
        unblocked_percent={a:float(v/Fraction(1326)*100) for a, v in masses.items()},
        rows=rows, squeeze_raise_to_bb=None, squeeze_shove_split=None,
        action_ev=None, pko_economy=None, solver_executed=False,
        notes=[
            'Call is approximately50% of the WHOLE deck AFTER excluding squeeze frequencies; total continuation is60%.',
            'All suited and low pairs call with the residual probability; selected offsuit classes also call.',
            'TT+, AQs+, AKo and KQs squeeze100% in this fixed benchmark; no trap frequency was assumed for them.',
            'Mixed squeeze/call light hands are explicit; this is not uniformly rescaling the old NVT call vector.',
            'J7o call80% only closes the approximate volume; it has no calculated EV justification.',
            'Percentages change after card removal and conditioning on the MP/BTN ranges; they are not fixed after blockers.',
            'No assertion that most players overcall50%, nor that10% squeeze is optimal at40BB in PKO.',
            'Squeeze does not mean shove. This postflop family includes the BB CALL branch only.'])
    value['sha256'] = digest(value)
    validate_defense(value)
    return value


def validate_defense(value):
    if value.get('schema') != SCHEMA or value.get('preset') != PRESET:
        raise StrategyError('KNOWN_BB_DEFENSE_SCHEMA_REQUIRED')
    body = {k:v for k, v in value.items() if k != 'sha256'}
    if digest(body) != value.get('sha256'):
        raise StrategyError('BB_DEFENSE_FINGERPRINT_MISMATCH')
    if (value.get('authority') != AUTHORITY or value.get('solver_executed') is not False
            or value.get('action_ev') is not None or value.get('pko_economy') is not None):
        raise StrategyError('BB_DEFENSE_MUST_REMAIN_AN_UNSOLVED_LAB_ASSUMPTION')
    rows = value['rows']
    if len(rows) != 169 or {r['hand'] for r in rows} != set(hand_classes()):
        raise StrategyError('BB_DEFENSE_REQUIRES_169_DISTINCT_CLASSES')
    masses = {a:0. for a in ('squeeze', 'call', 'fold')}
    for r in rows:
        frequencies = r['frequencies']
        if set(frequencies) != set(masses) or r['physical_combos'] != len(hand_to_combos(r['hand'])):
            raise StrategyError('BB_DEFENSE_ACTION_OR_COMBO_MISMATCH')
        if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in frequencies.values()):
            raise StrategyError('INVALID_BB_DEFENSE_FREQUENCY')
        if abs(sum(frequencies.values()) - 1) > 1e-12:
            raise StrategyError('BB_DEFENSE_FREQUENCIES_DO_NOT_SUM_TO_ONE')
        for a, p in frequencies.items():
            masses[a] += r['physical_combos']*p
    if value['denominator'] != dict(kind='UNBLOCKED_STARTING_COMBINATIONS', combinations=1326):
        raise StrategyError('BB_DEFENSE_UNBLOCKED_DENOMINATOR_REQUIRED')
    for a, mass in masses.items():
        if abs(value['effective_combo_mass'][a]-mass) > 1e-8:
            raise StrategyError('BB_DEFENSE_REPORTED_MASS_MISMATCH')
        if abs(value['unblocked_percent'][a]-mass/1326*100) > 1e-8:
            raise StrategyError('BB_DEFENSE_REPORTED_PERCENT_MISMATCH')
        if abs(value['requested_approximate_percent'][a]-mass/1326*100) > .01:
            raise StrategyError('BB_DEFENSE_OUTSIDE_APPROXIMATE_10_50_40_BUDGET')
    return value


def frequencies(value, action):
    validate_defense(value)
    if action not in ('squeeze', 'call', 'fold'):
        raise StrategyError('UNKNOWN_BB_DEFENSE_ACTION')
    return {r['hand']:r['frequencies'][action] for r in value['rows']}


def apply_to_plan(plan, defense):
    """Copy the preparation and replace ONLY BB's CALL prior in both references."""
    validate_defense(defense)
    if (plan.get('schema') != 'software.multiway-pilot-preparation.v1'
            or plan.get('mp_source_position') != 'LJ'
            or plan.get('root_pot_bb') != 7.5
            or tuple(plan.get('root', {}).get('stacks', ())) != (38., 38., 37.)):
        raise StrategyError('BB_DEFENSE_REQUIRES_THE_FIXED_MP_BTN_BB40_PILOT')
    result = copy.deepcopy(plan)
    call = frequencies(defense, 'call')
    combo = ComboRange.from_classes(call, defense['sha256'] + ':BB_CALL_ONLY')
    for ref in result['candidate_references'].values():
        if [r['role'] for r in ref['ranges']] != ['MP', 'BTN', 'BB']:
            raise StrategyError('STABLE_MP_BTN_BB_REFERENCE_ORDER_REQUIRED')
        parent = {k:copy.deepcopy(ref[k]) for k in ('sha256', 'source_file', 'reference_kind', 'mode', 'stage')}
        bb = dict(role='BB', source_position='BB', node_id=PRESET+':BB_OVERCALL', selected_action='call',
            class_frequencies=call.copy(), combo_range=combo.to_dict(), combo_mass=combo.mass,
            exporter_claimed_validated=False, source=dict(kind='USER_FIXED_LAB_PRIOR', preset_sha256=defense['sha256']),
            source_context=dict(mode=ref['mode'], stage=ref['stage'], stack=40, players=9),
            source_table=dict(stacks_before_posts_bb=dict.fromkeys(plan['source_seats'], 40.),
                actions=[dict(position='BB', type='post_ante', amount=1.),
                    dict(position='SB', type='post_sb', amount=.5),
                    dict(position='BB', type='post_bb', amount=1.),
                    dict(position='LJ', type='raise', amount=2.),
                    dict(position='BTN', type='call', amount=2.),
                    dict(position='SB', type='fold', amount=0.)],
                potBb=6.5, call_cost_bb=1., after_call_pot_bb=7.5),
            arrival_status='EXPLICIT_USER_FIXED_OVERCALL_ASSUMPTION_NOT_REAL_HRC_PARENT',
            exact_hrc_parent_confirmed=False)
        ref['ranges'][2] = bb
        ref['original_nvt_parent'] = parent
        ref['reference_kind'] = 'NVT_MP_BTN_PLUS_USER_FIXED_BB_CALL_ASSUMPTION'
        ref['fingerprint_kind'] = 'CANONICAL_COMPOSITE_REFERENCE_NOT_RAW_NVT_FILE'
        ref.pop('sha256')
        ref['sha256'] = digest(ref)
    result['bb_defense_assumption'] = dict(preset=PRESET, sha256=defense['sha256'],
        unblocked_percent=defense['unblocked_percent'], call_only_used_for_postflop=True,
        original_nvt_bb_preserved_in_baseline=True, native_hrc_parent_confirmed=False)
    result['status'] = 'PREPARED_USER_BB10C50_ASSUMPTION_NOT_SOLVED'
    result['required_before_solving'] = [
        ('For this user-authorized lab branch, use the supplied BB call weights as a fixed hypothesis; '
         'preserve MP/BTN priors and identify folded-range/bunching assumptions. Do not relabel it as an authentic HRC export.')
        if text.startswith('Use a real HRC parent') else text
        for text in result['required_before_solving']]
    return result


def report_text(defense):
    validate_defense(defense)
    lines = ['BB MP OPEN x BTN CALL — HIPOTESE DE LABORATORIO 40 BB',
        'Nao e range otimo nem medicao da populacao. Squeeze nao significa shove.',
        'Base:1326 combinacoes antes dos bloqueios. Percentuais por MAO somam100%.',
        'Massa: ' + ', '.join(f'{a}={defense["effective_combo_mass"][a]:.1f} combos ({defense["unblocked_percent"][a]:.5f}%)' for a in ('squeeze', 'call', 'fold')),
        'Formato: mao | squeeze% | call% | fold% | combos fisicos', '']
    for r in defense['rows']:
        f = r['frequencies']
        lines.append(f'{r["hand"]:3s} | {100*f["squeeze"]:6.2f} | {100*f["call"]:6.2f} | {100*f["fold"]:6.2f} | {r["physical_combos"]}')
    return '\n'.join(lines) + '\n'
