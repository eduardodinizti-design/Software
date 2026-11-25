"""SB-complete: JAMAIS foldar por poucos blinds (LEI Eduardo 25/11, pós-mortem da sessão).

No pós-mortem o Henrique foldou KQo, A7o, Q8s, K9s no SB pagando só 0,5-0,75bb (completar vs BB),
recebendo 5:1 a 7:1 de odds imediatas. Isso é a ATROCIDADE que o Eduardo proíbe — "foldar pra
poucos blinds pra trás". Causa-raiz: o spot SB-vs-BB-complete cai em NO_VALIDATED_NODE_FOR_CONTEXT
e o default é FOLD.

Guarda BOUNDED e platform-neutral (advisory). Dispara SÓ quando TODAS valem:
  - a recomendação é FOLD (status ADVICE);
  - pré-flop (board vazio);
  - o hero está no SB;
  - o to_call é IRRISÓRIO: 0 < to_call <= MAX_COMPLETE_TO_CALL (<=0,75bb = puro COMPLETE vs BB;
    um raise REAL vs o SB levaria o to_call a >= 1,5bb, então aqui NÃO há raise a enfrentar).

Promoção:
  - se o GTO já ABRE a mão em freq mista (>=OPEN_MIN_MIX) -> fold->raise (ROUBA, open 2X, LEI de size);
  - senão -> fold->call (COMPLETA). Jamais foldar por <=0,75bb.

Direção SEGURA (como o never_walk / never_fold_free): no pior caso completamos uma mão marginal OOP
por meia cega (perda minúscula); nunca cometemos a atrocidade de ceder a mão de graça. Puro: não lê
tela, não clica. Caveat SB_COMPLETE_NEVER_FOLD_CHEAP.
"""
from __future__ import annotations

MAX_COMPLETE_TO_CALL = 0.75   # <=0,75bb no SB = completar vs BB (um raise real daria >=1,5bb)
OPEN_MIN_MIX = 0.10           # promove fold->raise só se o GTO abre a mão em >= 10% (borderline)
OPEN_MULTIPLIER = 2.0         # open 2X (LEI de size do open)

_AGGR = ('raise', 'three_bet', 'open', 'open_raise', 'all_in', 'four_bet', 'isolate', 'iso')


def _open_in_mix(mix):
    """Ação AGRESSIVA (open/raise) de MAIOR freq no mix, se >= OPEN_MIN_MIX; senão None."""
    best, bf = None, 0.0
    for m in (mix or []):
        if not isinstance(m, dict) or m.get('action') not in _AGGR:
            continue
        try:
            f = float(m.get('frequency') or 0.0)
        except (TypeError, ValueError):
            f = 0.0
        if f > bf:
            best, bf = m.get('action'), f
    return best if bf >= OPEN_MIN_MIX else None


def never_fold_sb_complete(advice, state):
    """Promove fold->raise/call quando foldar seria ceder o SB por poucos blinds. Senão, inalterada.
    BOUNDED: só toca um FOLD pré-flop no SB com to_call minúsculo; nunca um call/raise/check já dado."""
    if not isinstance(advice, dict) or advice.get('status') != 'ADVICE':
        return advice
    if advice.get('recommended') != 'fold':
        return advice
    st = state or {}
    if st.get('board'):
        return advice                                       # só pré-flop
    if (st.get('positions') or {}).get('hero') != 'SB':
        return advice                                       # só no SB
    tocall = (st.get('to_call') or {}).get('to_call_bb')
    if not (isinstance(tocall, (int, float)) and 0 < tocall <= MAX_COMPLETE_TO_CALL):
        return advice                                       # precisa ser um COMPLETE irrisório vs BB
    act = _open_in_mix(advice.get('mix'))
    if act:                                                 # o GTO abre a mão -> ROUBA (open 2X)
        return dict(advice, recommended='raise',
                    sizing=dict((advice.get('sizing') or {}), multiplier=OPEN_MULTIPLIER),
                    exploit=dict(base='fold', to='raise', reason='SB_COMPLETE_NEVER_FOLD_CHEAP'),
                    caveats=list(advice.get('caveats') or []) + ['SB_COMPLETE_NEVER_FOLD_CHEAP'])
    return dict(advice, recommended='call',                 # senão COMPLETA (jamais folda por <=0,75bb)
                exploit=dict(base='fold', to='call', reason='SB_COMPLETE_NEVER_FOLD_CHEAP'),
                caveats=list(advice.get('caveats') or []) + ['SB_COMPLETE_NEVER_FOLD_CHEAP'])
