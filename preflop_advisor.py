"""Exploratory live preflop advisor over the NVT range reference.

Separate from preflop_study.py: that module is a strict, exact-match SIMULATION
validator; this one turns the live table reading into a usable recommendation by
consulting the validated range pack at the nearest stack bucket. It is labelled
EXPLORATORY and never authorises execution.

The NVT pack is a reference, optimised for short stacks: it covers discrete
stacks 5-25bb, 9-max, chip EV + ICM + PKO. Deep stacks (>25bb) and post-flop are
out of coverage and abstain here, to be developed into the bot's own engine.

No capture, no clicks. Stack bucketing and the 9-max table are explicit
approximations, reported in every answer.
"""
import json
from pathlib import Path

from preflop_study import hand_key, Blocked

RAISE_FLOOR_BB = 1.5  # a bet above the BB (1.0) is a raise, not a blind post


def infer_live_spot(table_state):
    """Guess the preflop spot from the bets on the table (approximate, by the
    nearest-seat bet attribution). If the hero has not raised: no non-hero raiser
    -> first_in; exactly one -> vs_open; else abstain. If the hero already opened:
    exactly one bet above the hero's -> vs_3bet against that position; else
    abstain (4bet/multiway). `opener` holds the aggressor (opener or 3bettor)."""
    positions = table_state.get('positions') or {}
    hero_bet = 0.0
    raisers = {}
    for bet in (table_state.get('bets') or []):
        seat, amount = bet.get('seat'), bet.get('bet_bb')
        if not isinstance(amount, (int, float)):
            continue
        if seat == 'hero':
            hero_bet = max(hero_bet, amount)
            continue
        if amount > RAISE_FLOOR_BB and seat in positions:
            raisers[positions[seat]] = max(raisers.get(positions[seat], 0.0), amount)
    if hero_bet > RAISE_FLOOR_BB:                       # hero has already opened
        rereraisers = {p: a for p, a in raisers.items() if a > hero_bet + 0.4}
        if len(rereraisers) == 1:
            return dict(spot='vs_3bet', opener=next(iter(rereraisers)))
        return dict(spot='abstain', opener=None,
                    reason='HERO_OPENED_NO_RERAISE' if not rereraisers else 'MULTIWAY_OR_4BET_NOT_COVERED')
    if not raisers:
        return dict(spot='first_in', opener=None)
    if len(raisers) == 1:
        return dict(spot='vs_open', opener=next(iter(raisers)))
    return dict(spot='abstain', opener=None, reason='MULTIWAY_OR_3BET_NOT_COVERED')


