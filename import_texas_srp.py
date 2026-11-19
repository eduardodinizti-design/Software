"""Destilador GENÉRICO de estudo TexasSolver -> pack de SOMBRA pós-flop (família
IP-abre vs BB, pote simples / single-raised, chip EV).

Generaliza o `HoldemResources/.../import-texas-cbet.py` (que fez o btn_vs_bb_25, só
flop) em três eixos pedidos pelo Eduardo (19/11):

  1. VOCABULÁRIO DE SIZE = o do NOSSO slider pós-flop: 1/3, 1/2, 2/3, all-in
     (t33/t50/t66/allin). O solver usou outros % (ex.: 33% e 60% do pote), mas a gente
     TRADUZ cada aposta pelo valor REAL de fichas ao bucket mais próximo do nosso slider
     e grava o % do solver ao lado (auditável). A sombra fala na nossa língua, não na do
     solver. (EXCEÇÃO de size por SPR = Plano Geométrico por street, dono é
     postflop_adjustments.geometric_street_plan; a sombra só sinaliza, não força.)

  2. FLOP + TURN. O conversor antigo só lia o nó do flop. Aqui lemos:
       - FLOP agg: c-bet do IP depois do check do BB (PER-COMBO).
       - FLOP def: resposta do BB a cada size (AGREGADO do range).
       - TURN agg: 2ª barrela do IP na LINHA PRIMÁRIA (IP aposta o size que mais joga no
         flop, BB paga, BB dá check no turn), por CARTA de turn (AGREGADO do range).
     Honesto: turn é agregado de range (não per-combo) e só da linha primária.

  3. FAMÍLIA de spot p/ APROXIMAÇÃO. O pack declara family='ip_vs_bb_srp' e native_ip
     (BTN). A sombra pode emprestar por aproximação a spots semelhantes (ex.: CO vs BB),
     com caveat, sem refazer o estudo.

Uso: python -I import_texas_srp.py <dir_resultados> <dir_entradas> <spot> "<rótulo>" \
         <open_bb> <versão> <saida.json> [native_ip=BTN]
  dir_resultados: pasta com <flop>.json (dump do TexasSolver, flop+turn).
  dir_entradas:   pasta com <flop>.txt (inputs; traz set_pot/stack/ranges/sizes).

Passivo: só lê os JSON/txt do estudo (dado do solver) e escreve o pack. Não executa nada.
"""
import json
import os
import re
import sys
from itertools import combinations, permutations

R = '23456789TJQKA'
SUITS = 'shdc'
SCHEMA = 'nvt-srp-ipvsbb-shadow.v1'
FAMILY = 'ip_vs_bb_srp'

# NOSSO slider pós-flop. 1/2 pode não aparecer num estudo (o solver pode não usar 50%);
# tudo bem — agg_actions por flop lista só o que de fato existe.
OUR_FRACS = (('t33', 1.0 / 3.0), ('t50', 0.5), ('t66', 2.0 / 3.0))
MIN_RANGE_WEIGHT = 0.25
ACT = re.compile(r'^(CHECK|BET|RAISE|CALL|FOLD|ALLIN)\s*([\d.]*)')
DEF_NAME = {'FOLD': 'fold', 'CALL': 'call', 'RAISE': 'raise', 'ALLIN': 'raise'}


def canon(cards):
    """Forma canônica de um flop (menor string sobre permutações de naipe). IDÊNTICA à do
    solver_cbet_shadow/import-texas-cbet p/ casar o índice por isomorfismo."""
    best = None
    for perm in permutations(SUITS):
        m = dict(zip(SUITS, perm))
        s = ''.join(sorted((c[0] + m[c[1]] for c in cards),
                           key=lambda c: (-R.index(c[0]), c[1])))
        if best is None or s < best:
            best = s
    return best


def expand(label):
    r1, r2 = label[0], label[1]
    if r1 == r2:
        return [r1 + a + r2 + b for a, b in combinations(SUITS, 2)]
    if label.endswith('s'):
        return [r1 + a + r2 + a for a in SUITS]
    return [r1 + a + r2 + b for a in SUITS for b in SUITS if a != b]


def read_inputs(txt_path):
    """Lê pote, stack e ranges ip/oop do input .txt do solver."""
    pot = stack = None
    rng = {}
    for line in open(txt_path, encoding='utf-8'):
        if line.startswith('set_pot'):
            pot = float(line.split()[1])
        elif line.startswith('set_effective_stack'):
            stack = float(line.split()[1])
        elif line.startswith('set_range_'):
            who = line.split()[0][len('set_range_'):]
            body = line.split(None, 1)[1].strip()
            w = {}
            for part in body.split(','):
                lab, _, f = part.partition(':')
                lab = lab.strip()
                if not lab:
                    continue
                for c in expand(lab):
                    w[c] = float(f) if f else 1.0
            rng[who] = w
    return pot, stack, rng


