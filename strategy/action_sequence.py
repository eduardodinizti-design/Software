"""B07 — replay da SEQUÊNCIA de ações pré-flop (plano de evolução do cérebro).

Dada uma lista de ações CONFIRMADAS (posts, limp/call, raise, fold, check,
all-in), reconstrói quantos AUMENTOS houve e o direito de reabrir, e ROTULA o
nível: unopened / limped / open / 3bet / 4bet / 5bet+. Diferencia open, 3bet e
4bet COM histórico; sequência ausente ou ambígua fica `pending`, sem inventar
quem agiu. Reaproveita as regras e o vocabulário de `preflop_study.reconstruct`
(mesmas invariantes de ficha/turno/reabertura), numa forma leve p/ o estado ao
vivo. PURO: sem captura nem clique.

Vocabulário de evento (position-based): {position, type, amount_bb}, type em
post_sb | post_bb | post_ante | limp | call | raise | fold | check | all_in.
'limp' = call voluntário do BB sem raise; 'all_in' = raise/call que gasta todo o
stack (tratado como raise se reabre, senão call).
"""
from decimal import Decimal

from preflop_study import amount, POSITIONS

_RAISE_TYPES = ('raise', 'all_in')
_LABELS = {0: 'unopened', 1: 'open', 2: '3bet', 3: '4bet'}


def _pending(reason, **extra):
    return dict(status='PENDING', reason=reason, label='pending', pending=True,
                n_raises=0, aggressor=None, limpers=[], folded=[], active=[],
                pot=0.0, reopened=False, contributions={}, **extra)


def replay(events, participants, *, blinds=(Decimal('0.5'), Decimal(1))):
    """Reconstrói o estado de apostas pré-flop a partir de `events` (confirmados).

    participants = {position: start_stack_bb}. Devolve dict com status OK|PENDING,
    label (nível), n_raises, aggressor (última agressão), limpers, folded, active
    (não foldados), pot, reopened (a última agressão reabriu a ação), contributions
    e chip_conservation. Sequência vazia/sem blinds ou lance inválido -> PENDING
    (não inventa)."""
    if not isinstance(events, list) or not events:
        return _pending('EMPTY_SEQUENCE')
    if not isinstance(participants, dict) or not participants:
        return _pending('NO_PARTICIPANTS')
    try:
        start = {p: amount(v) for p, v in participants.items()}
    except Exception:                                  # noqa: BLE001
        return _pending('INVALID_START_STACKS')

    sb, bb = blinds
    bets = {p: Decimal(0) for p in start}
    stacks = dict(start)
    folded, limpers = set(), []
    high = Decimal(0)
    min_raise = bb
    n_raises = 0
    aggressor = None
    reopened = False
    voluntary = False
    posted_bb = False

    for ev in events:
        if not isinstance(ev, dict):
            return _pending('INVALID_EVENT')
        pos, typ = ev.get('position'), ev.get('type')
        if pos not in start or pos in folded:
            return _pending('INVALID_PARTICIPANT', reason_pos=pos)
        try:
            paid = amount(ev.get('amount_bb', 0))
        except Exception:                              # noqa: BLE001
            return _pending('INVALID_AMOUNT')
        if typ in ('post_sb', 'post_bb', 'post_ante'):
            if voluntary:
                return _pending('FORCED_BET_AFTER_VOLUNTARY')
            if typ == 'post_bb':
                posted_bb = True
        elif typ == 'fold':
            voluntary = True
            folded.add(pos)
        elif typ == 'check':
            voluntary = True
            if high - bets[pos] > 0:
                return _pending('ILLEGAL_CHECK')
        elif typ in ('limp', 'call'):
            voluntary = True
            owed = high - bets[pos]
            if typ == 'limp' and n_raises > 0:
                return _pending('LIMP_AFTER_RAISE')
            if n_raises == 0 and typ in ('limp', 'call') and owed <= bb:
                limpers.append(pos)                    # call ao nível do BB = limp
        elif typ in _RAISE_TYPES:
            voluntary = True
            target = bets[pos] + paid
            if target <= high:
                if typ == 'all_in':                    # all-in curto que não reabre = call
                    owed = high - bets[pos]
                else:
                    return _pending('RAISE_NOT_ABOVE_HIGH')
            else:
                reopened = (target - high) >= min_raise
                if reopened:
                    min_raise = target - high
                n_raises += 1
                aggressor = pos
        else:
            return _pending('UNKNOWN_ACTION', reason_type=typ)
        if paid > stacks[pos]:
            return _pending('STACK_OVERDRAW')
        stacks[pos] -= paid
        if typ != 'post_ante':
            bets[pos] += paid
            high = max(high, bets[pos])

    if not posted_bb:
        return _pending('BLINDS_MISSING')

    label = _LABELS.get(n_raises, '5bet+') if n_raises else ('limped' if limpers else 'unopened')
    pot = sum(bets.values()) + Decimal(0)
    active = [p for p in start if p not in folded]
    conserved = (sum(stacks.values()) + sum(bets.values())) == sum(start.values())
    return dict(status='OK', label=label, pending=False, n_raises=n_raises,
                aggressor=aggressor, limpers=limpers, folded=sorted(folded),
                active=active, pot=float(pot), reopened=reopened,
                contributions={p: float(bets[p]) for p in start},
                chip_conservation=conserved)