class PreflopAdvisor:
    # Short stacks (5-25) come from the validated NVT pack; 40/100 from the deep
    # reference pack (not HRC-validated, flagged in every answer).
    STACK_BUCKETS = (5, 8, 10, 12, 15, 20, 25, 40, 100)

    def __init__(self, pack):
        if pack.get('format') != 'nvt-range-export' or pack.get('version') != 1:
            raise Blocked('UNSUPPORTED_RANGE_FORMAT')
        self.hands = pack['hands']
        if len(self.hands) != 169:
            raise Blocked('INVALID_HAND_INDEX')
        self.nodes = list(pack['nodes'])   # includes unvalidated reference (deep) nodes
        self.engine_commit = pack.get('engineCommit')
        self._index = {}
        for n in self.nodes:
            self._index.setdefault(self._key_of(n), n)

    @classmethod
    def from_file(cls, path):
        return cls(json.loads(Path(path).read_text(encoding='utf-8')))

    @classmethod
    def from_files(cls, *paths):
        """Merge several packs (e.g. the validated short pack plus the deep
        reference pack). They must share format/version and the 169-hand index."""
        merged = None
        for path in paths:
            pack = json.loads(Path(path).read_text(encoding='utf-8'))
            if merged is None:
                merged = dict(pack)
            elif pack.get('hands') != merged['hands']:
                raise Blocked('HAND_INDEX_MISMATCH_BETWEEN_PACKS')
            else:
                merged = dict(merged, nodes=merged['nodes'] + pack['nodes'])
        return cls(merged)

    @staticmethod
    def _key_of(node):
        c = node['context']
        return (c['mode'], c['format'], c['stage'], c['players'], c['stack'],
                node['spot'], node['hero'], tuple(node.get('vs') or ()),
                node.get('spread'))

    def bucket_stack(self, stack_bb):
        """Nearest covered stack bucket, or (None, reason) when out of coverage.

        The HRC solutions top out at 100bb, but real tournaments play deeper,
        especially early. Preflop open/3bet ranges change little above 100bb, so
        a stack at or beyond the top bucket uses the 100bb range as the best
        available reference (the extrapolation is flagged in the caveats), rather
        than abstaining and leaving a common deep table without advice."""
        if not isinstance(stack_bb, (int, float)) or stack_bb <= 0:
            return None, 'STACK_UNKNOWN'
        if stack_bb >= self.STACK_BUCKETS[-1]:
            return self.STACK_BUCKETS[-1], 'OK'
        return min(self.STACK_BUCKETS, key=lambda s: abs(s - stack_bb)), 'OK'

    def advise(self, *, hero_cards, hero_position, stack_bb, mode='chip_ev',
               table_format=None, stage='mid', players=9, spot='open_raise', vs=(), spread=None):
        """An exploratory recommendation for one preflop spot, or an abstention.

        Returns status ADVICE | ABSTAIN | OUT_OF_RANGE with the action mix, EVs,
        the recommended (most frequent) action, and the approximations made. ICM/
        PKO nodes carry a stack spread; absent one, equal stacks ('iguais') are
        assumed and flagged."""
        bucket, why = self.bucket_stack(stack_bb)
        if bucket is None:
            return self._abstain(why, stack_bb=stack_bb)
        try:
            hand = hand_key(hero_cards)
        except Blocked as exc:
            return self._abstain(str(exc))
        spread = spread if spread is not None else ('iguais' if mode in ('icm', 'pko_icm') else None)
        if table_format is None:
            table_format = 'pko' if mode in ('pko', 'pko_icm') else 'regular'
        node = self._index.get((mode, table_format, stage, players, bucket, spot, hero_position, tuple(vs), spread))
        if node is None:
            return self._abstain('NO_VALIDATED_NODE_FOR_CONTEXT',
                                 context=dict(mode=mode, stage=stage, stack=bucket, spot=spot,
                                              hero=hero_position, players=players))
        i = self.hands.index(hand)
        validated = bool(node.get('validated'))
        caveats = self._caveats(bucket, stack_bb, players, mode)
        if not validated:
            caveats.append('UNVALIDATED_REFERENCE_RANGE')
        base = dict(spot=spot, hero_position=hero_position, hand=hand, node_id=node['id'],
                    source=node['source'], validated=validated, exploratory=True,
                    execution_allowed=False, stack_bb=stack_bb, stack_bucket=bucket,
                    bucketed=bucket != stack_bb, players_assumed=players, caveats=caveats)
        if i in (node.get('outOfRange') or []):
            return dict(base, status='OUT_OF_RANGE')
        mix, ev = [], {}
        for act in node['actions']:
            freq = node['freq'][act][i]
            if freq > 0:
                mix.append(dict(action=act, frequency=freq))
            values = (node.get('ev') or {}).get(act)
            ev[act] = values[i] if values is not None and len(values) == 169 else None
        recommended = max(mix, key=lambda m: m['frequency'])['action'] if mix else None
        return dict(base, status='ADVICE', mix=mix, ev=ev, ev_unit=node['evUnit'], recommended=recommended)

    def advise_first_in(self, **kwargs):
        """First-in (unopened) decision: open_raise where the pack has it, else
        open_shove (short stacks). Covers 5-25bb; 20bb has no first-in node here."""
        kwargs.pop('spot', None)
        kwargs.pop('vs', None)
        primary = self.advise(spot='open_raise', vs=(), **kwargs)
        if not (primary['status'] == 'ABSTAIN' and primary.get('reason') == 'NO_VALIDATED_NODE_FOR_CONTEXT'):
            return primary
        return self.advise(spot='open_shove', vs=(), **kwargs)

    def advise_from_reading(self, table_state, hero_cards, **kwargs):
        """Pull hero's position/stack from a read_table_state result, infer the
        spot from the bets (first_in or vs_open), advise, and attach a founded
        raise size for the recommended action. The spot inference is approximate
        (it rides on the nearest-seat bet attribution)."""
        positions = table_state.get('positions') or {}
        hero = table_state.get('seats', {}).get('hero', {})
        if 'hero' not in positions:
            return self._abstain('HERO_POSITION_UNKNOWN')
        spot = infer_live_spot(table_state)
        base = dict(hero_cards=hero_cards, hero_position=positions['hero'], stack_bb=hero.get('stack_bb'))
        if spot['spot'] in ('vs_open', 'vs_3bet'):
            result = self.advise(spot=spot['spot'], vs=(spot['opener'],), **base, **kwargs)
            if isinstance(result, dict):
                result.setdefault('caveats', []).append('AGGRESSOR_INFERRED_%s' % spot['opener'])
        elif spot['spot'] == 'first_in':
            result = self.advise_first_in(**base, **kwargs)
        else:
            return self._abstain(spot.get('reason', 'SPOT_NOT_COVERED'))
        if isinstance(result, dict) and result.get('status') == 'ADVICE' and result.get('recommended'):
            import sizing
            result['sizing'] = sizing.size_from_reading(result['recommended'], table_state,
                                                        positions['hero'], spot.get('opener'))
        return result

    def _caveats(self, bucket, stack_bb, players, mode):
        out = ['EXPLORATORY_NOT_FOR_EXECUTION', 'NVT_REFERENCE_SHORT_STACK_ONLY']
        if bucket != stack_bb:
            out.append('STACK_BUCKETED_%s_TO_%sBB' % (stack_bb, bucket))
        if isinstance(stack_bb, (int, float)) and stack_bb > self.STACK_BUCKETS[-1]:
            # Beyond the deepest solved stack: the 100bb range is a reference, not a solution.
            out.append('STACK_ABOVE_SOLVED_DEPTH_100BB_REFERENCE')
        if players != 9:
            out.append('TABLE_IS_9MAX_REFERENCE')
        if mode != 'chip_ev':
            out.append('ICM_PKO_NEEDS_TOURNAMENT_INPUTS')
        if mode in ('icm', 'pko_icm'):
            out.append('ICM_SPREAD_ASSUMED_EQUAL_STACKS')
        return out

    @staticmethod
    def _abstain(reason, **extra):
        return dict(status='ABSTAIN', reason=reason, exploratory=True, execution_allowed=False, **extra)