def wkey(w, c):
    return w.get(c, w.get(c[2:] + c[:2], 0.0))


def _bucket(amount, pot_before, stack_eff):
    """Aposta em fichas -> bucket do NOSSO slider (t33/t50/t66/allin), pelo valor REAL.
    Devolve (bucket, pct_do_pote)."""
    if stack_eff is not None and amount >= stack_eff - 1e-6:
        return 'allin', (amount / pot_before if pot_before else None)
    if not pot_before or pot_before <= 0:
        return None, None
    p = amount / pot_before
    if p >= 0.85:                       # aposta enorme sem ser all-in: cola no maior bucket
        return 't66', p
    return min(OUR_FRACS, key=lambda x: abs(x[1] - p))[0], p


def _label_node(node, pot_before, stack_eff, sizes_seen):
    """Dado um action_node com strategy, devolve (nomes, idx_check) traduzindo cada ação
    de aposta ao bucket do nosso slider. Registra o % do solver por bucket em sizes_seen."""
    acts = node['strategy']['actions']
    names = []
    for a in acts:
        m = ACT.match(a)
        if m.group(1) == 'CHECK':
            names.append('check')
        else:
            amt = float(m.group(2))
            b, pct = _bucket(amt, pot_before, stack_eff)
            names.append(b or 'bet')
            if b and pct is not None:
                sizes_seen.setdefault(b, []).append(round(pct, 4))
    return names, (names.index('check') if 'check' in names else None)


def _primary_bet(names, freq, idx_check):
    """Índice do size de aposta que o range MAIS joga no flop (linha primária p/ o turn)."""
    best_i, best_f = None, -1.0
    for i, (nm, f) in enumerate(zip(names, freq)):
        if i == idx_check:
            continue
        if f > best_f:
            best_i, best_f = i, f
    return best_i


def ingest_flop(json_path, txt_path):
    d = json.load(open(json_path, encoding='utf-8'))
    pot, stack, rng = read_inputs(txt_path)
    board = os.path.basename(json_path)[:-5]
    cards = [board[i:i + 2] for i in (0, 2, 4)]
    sizes_seen = {}

    # --- FLOP agg: IP decide c-bet depois do CHECK do BB ---
    agg_node = d['childrens']['CHECK']
    names, idx_ck = _label_node(agg_node, pot, stack, sizes_seen)
    strat = agg_node['strategy']['strategy']
    wip = {c: wkey(rng.get('ip', {}), c) for c in strat}
    agg = {c: [round(x, 4) for x in v] for c, v in strat.items() if wip[c] >= MIN_RANGE_WEIGHT}
    W = sum(wip.values()) or 1.0
    tot = [sum(v[i] * wip[c] for c, v in strat.items()) / W for i in range(len(names))]

    # --- FLOP def: resposta do BB a cada size (agregado do range que chega à aposta) ---
    root = d['strategy']
    ck = root['actions'].index('CHECK')
    woop = {c: wkey(rng.get('oop', {}), c) * v[ck] for c, v in root['strategy'].items()}
    defs = {}
    for a, nm in zip(agg_node['strategy']['actions'], names):
        if nm == 'check':
            continue
        child = agg_node['childrens'].get(a)
        if not child or 'strategy' not in child:
            continue
        ca, cs = child['strategy']['actions'], child['strategy']['strategy']
        Wd = sum(woop.get(c, 0) for c in cs) or 1.0
        f = {}
        for i, x in enumerate(ca):
            k = DEF_NAME.get(ACT.match(x).group(1), x.lower())
            f[k] = f.get(k, 0) + sum(v[i] * woop.get(c, 0) for c, v in cs.items()) / Wd
        defs[nm] = dict(actions=list(f), freq=[round(v, 4) for v in f.values()])

    # --- TURN agg: 2ª barrela do IP na LINHA PRIMÁRIA (IP aposta o size + jogado, BB paga,
    #     BB dá check no turn), por carta de turn, AGREGADO do range do IP que segue a linha.
    turn = {}
    turn_after = None
    pi = _primary_bet(names, tot, idx_ck)
    if pi is not None:
        a_prim = agg_node['strategy']['actions'][pi]
        turn_after = names[pi]
        bet_node = agg_node['childrens'].get(a_prim) or {}
        call = (bet_node.get('childrens') or {}).get('CALL') or {}
        # fichas já investidas por lado nessa linha (flop): o IP apostou amt; pote cresce.
        amt = float(ACT.match(a_prim).group(2)) if ACT.match(a_prim).group(2) else 0.0
        pot_turn = pot + 2 * amt
        stack_turn = (stack - amt) if stack is not None else None
        # peso do combo do IP que chega ao turn ~ peso no range * freq do size primário.
        wturn = {c: wip.get(c, 0.0) * v[pi] for c, v in strat.items()}
        Wt = sum(wturn.values()) or 1.0
        if call.get('node_type') == 'chance_node':
            for tc, tnode in (call.get('dealcards') or {}).items():
                # BB (OOP) age 1º no turn; seguimos o CHECK dele p/ o nó de barrela do IP.
                ipn = tnode
                if tnode.get('player') == 1 and 'CHECK' in (tnode.get('childrens') or {}):
                    ipn = tnode['childrens']['CHECK']
                if 'strategy' not in ipn:
                    continue
                tnames, _ = _label_node(ipn, pot_turn, stack_turn, sizes_seen)
                ts = ipn['strategy']['strategy']
                n = len(tnames)
                tf = [sum(v[i] * wturn.get(c, 0.0) for c, v in ts.items()) / Wt
                      for i in range(n)]
                turn[tc] = dict(actions=tnames, freq=[round(x, 4) for x in tf])

    k = canon(cards)
    flop_sorted = ''.join(sorted(cards, key=lambda c: (-R.index(c[0]), SUITS.index(c[1]))))
    entry = dict(flop=flop_sorted, canon=k,
                 agg_actions=names, agg=agg, freq=[round(x, 4) for x in tot],
                 **({'def': defs} if defs else {}),
                 **({'turn_after': turn_after, 'turn': turn} if turn else {}))
    return entry, pot, stack, {b: round(sum(v) / len(v), 4) for b, v in sizes_seen.items()}


