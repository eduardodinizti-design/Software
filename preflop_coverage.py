"""Ledger de COBERTURA pré-flop: prova, sem buraco silencioso, o que o pack
responde `solved`, o que cai em `surrogate` (aproximação rotulada) e o que é
`null` (lacuna real a resolver).

Um contexto 9-max totalmente resolvido tem 84 nós:
  open_raise = 8  (UTG..SB abrem; BB nunca é o primeiro a agir)
  vs_open    = 36 (todo par abridor>respondente com o respondente agindo depois)
  vs_3bet    = 36 (todo par abridor>3bettor)
  limp       = 4  (sb_first_in, vs_limp, vs_iso, vs_limp_jam)
Isso casa exatamente com o que o ingestor HRC emite por arquivo (ver hrc_ingest).

Puro/offline: só lê o pack e conta. Não decide estratégia, não clica.
"""
from hrc_ingest import POSITIONS

OPENERS = tuple(p for p in POSITIONS if p != 'BB')        # UTG..SB (8)


def expected_open_raise():
    return set(OPENERS)                                   # 8 heróis


def expected_pairs():
    """Pares (abridor, posterior) com o posterior agindo DEPOIS do abridor. 36."""
    pairs = set()
    for i, op in enumerate(POSITIONS):
        if op == 'BB':
            continue
        for later in POSITIONS[i + 1:]:
            pairs.add((op, later))
    return pairs


EXPECTED = {'open_raise': 8, 'vs_open': 36, 'vs_3bet': 36,
            'sb_first_in': 1, 'vs_limp': 1, 'vs_iso': 1, 'vs_limp_jam': 1}
FULL_CONTEXT_NODES = sum(EXPECTED.values())               # 84


def _ctx_key(node):
    c = node['context']
    return (c['mode'], c['format'], c['stage'], c['players'], c['stack'], node['spread'])


def _present_pairs(nodes, spot):
    """Pares (abridor, posterior) presentes para um spot, normalizando a direção:
    vs_open guarda hero=respondente/vs=abridor; vs_3bet guarda hero=abridor/vs=3bettor."""
    out = set()
    for n in nodes:
        if n['spot'] != spot or not n['vs']:
            continue
        if spot == 'vs_open':
            out.add((n['vs'][0], n['hero']))              # (abridor, respondente)
        elif spot == 'vs_3bet':
            out.add((n['hero'], n['vs'][0]))              # (abridor, 3bettor)
    return out


def coverage_by_context(pack):
    """Para cada contexto presente, devolve contagem por spot, completude e as
    células faltantes (heróis/pares ausentes). Nenhuma lacuna fica implícita."""
    by_ctx = {}
    for n in pack['nodes']:
        by_ctx.setdefault(_ctx_key(n), []).append(n)

    report = {}
    exp_pairs = expected_pairs()
    exp_open = expected_open_raise()
    for ctx, nodes in sorted(by_ctx.items(),
                             key=lambda kv: tuple('' if x is None else str(x) for x in kv[0])):
        counts = {}
        for n in nodes:
            counts[n['spot']] = counts.get(n['spot'], 0) + 1
        present_open = {n['hero'] for n in nodes if n['spot'] == 'open_raise'}
        missing = {
            'open_raise': sorted(exp_open - present_open),
            'vs_open': sorted(exp_pairs - _present_pairs(nodes, 'vs_open')),
            'vs_3bet': sorted(exp_pairs - _present_pairs(nodes, 'vs_3bet')),
            'limp': [k for k in ('sb_first_in', 'vs_limp', 'vs_iso', 'vs_limp_jam')
                     if counts.get(k, 0) == 0],
        }
        total = sum(counts.get(s, 0) for s in EXPECTED)
        report[ctx] = dict(
            counts=counts, total=total, expected=FULL_CONTEXT_NODES,
            completeness=round(total / FULL_CONTEXT_NODES, 4),
            regime=_regime(counts),
            fill={s: '%d/%d' % (counts.get(s, 0), EXPECTED[s]) for s in EXPECTED},
            missing={k: v for k, v in missing.items() if v})
    return report


def _regime(counts):
    """Classifica o REGIME de um contexto pela estrutura presente, para não ler
    uma solve legitimamente estreita (push/fold raso) como 'lacuna':
      raise_tree   open+vs_open+vs_3bet (árvore de raise completa, ~tipicamente >=20bb)
      no_3bet_tree open+vs_open mas sem vs_3bet (3bet é shove, dobrado no vs_open)
      pushfold     só RFI (ex.: chip 8-12bb, solve estreita de SB vs BB)
      sparse       nada de RFI (só limp/outro)"""
    if counts.get('vs_3bet', 0) > 0:
        return 'raise_tree'
    if counts.get('vs_open', 0) > 0:
        return 'no_3bet_tree'
    if counts.get('open_raise', 0) > 0:
        return 'pushfold'
    return 'sparse'


