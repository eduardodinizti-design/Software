"""Explicit tournament economics, independent of entry/re-entry rules. No input/OCR.

Bounty amounts are the entire target's head expressed in BB using an explicitly
configured conversion. Unknown amounts/activation never become invented cash.
"""
import math
import re

KINDS = ('auto', 'regular', 'ko', 'pko', 'mystery')
ENTRIES = ('auto', 'freezeout', 'reentry', 'rebuy')
MODES = ('chip_ev', 'icm', 'pko', 'pko_icm')
STAGES = ('mid', 'pre_itm', 'bubble', 'ft')


def finite(value, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum


def validate(kind='auto', entry='auto', bounty_bb=None, cash_fraction=None,
             bounty_active=None, bounty_bb_per_unit=None):
    if kind not in KINDS or entry not in ENTRIES:
        raise ValueError('Tipo de torneio/entrada inválido.')
    if bounty_bb is not None and not finite(bounty_bb):
        raise ValueError('Valor da cabeça em BB deve ser finito e não negativo.')
    if cash_fraction is not None and (not finite(cash_fraction) or cash_fraction > 1):
        raise ValueError('Fração do bounty paga em dinheiro deve estar entre 0 e 1.')
    if bounty_active is not None and type(bounty_active) is not bool:
        raise ValueError('Ativação do bounty deve ser explícita ou desconhecida.')
    if bounty_bb_per_unit is not None and (not finite(bounty_bb_per_unit) or bounty_bb_per_unit<=0):
        raise ValueError('Conversão do bounty em BB deve ser finita e positiva.')


def resolve(tournament=None, *, kind='auto', entry='auto', mode=None, stage=None,
            bounty_bb=None, cash_fraction=None, bounty_active=None, bounty_bb_per_unit=None):
    validate(kind, entry, bounty_bb, cash_fraction, bounty_active,bounty_bb_per_unit)
    if mode not in (None, *MODES) or stage not in (None, *STAGES):
        raise ValueError('Modo/fase de torneio inválido.')
    tournament = tournament or {}
    name = str(tournament.get('name') or '')
    source = 'manual' if kind != 'auto' else 'name_or_reader'
    family = kind
    if kind == 'auto':
        if tournament.get('is_mystery') or re.search(r'MYSTER|MIST[EÉ]R|\bM[ .]?KO\b', name, re.I):
            family = 'mystery'
        elif re.search(r'\bP[ .]?KO\b|PROGRESSIVE|PROGRESSIVO', name, re.I):
            family = 'pko'
        elif tournament.get('is_ko') or re.search(r'\bKO\b|KNOCKOUT', name, re.I):
            family = 'ko'
        elif tournament.get('is_pko') and not re.search(r'BOUNTY', name, re.I):
            family = 'pko'
        elif re.search(r'BOUNTY', name, re.I):
            family = 'unknown_bounty'
        elif mode in ('pko', 'pko_icm'):
            family, source = 'pko', 'explicit_legacy_mode'
        else:
            family, source = 'regular', 'chip_ev_reference_unconfirmed_type'
    if entry == 'auto':
        entry = ('freezeout' if re.search(r'FREEZE\s*OUT|FREEZEOUT', name, re.I)
                 else 'reentry' if re.search(r'RE[ -]?ENTRY|REENTR', name, re.I)
                 else 'rebuy' if re.search(r'RE[ -]?BUY', name, re.I) else 'unknown')
    if stage is None:
        left, paid = tournament.get('players_left'), tournament.get('paid')
        if type(left) is int and 0 < left <= 9:
            stage = 'ft'
        elif type(left) is int and type(paid) is int and paid > 0 and paid < left <= paid + max(1, round(.15 * paid)):
            stage = 'bubble'
        elif type(left) is int and type(paid) is int and paid < left <= round(1.6 * paid):
            stage = 'pre_itm'
        else:
            stage = 'mid'
    active = family in ('ko', 'pko')
    if family == 'mystery':
        active = bounty_active if bounty_active is not None else tournament.get('bounty_active')
    if family == 'unknown_bounty':
        active = None
    icm = mode in ('icm', 'pko_icm') if mode else stage in ('pre_itm', 'bubble', 'ft')
    lookup_mode = ('pko_icm' if icm else 'pko') if family == 'pko' and active else ('icm' if icm else 'chip_ev')
    # KO has a fixed cash reward, not a progressive-bounty source tree. A PKO
    # cash fraction is supplied explicitly; Mystery needs activation and an
    # expected cash reward instead of treating every sealed envelope alike.
    fraction = 1.0 if family in ('ko', 'mystery') else cash_fraction
    cash = bounty_bb * fraction if active is True and bounty_bb is not None and fraction is not None else None
    if family == 'regular' or active is False:
        cash = 0.0
    reasons = []
    if source == 'chip_ev_reference_unconfirmed_type':reasons.append('TOURNAMENT_TYPE_UNCONFIRMED')
    if family == 'ko':reasons.append('KO_USES_REGULAR_PRIOR_PLUS_FIXED_CASH_MODEL')
    if family in ('ko','pko', 'mystery', 'unknown_bounty') and cash is None:
        reasons.append('BOUNTY_VALUE_OR_ACTIVATION_UNCONFIRMED')
    return dict(kind=family, entry_type=entry, source=source, mode=lookup_mode,
                stage=stage, bounty_active=active, bounty_head_bb=bounty_bb,
                cash_fraction=fraction, immediate_cash_bb=cash,
                bounty_bb_per_unit=bounty_bb_per_unit,
                future_progressive_value_included=False,
                reference_reasons=reasons,
                meaning='Entrada/reentrada não substitui modalidade; bounty desconhecido não é dinheiro confirmado.')


def for_target(profile, *, units=None, fresh=False, seat=None, unit='unknown'):
    """Bind a live progressive head to this frame's actual target, never a global head.

    A fixed KO head can be configured globally. PKO needs a fresh target read and
    a declared currency-to-BB model. Manual study calls resolve() directly.
    """
    answer=dict(profile)
    if profile['kind']!='pko':return answer
    rate=1.0 if unit=='bb' else profile.get('bounty_bb_per_unit');fraction=profile.get('cash_fraction')
    if fresh and seat is not None and finite(units) and finite(rate) and rate>0 and finite(fraction):
        head=units*rate
        if math.isfinite(head):
            answer.update(bounty_head_bb=head,immediate_cash_bb=head*fraction,
                          target_bounty_units=units,target_bounty_unit=unit,target_seat=seat,
                          amount_source='fresh_target_bb' if unit=='bb' else 'fresh_target_read_and_declared_conversion')
            return answer
    answer.update(immediate_cash_bb=None,target_seat=seat,amount_source='unconfirmed_target_head')
    answer['reference_reasons']=[*profile['reference_reasons'],'PKO_TARGET_HEAD_OR_CONVERSION_UNCONFIRMED']
    return answer


def cash_call_ev(*, equity, win_probability, pot_bb, to_call_bb, profile,
                 covers_target, heads_up):
    """Terminal HU chip-EV + immediate cash only; split pots do not earn a bounty.

    P includes the opponent's contestable bet. Coverage must be confirmed, not
    inferred merely from a large hero stack. Multiway requires a side-pot model.
    """
    if not all(finite(v) for v in (equity, win_probability, pot_bb, to_call_bb)) or not 0 <= win_probability <= equity <= 1:
        raise ValueError('Entradas inválidas para EV do call.')
    cash = profile.get('immediate_cash_bb')
    eligible = covers_target is True and heads_up is True and finite(cash)
    bonus = win_probability * cash if eligible else 0.0
    chip_ev = equity * (pot_bb + to_call_bb) - to_call_bb
    return dict(chip_call_ev_bb=chip_ev, immediate_bounty_ev_bb=bonus,
                call_ev_bb=chip_ev + bonus, bounty_applied=eligible and cash > 0,
                scope='terminal_HU_chip_EV_no_sidepots_no_future_progressive_ICM',
                bounty_reason='CONFIRMED_COVERAGE_CASH' if eligible else 'NO_CONFIRMED_HU_COVERAGE_CASH')