def build(src_res, src_ent, spot, label, open_bb, version, native_ip):
    flops = []
    pot = stack = None
    solver_pct = {}
    skipped = []
    for name in sorted(os.listdir(src_res)):
        if not name.endswith('.json'):
            continue
        board = name[:-5]
        txt = os.path.join(src_ent, board + '.txt')
        if not os.path.exists(txt):
            txt = next((os.path.join(src_ent, f) for f in sorted(os.listdir(src_ent))
                        if f.endswith('.txt')), None)
        try:
            # RESILIENTE: se o solver ainda está rodando, um JSON pode estar meio-escrito
            # (json.load falha) — pula sem derrubar o build. Re-gerar depois pega os prontos.
            entry, p, s, sp = ingest_flop(os.path.join(src_res, name), txt)
        except (ValueError, OSError, KeyError, StopIteration) as e:
            skipped.append('%s (%s)' % (name, type(e).__name__))
            continue
        pot = pot or p
        stack = stack or s
        for b, v in sp.items():
            solver_pct.setdefault(b, []).append(v)
        flops.append(entry)
    if skipped:
        print('  [aviso] %d flop(s) pulados (incompletos/ilegíveis): %s'
              % (len(skipped), ', '.join(skipped[:5]) + (' ...' if len(skipped) > 5 else '')))
    return dict(
        schema=SCHEMA, family=FAMILY, native_ip=(native_ip or 'BTN').upper(),
        spot=spot, label=label, grading='freq', aggressor='ip',
        pot_bb=pot, stack_bb=stack, open_bb=float(open_bb),
        our_sizes=['check', 't33', 't50', 't66', 'allin'],
        solver_pct_by_bucket={b: round(sum(v) / len(v), 4) for b, v in solver_pct.items()},
        min_range_weight=MIN_RANGE_WEIGHT, version=version,
        note='SOMBRA pós-flop família IP-vs-BB SRP chip EV. Sizes no vocabulário do NOSSO '
             'slider (1/3,1/2,2/3,allin), traduzidos pelo valor real de fichas. Flop '
             'per-combo (agg) + def agregado + turn agregado (linha primária). '
             'execution_allowed=False (shadow). Exceção de size = Plano Geométrico por '
             'street (postflop_adjustments), a sombra só sinaliza.',
        flops=flops)


def main(argv=None):
    a = argv or sys.argv[1:]
    if len(a) < 7:
        print(__doc__)
        return 2
    src_res, src_ent, spot, label, open_bb, version, out = a[:7]
    native_ip = a[7] if len(a) > 7 else 'BTN'
    pack = build(src_res, src_ent, spot, label, open_bb, version, native_ip)
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(pack, fh, separators=(',', ':'), ensure_ascii=False)
    nturn = sum(len(f.get('turn') or {}) for f in pack['flops'])
    ncombo = sum(len(f.get('agg') or {}) for f in pack['flops'])
    print('PACK %s: %s' % (spot, out))
    print('  flops=%d  agg_combos=%d  turn_nodes=%d' % (len(pack['flops']), ncombo, nturn))
    print('  pot=%s stack=%s  solver%%/bucket=%s'
          % (pack['pot_bb'], pack['stack_bb'],
             json.dumps(pack['solver_pct_by_bucket'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