def summarize(pack):
    """Resumo de alto nível: nº de contextos, quantos 100% completos, nós totais,
    distribuição por mode/stage, e a lista de contextos incompletos."""
    rep = coverage_by_context(pack)
    full = [c for c, r in rep.items() if r['completeness'] >= 1.0]
    # near_full = regime de raise completo mas faltando poucas células -> LACUNA REAL
    # a preencher; structural = push/fold ou sem-3bet (estreito por natureza, não gap).
    near_full = {c: r['completeness'] for c, r in rep.items()
                 if r['completeness'] < 1.0 and r['regime'] == 'raise_tree'}
    structural = {c: r['regime'] for c, r in rep.items()
                  if r['completeness'] < 1.0 and r['regime'] != 'raise_tree'}
    by_mode, by_stage, by_regime = {}, {}, {}
    for n in pack['nodes']:
        by_mode[n['context']['mode']] = by_mode.get(n['context']['mode'], 0) + 1
        by_stage[n['context']['stage']] = by_stage.get(n['context']['stage'], 0) + 1
    for r in rep.values():
        by_regime[r['regime']] = by_regime.get(r['regime'], 0) + 1
    return dict(
        contexts=len(rep), contexts_full=len(full),
        contexts_partial=len(rep) - len(full),
        nodes_total=len(pack['nodes']), by_mode=by_mode, by_stage=by_stage,
        by_regime=by_regime,
        near_full_gaps=dict(sorted(near_full.items(), key=lambda kv: kv[1])),
        structural=dict(sorted(structural.items())))


def nearest_stack(target, available):
    """Surrogate de stack: bucket solved mais próximo (|Δ| mínimo). Devolve
    (stack, 'solved') se exato, senão (stack_mais_proximo, 'surrogate')."""
    if not available:
        return None, 'null'
    if target in available:
        return target, 'solved'
    best = min(available, key=lambda s: (abs(s - target), s))
    return best, 'surrogate'


def query_grid(pack, *, stacks, modes_stages, spots=('open_raise',)):
    """Classifica uma GRADE de consulta ao vivo: para cada (mode,format,stage,
    spread,stack,spot), diz solved/surrogate(stack mais próximo)/null. É o mapa
    que o operador usa p/ saber a procedência antes de confiar num nó."""
    present = {}
    for n in pack['nodes']:
        c = n['context']
        present.setdefault((c['mode'], c['format'], c['stage'], n['spread'], n['spot']), set()).add(c['stack'])
    grid = []
    for (mode, fmt, stage, spread) in modes_stages:
        for spot in spots:
            avail = sorted(present.get((mode, fmt, stage, spread, spot), set()))
            for st in stacks:
                chosen, kind = nearest_stack(st, avail)
                grid.append(dict(mode=mode, format=fmt, stage=stage, spread=spread,
                                 spot=spot, stack=st, resolved=chosen, kind=kind))
    return grid


def _cli(argv=None):
    import argparse
    import json
    ap = argparse.ArgumentParser(description='Ledger de cobertura pré-flop de um pack')
    ap.add_argument('pack')
    ap.add_argument('--out', help='grava o ledger detalhado em JSON')
    args = ap.parse_args(argv)
    pack = json.loads(open(args.pack, encoding='utf-8').read())
    s = summarize(pack)
    print('contextos=%d (completos=%d, parciais=%d)  nós=%d'
          % (s['contexts'], s['contexts_full'], s['contexts_partial'], s['nodes_total']))
    print('por mode  :', s['by_mode'])
    print('por stage :', s['by_stage'])
    print('por regime:', s['by_regime'])
    if s['near_full_gaps']:
        print('--- LACUNAS REAIS (árvore de raise quase completa, faltam células) ---')
        for ctx, comp in s['near_full_gaps'].items():
            print('  %.0f%%  %s  faltam=%s'
                  % (comp * 100, ctx, coverage_by_context(pack)[ctx]['missing']))
    if s['structural']:
        print('--- estreitos por natureza (push/fold ou sem-3bet; não é lacuna) ---')
        for ctx, reg in list(s['structural'].items())[:40]:
            print('  %-14s %s' % (reg, ctx))
    if args.out:
        open(args.out, 'w', encoding='utf-8').write(
            json.dumps(coverage_by_context(pack), ensure_ascii=False, default=list))
        print('ledger ->', args.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(_cli())
