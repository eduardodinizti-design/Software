"""Direct 5–7 card evaluation; same ordering as the independent five-card reference."""
from collections import Counter
from .postflop import RANKS


def straight_high(values):
    values=set(values)
    if 14 in values: values.add(1)
    for high in range(14,4,-1):
        if all(v in values for v in range(high-4,high+1)): return high
    return 0


def rank_hand(cards):
    if not 5<=len(cards)<=7: raise ValueError('Avaliador exige cinco a sete cartas.')
    values=[RANKS.index(c[0])+2 for c in cards]
    counts=Counter(values);ordered=sorted(counts,reverse=True)
    suits={s:[] for s in 'cdhs'}
    for card,value in zip(cards,values): suits[card[1]].append(value)
    flush=next((sorted(v,reverse=True) for v in suits.values() if len(v)>=5),None)
    if flush:
        straight=straight_high(flush)
        if straight: return (8,straight)
    quads=[v for v in ordered if counts[v]==4]
    if quads: return (7,quads[0],max(v for v in ordered if v!=quads[0]))
    trips=[v for v in ordered if counts[v]>=3]
    if trips:
        pairs=[v for v in ordered if v!=trips[0] and counts[v]>=2]
        if pairs: return (6,trips[0],pairs[0])
    if flush: return (5,*flush[:5])
    straight=straight_high(ordered)
    if straight: return (4,straight)
    if trips: return (3,trips[0],*[v for v in ordered if v!=trips[0]][:2])
    pairs=[v for v in ordered if counts[v]>=2]
    if len(pairs)>=2: return (2,*pairs[:2],max(v for v in ordered if v not in pairs[:2]))
    if pairs: return (1,pairs[0],*[v for v in ordered if v!=pairs[0]][:3])
    return (0,*ordered[:5])
