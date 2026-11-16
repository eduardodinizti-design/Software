"""Estudo do banco de mãos gravado por `hand_recorder`. PURO: só lê e agrega.

Responde às perguntas de estudo que o Eduardo pediu:
  - por ADVERSÁRIO (id): quantas mãos, resultado líquido (bb), como ele joga (HUD visto).
  - por LINHA (line_key): EV médio por linha -> quais linhas estão MENOS-EV (corrigir) e
    quais são LUCRATIVAS (explorar mais).
  - por SPOT/posição e visão geral.

EV aqui é o `delta_bb` REALIZADO por mão (resultado), não EV teórico — é o ledger do que
aconteceu de fato. Linhas com amostra pequena vêm marcadas (baixa confiança).
"""
from collections import defaultdict

MIN_SAMPLE = 20          # abaixo disto, a média de EV da linha é ruído (marcada low_sample)


def _delta(h):
    d = (h.get('result') or {}).get('delta_bb')
    return d if isinstance(d, (int, float)) else None


def by_opponent(hands):
    """{opponent_id: {hands, net_bb, outcomes, hud_last, categorias}}. Agrega sobre as mãos
    em que o adversário esteve na mesa (pelo id do nameplate)."""
    agg = defaultdict(lambda: dict(hands=0, net_bb=0.0, outcomes=defaultdict(int),
                                   hud_last=None, categories=defaultdict(int)))
    for h in hands:
        d = _delta(h)
        for o in h.get('opponents', []):
            oid = o.get('id')
            if not oid:
                continue
            a = agg[oid]
            a['hands'] += 1
            if d is not None:
                a['net_bb'] += d            # resultado do hero NA mão em que o vilão estava
            a['outcomes'][(h.get('result') or {}).get('outcome', 'unknown')] += 1
            if o.get('hud'):
                a['hud_last'] = o['hud']
            if o.get('category'):
                a['categories'][o['category']] += 1
    return {k: dict(hands=v['hands'], net_bb=round(v['net_bb'], 2),
                    outcomes=dict(v['outcomes']), hud_last=v['hud_last'],
                    categories=dict(v['categories'])) for k, v in agg.items()}


def by_line(hands, *, min_sample=MIN_SAMPLE):
    """{line_key: {n, net_bb, avg_bb, outcomes, low_sample}} ordenado por avg_bb.
    line_key = posição do hero + sequência de ações (sem valores) — ver hand_recorder."""
    agg = defaultdict(lambda: dict(n=0, net_bb=0.0, outcomes=defaultdict(int)))
    for h in hands:
        lk = h.get('line_key') or (h.get('hero') or {}).get('position') or '?'
        d = _delta(h)
        a = agg[lk]
        a['n'] += 1
        if d is not None:
            a['net_bb'] += d
        a['outcomes'][(h.get('result') or {}).get('outcome', 'unknown')] += 1
    rows = []
    for lk, a in agg.items():
        rows.append(dict(line_key=lk, n=a['n'], net_bb=round(a['net_bb'], 2),
                         avg_bb=round(a['net_bb'] / a['n'], 3) if a['n'] else 0.0,
                         outcomes=dict(a['outcomes']), low_sample=a['n'] < min_sample))
    rows.sort(key=lambda r: r['avg_bb'])
    return rows


def leaks(hands, *, min_sample=MIN_SAMPLE, top=10):
    """Linhas MENOS-EV com amostra suficiente (candidatas a corrigir)."""
    rows = [r for r in by_line(hands, min_sample=min_sample)
            if not r['low_sample'] and r['avg_bb'] < 0]
    return rows[:top]


def profitable(hands, *, min_sample=MIN_SAMPLE, top=10):
    """Linhas mais LUCRATIVAS com amostra suficiente (explorar mais)."""
    rows = [r for r in by_line(hands, min_sample=min_sample)
            if not r['low_sample'] and r['avg_bb'] > 0]
    return list(reversed(rows))[:top]


def exploit_targets(hands, *, min_sample=5):
    """Adversários contra quem mais ganhamos/perdemos (id), com amostra mínima."""
    opp = by_opponent(hands)
    rows = [dict(id=k, **v) for k, v in opp.items() if v['hands'] >= min_sample]
    best = sorted(rows, key=lambda r: -r['net_bb'])[:10]
    worst = sorted(rows, key=lambda r: r['net_bb'])[:10]
    return dict(mais_lucrativos=best, mais_custosos=worst)


def summary(hands):
    deltas = [_delta(h) for h in hands if _delta(h) is not None]
    outc = defaultdict(int)
    for h in hands:
        outc[(h.get('result') or {}).get('outcome', 'unknown')] += 1
    reached = defaultdict(int)
    for h in hands:
        reached[h.get('reached_street', 'preflop')] += 1
    return dict(total_hands=len(hands), com_resultado=len(deltas),
                net_bb=round(sum(deltas), 2) if deltas else 0.0,
                bb_por_mao=round(sum(deltas) / len(deltas), 3) if deltas else None,
                outcomes=dict(outc), chegou_ate=dict(reached),
                adversarios_distintos=len(by_opponent(hands)))


def _fmt(hands):
    s = summary(hands)
    L = ['=== BANCO DE MÃOS (estudo) ===',
         'Mãos: %d | com resultado: %d | net: %s bb | bb/mão: %s' % (
             s['total_hands'], s['com_resultado'], s['net_bb'], s['bb_por_mao']),
         'Outcomes: %s | chegou até: %s | adversários: %d' % (
             s['outcomes'], s['chegou_ate'], s['adversarios_distintos']),
         '', 'LINHAS MENOS-EV (corrigir):']
    for r in leaks(hands):
        L.append('  %-28s n=%d avg=%+.3f bb net=%+.1f' % (r['line_key'], r['n'], r['avg_bb'], r['net_bb']))
    L.append('LINHAS LUCRATIVAS (explorar):')
    for r in profitable(hands):
        L.append('  %-28s n=%d avg=%+.3f bb net=%+.1f' % (r['line_key'], r['n'], r['avg_bb'], r['net_bb']))
    return '\n'.join(L)


if __name__ == '__main__':
    import sys
    from hand_recorder import load_hands
    hands = load_hands(sys.argv[1] if len(sys.argv) > 1 else 'logs/maos/maos.jsonl')
    print(_fmt(hands))
