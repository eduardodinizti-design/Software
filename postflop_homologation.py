"""Homologação pós-flop: usa o SOLVER como oráculo p/ medir e expor onde a HEURÍSTICA
erra, nos spots cobertos (offline, nunca executa).

É o degrau que falta p/ tirar o pós-flop da sombra de forma responsável: em vez de
"confiar" na heurística, mede a concordância dela com o solver combo-a-combo e lista os
desvios SISTEMÁTICOS (os leaks). Não muda nada na estratégia; só produz evidência.

Nó medido (o único per-combo do pacote de 100 flops): c-bet do BTN no flop depois do
check do BB (`agg`). Para cada (flop, combo) compara, no nível CHECK vs APOSTA:
  - solver: argmax sobre [check, b33, b50, b70, allin] -> 'check' ou 'bet'.
  - heurística: advise_postflop(pot_type=single_raised, aggressor=hero) -> 'check'/'bet'.
Agrega taxa de acerto e tabula os desvios por categoria de mão (para ver se é um leak
estrutural, ex.: "a heurística dá check em mão X que o solver aposta").
"""
import json
import os
from collections import Counter, defaultdict

import solver_cbet_shadow as scs
from postflop_advisor import advise_postflop
from postflop_eval import hand_strength

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'strategy_data', 'postflop_solver', 'btn_vs_bb_25.json')

# Estado sintético do nó de c-bet do BTN: pote 5,5bb, stack efetivo 23bb, BTN(hero) in
# position, BB já deu check (to_call 0). Determinístico, offline.
POT_BB = 5.5
STACK_BB = 23.0


def _state():
    return {'positions': {'hero': 'BTN', 'bb': 'BB'},
            'seats': {'hero': {'occupied': True, 'stack_bb': STACK_BB},
                      'bb': {'occupied': True, 'stack_bb': STACK_BB}},
            'pot': {'pot_bb': POT_BB}, 'to_call': {'to_call_bb': 0}}


def _combo_to_cards(combo):
    """'AhKd' -> ['Ah','Kd']."""
    return [combo[:2], combo[2:]]


DECISIVE = 0.80          # uma ação (check OU apostar) com freq >= isto -> nó DECISIVO

def _solver_action(freq):
    """Ação coarse do solver: 'check' se o check é a mais jogada, senão 'bet'."""
    # freq ordem: [check, b33, b50, b70, allin]
    if freq[0] >= max(freq[1:]):
        return 'check'
    return 'bet'


def _solver_decisiveness(freq):
    """'check'/'bet'/'mix': decisivo quando check>=DECISIVE ou soma das apostas>=DECISIVE."""
    bet = sum(freq[1:])
    if freq[0] >= DECISIVE:
        return 'check'
    if bet >= DECISIVE:
        return 'bet'
    return 'mix'


def _heuristic_action(hero, board):
    adv = advise_postflop(_state(), hero, board, street='FLOP', mode='chip_ev',
                          aggressor='hero', pot_type='single_raised')
    rec = (adv.get('recommended') or '').lower()
    if rec in ('bet', 'raise', 'all_in'):
        return 'bet'
    return 'check'          # check ou qualquer piso não-agressivo


def run(data_path=DATA, *, min_combo_weight_ignored=True):
    """Roda a homologação e devolve um dicionário com métricas e desvios."""
    with open(data_path, encoding='utf-8') as _fh:
        pack = json.load(_fh)
    total = 0
    agree = 0
    dec_total = 0                             # só nós DECISIVOS do solver (>=80% um lado)
    dec_agree = 0
    mix_n = 0                                 # nós mistos (solver mescla check/aposta)
    confusion = Counter()                     # (solver, heur) -> n
    # Desvios por categoria de mão feita, separados por direção.
    heur_checks_solver_bets = Counter()       # heurística passou, solver aposta (leak passivo)
    heur_bets_solver_checks = Counter()       # heurística apostou, solver passa (leak agressivo)
    examples = defaultdict(list)
    for entry in pack['flops']:
        board = scs._parse_flop(entry['flop'])
        for combo, freq in entry['agg'].items():
            hero = _combo_to_cards(combo)
            # pula combos que colidem com o board (não deveriam existir no agg, guarda)
            if hero[0] in board or hero[1] in board:
                continue
            s = _solver_action(freq)
            h = _heuristic_action(hero, board)
            total += 1
            confusion[(s, h)] += 1
            dec = _solver_decisiveness(freq)
            if dec == 'mix':
                mix_n += 1
            else:
                dec_total += 1
                if dec == h:
                    dec_agree += 1
            if s == h:
                agree += 1
                continue
            st = hand_strength(hero, board)
            cat = st['made'] if st else 'unknown'
            if s == 'bet' and h == 'check':
                heur_checks_solver_bets[cat] += 1
                if len(examples[('passivo', cat)]) < 5:
                    examples[('passivo', cat)].append((entry['flop'], combo, [round(x, 3) for x in freq]))
            else:
                heur_bets_solver_checks[cat] += 1
                if len(examples[('agressivo', cat)]) < 5:
                    examples[('agressivo', cat)].append((entry['flop'], combo, [round(x, 3) for x in freq]))
    return dict(total=total, agree=agree,
                agreement_pct=round(100.0 * agree / total, 2) if total else None,
                decisive_total=dec_total, decisive_agree=dec_agree,
                decisive_agreement_pct=round(100.0 * dec_agree / dec_total, 2) if dec_total else None,
                mixed_nodes=mix_n,
                mixed_pct=round(100.0 * mix_n / total, 2) if total else None,
                confusion={'%s->%s' % k: v for k, v in sorted(confusion.items())},
                leak_passivo_heur_check_solver_bet=dict(heur_checks_solver_bets.most_common()),
                leak_agressivo_heur_bet_solver_check=dict(heur_bets_solver_checks.most_common()),
                examples={'%s/%s' % k: v for k, v in examples.items()})


## ----------------------------------------------------------------------------
## Homologação do TURN com o pacote As7d2c do PR#12 (flop+turn per-combo).
## ----------------------------------------------------------------------------
import gzip
import solver_pr12_shadow as pr12

ROOT_POT = 5.5
ROOT_STACK = 22.5


def _turn_state(pot_bb, hero_pos, villain_pos):
    """Estado EXATO de um nó de turn com to_call=0: como não há aposta pendente, as
    contribuições pós-flop são simétricas, logo stack efetivo = 22,5 − (pot−5,5)/2."""
    stack = round(ROOT_STACK - (pot_bb - ROOT_POT) / 2.0, 3)
    return {'positions': {'hero': hero_pos, 'bb': villain_pos},
            'seats': {'hero': {'occupied': True, 'stack_bb': stack},
                      'bb': {'occupied': True, 'stack_bb': stack}},
            'pot': {'pot_bb': pot_bb}, 'to_call': {'to_call_bb': 0}}


def _turn_solver_coarse(actions, freq):
    """(coarse, decisive) do nó de turn: 'check' vs 'bet' (soma dos sizes de aposta)."""
    idx = {a: i for i, a in enumerate(actions)}
    check = freq[idx['check']] if 'check' in idx else 0.0
    bet = sum(f for a, f in zip(actions, freq) if a != 'check')
    coarse = 'check' if check >= bet else 'bet'
    return coarse, max(check, bet) >= DECISIVE


def run_turn(path=None, *, max_nodes=None):
    """Homologa a decisão de TURN (check-vs-aposta, to_call=0) no board As7d2c do PR#12,
    por ator (BTN e BB). Mesmo método do flop: concordância heurística×solver, split
    decisivo/misto e leaks por categoria de mão. `max_nodes` limita (p/ testes rápidos)."""
    with gzip.open(pr12._data_path(path), 'rb') as fh:
        pack = json.load(fh)
    POS_OF = {'BTN': ('BTN', 'BB'), 'BB': ('BB', 'BTN')}
    total = agree = dec_total = dec_agree = mix_n = 0
    confusion = Counter()
    by_actor = defaultdict(lambda: [0, 0])          # pos -> [total, agree]
    leak_passivo = Counter()                         # heur check, solver bet
    leak_agressivo = Counter()                       # heur bet, solver check
    examples = defaultdict(list)
    seen_nodes = 0
    for key, node in pack['nodes'].items():
        if node['street'] != 'TURN' or 'check' not in node['actions']:
            continue                                 # só nós com decisão check-vs-aposta
        seen_nodes += 1
        if max_nodes and seen_nodes > max_nodes:
            break
        board = node['board']                        # 4 cartas (As7d2c + turn)
        hero_pos, villain_pos = POS_OF[node['actor_pos']]
        state = _turn_state(node['pot_bb'], hero_pos, villain_pos)
        aggressor = 'hero' if hero_pos == 'BTN' else 'BTN'
        actions, combos = node['actions'], node['combos']
        for combo, freq in combos.items():
            hero = [combo[:2], combo[2:]]
            if hero[0] in board or hero[1] in board:
                continue
            s, _dec = _turn_solver_coarse(actions, freq)
            adv = advise_postflop(state, hero, board, street='TURN', mode='chip_ev',
                                  aggressor=aggressor, pot_type='single_raised')
            rec = (adv.get('recommended') or '').lower()
            h = 'bet' if rec in ('bet', 'raise', 'all_in') else 'check'
            total += 1
            confusion[(s, h)] += 1
            by_actor[node['actor_pos']][0] += 1
            if _dec:
                dec_total += 1
            else:
                mix_n += 1
            if s == h:
                agree += 1
                by_actor[node['actor_pos']][1] += 1
                if _dec:
                    dec_agree += 1
                continue
            st = hand_strength(hero, board)
            cat = st['made'] if st else 'unknown'
            tgt = leak_passivo if (s == 'bet' and h == 'check') else leak_agressivo
            tgt[cat] += 1
            tag = 'passivo' if (s == 'bet' and h == 'check') else 'agressivo'
            if len(examples[(tag, cat)]) < 4:
                examples[(tag, cat)].append((''.join(board), combo, node['actor_pos'],
                                             [round(x, 3) for x in freq]))
    return dict(board='As7d2c', total=total, agree=agree,
                agreement_pct=round(100.0 * agree / total, 2) if total else None,
                decisive_total=dec_total, decisive_agree=dec_agree,
                decisive_agreement_pct=round(100.0 * dec_agree / dec_total, 2) if dec_total else None,
                mixed_nodes=mix_n, mixed_pct=round(100.0 * mix_n / total, 2) if total else None,
                by_actor={k: dict(total=v[0], agree=v[1],
                                  pct=round(100.0 * v[1] / v[0], 2) if v[0] else None)
                          for k, v in by_actor.items()},
                confusion={'%s->%s' % k: v for k, v in sorted(confusion.items())},
                leak_passivo_heur_check_solver_bet=dict(leak_passivo.most_common()),
                leak_agressivo_heur_bet_solver_check=dict(leak_agressivo.most_common()),
                examples={'%s/%s' % k: v for k, v in examples.items()})


## ----------------------------------------------------------------------------
## Homologação do TURN a partir dos DUMPS BRUTOS do TexasSolver (multi-board) —
## generaliza o achado de 1 board (PR#12) para o batch de boards que resolvemos.
## ----------------------------------------------------------------------------
import glob as _glob
import re as _re

_AMT = _re.compile(r'([\d.]+)')


def _act_name_raw(a):
    u = a.upper()
    if u.startswith('CHECK'): return 'check'
    if u.startswith('ALLIN') or u.startswith('ALL_IN'): return 'all_in'
    if u.startswith('BET'): return 'bet'
    if u.startswith('RAISE'): return 'raise'
    if u.startswith('CALL'): return 'call'
    if u.startswith('FOLD'): return 'fold'
    return u.lower()


def _amt_of(a):
    m = _AMT.search(a)
    return float(m.group(1)) if m else 0.0


def _collect_turn_nodes_raw(dump, root_board, root_pot=ROOT_POT, root_stack=ROOT_STACK):
    """Varre um dump bruto e devolve os nós de TURN com decisão check-vs-aposta
    (to_call=0). Para cada: board(4), actor(0/1), pot_bb reconstruído, actions(nomes),
    combos{combo:[freqs]}. Reconstrói o pote simulando as contribuições pela linha."""
    out = []

    def walk(node, board, deals, committed, pot):
        if not isinstance(node, dict):
            return
        nt = node.get('node_type')
        if nt == 'action_node':
            actions = node.get('actions') or []
            names = [_act_name_raw(a) for a in actions]
            # to_call=0 <=> existe CHECK no menu (só se pode dar check sem aposta pendente)
            if deals == 1 and 'check' in names:
                ss = (node.get('strategy') or {}).get('strategy') or {}
                if ss:
                    out.append(dict(board=list(board), actor=node.get('player'),
                                    pot_bb=round(pot, 2), actions=names, combos=ss))
            # recursão pelas ações (atualiza committed/pot)
            player = node.get('player')
            for a, child in (node.get('childrens') or {}).items():
                nm = _act_name_raw(a)
                amt = _amt_of(a)
                nc = list(committed)
                npot = pot
                if nm in ('bet', 'raise', 'all_in'):      # 'to' no total da rua
                    inc = max(0.0, amt - committed[player])
                    nc[player] = amt
                    npot = pot + inc
                elif nm == 'call':
                    target = max(committed)
                    inc = max(0.0, target - committed[player])
                    nc[player] = target
                    npot = pot + inc
                walk(child, board, deals, nc, npot)
        elif nt == 'chance_node':
            for card, child in (node.get('dealcards') or {}).items():
                # nova rua: reseta committed da rua (o pote acumulado permanece)
                walk(child, board + [card], deals + 1, [0.0, 0.0], pot)

    walk(dump, list(root_board), 0, [0.0, 0.0], root_pot)
    return out


def run_turn_raw(path, *, max_combos_per_node=80, max_nodes_per_board=200, seed=0):
    """Homologa o TURN (check-vs-aposta) a partir de dump(s) BRUTO(s) do TexasSolver.
    `path`: um .json de dump ou um diretório deles. Reconstrói o estado exato por nó e
    compara a heurística com o solver, agregando POR BOARD e no total. Amostra combos/nós
    (tratável) de forma determinística. Board (flop) inferido do nome do arquivo."""
    import random
    files = ([path] if path.endswith('.json') else sorted(_glob.glob(os.path.join(path, '*.json'))))
    rng = random.Random(seed)
    tot = agree = dec_tot = dec_agree = mix_n = 0
    by_board = {}
    leak_passivo = Counter(); leak_agressivo = Counter()
    POS = {0: 'BTN', 1: 'BB'}            # oop=1=BB age primeiro; player0=IP=BTN
    for f in files:
        tag = os.path.splitext(os.path.basename(f))[0]
        flop = [tag[i:i + 2] for i in (0, 2, 4)] if len(tag) >= 6 else None
        if not flop:
            continue
        with open(f, encoding='utf-8') as fh:
            dump = json.load(fh)
        nodes = _collect_turn_nodes_raw(dump, flop)
        if max_nodes_per_board and len(nodes) > max_nodes_per_board:
            nodes = rng.sample(nodes, max_nodes_per_board)
        b_tot = b_agree = 0
        for nd in nodes:
            actor = nd['actor']
            if actor not in (0, 1):
                continue
            hero_pos, villain_pos = (POS[actor], POS[1 - actor])
            state = _turn_state(nd['pot_bb'], hero_pos, villain_pos)
            aggressor = 'hero' if hero_pos == 'BTN' else 'BTN'
            board = nd['board']
            items = list(nd['combos'].items())
            if max_combos_per_node and len(items) > max_combos_per_node:
                items = rng.sample(items, max_combos_per_node)
            for combo, freq in items:
                hero = [combo[:2], combo[2:]]
                if hero[0] in board or hero[1] in board:
                    continue
                s, dec = _turn_solver_coarse(nd['actions'], freq)
                adv = advise_postflop(state, hero, board, street='TURN', mode='chip_ev',
                                      aggressor=aggressor, pot_type='single_raised')
                rec = (adv.get('recommended') or '').lower()
                h = 'bet' if rec in ('bet', 'raise', 'all_in') else 'check'
                tot += 1; b_tot += 1
                if dec:
                    dec_tot += 1
                else:
                    mix_n += 1
                if s == h:
                    agree += 1; b_agree += 1
                    if dec:
                        dec_agree += 1
                else:
                    st = hand_strength(hero, board)
                    cat = st['made'] if st else 'unknown'
                    (leak_passivo if s == 'bet' else leak_agressivo)[cat] += 1
        by_board[tag] = dict(n=b_tot, agree=b_agree,
                             pct=round(100.0 * b_agree / b_tot, 1) if b_tot else None)
    return dict(boards=len(by_board), total=tot, agree=agree,
                agreement_pct=round(100.0 * agree / tot, 2) if tot else None,
                decisive_agreement_pct=round(100.0 * dec_agree / dec_tot, 2) if dec_tot else None,
                mixed_pct=round(100.0 * mix_n / tot, 2) if tot else None,
                by_board=by_board,
                leak_passivo_heur_check_solver_bet=dict(leak_passivo.most_common()),
                leak_agressivo_heur_bet_solver_check=dict(leak_agressivo.most_common()))


## ----------------------------------------------------------------------------
## Homologação do TURN a partir do PACOTE DESTILADO dos 24 boards (reproduz o achado
## dos dumps brutos sem precisar dos 1,4 GB; só as linhas canônicas de 3 ruas).
## ----------------------------------------------------------------------------
import solver_turn_shadow as sts


def run_turn_pack(path=None, *, max_combos_per_node=80, max_nodes=None, seed=0):
    """Homologa o TURN (check-vs-aposta, to_call=0) LENDO o pacote destilado dos 24
    boards (`turn_pack_24boards.json.gz`). Mesmo método do `run_turn_raw`, mas sobre as
    linhas canônicas (checkthrough/betcall) de cada board. Agrega por board e no total.
    Amostra combos por nó de forma determinística."""
    import random
    pack = sts.load_pack(path)
    if pack is None:
        return dict(boards=0, total=0, agree=0, agreement_pct=None)
    rng = random.Random(seed)
    POS_PAIR = {'BTN': ('BTN', 'BB'), 'BB': ('BB', 'BTN')}
    tot = agree = dec_tot = dec_agree = mix_n = 0
    by_board = {}
    leak_passivo = Counter(); leak_agressivo = Counter()
    seen = 0
    for key, node in pack['nodes'].items():
        if node['street'] != 'TURN' or 'check' not in node['actions']:
            continue
        seen += 1
        if max_nodes and seen > max_nodes:
            break
        board = node['board']
        flop = ''.join(board[:3])
        hero_pos, villain_pos = POS_PAIR[node['actor_pos']]
        state = _turn_state(node['pot_bb'], hero_pos, villain_pos)
        aggressor = 'hero' if hero_pos == 'BTN' else 'BTN'
        items = list(node['combos'].items())
        if max_combos_per_node and len(items) > max_combos_per_node:
            items = rng.sample(items, max_combos_per_node)
        bb = by_board.setdefault(flop, [0, 0])
        for combo, freq in items:
            hero = [combo[:2], combo[2:]]
            if hero[0] in board or hero[1] in board:
                continue
            s, dec = _turn_solver_coarse(node['actions'], freq)
            adv = advise_postflop(state, hero, board, street='TURN', mode='chip_ev',
                                  aggressor=aggressor, pot_type='single_raised')
            rec = (adv.get('recommended') or '').lower()
            h = 'bet' if rec in ('bet', 'raise', 'all_in') else 'check'
            tot += 1; bb[0] += 1
            if dec:
                dec_tot += 1
            else:
                mix_n += 1
            if s == h:
                agree += 1; bb[1] += 1
                if dec:
                    dec_agree += 1
            else:
                st = hand_strength(hero, board)
                cat = st['made'] if st else 'unknown'
                (leak_passivo if s == 'bet' else leak_agressivo)[cat] += 1
    return dict(boards=len(by_board), total=tot, agree=agree,
                agreement_pct=round(100.0 * agree / tot, 2) if tot else None,
                decisive_agreement_pct=round(100.0 * dec_agree / dec_tot, 2) if dec_tot else None,
                mixed_pct=round(100.0 * mix_n / tot, 2) if tot else None,
                by_board={b: dict(n=v[0], agree=v[1],
                                  pct=round(100.0 * v[1] / v[0], 1) if v[0] else None)
                          for b, v in by_board.items()},
                leak_passivo_heur_check_solver_bet=dict(leak_passivo.most_common()),
                leak_agressivo_heur_bet_solver_check=dict(leak_agressivo.most_common()))


def _fmt_turn(r):
    L = ['=== HOMOLOGAÇÃO TURN (check-vs-aposta, As7d2c, PR#12) ===',
         'Decisões (combo×nó de turn to_call=0): %d' % r['total'],
         'Concordância (todos): %s%% (%d/%d)' % (r['agreement_pct'], r['agree'], r['total']),
         'Concordância em nós DECISIVOS: %s%% (%d/%d)' % (
             r['decisive_agreement_pct'], r['decisive_agree'], r['decisive_total']),
         'Nós MISTOS: %d (%s%%)' % (r['mixed_nodes'], r['mixed_pct']),
         'Por ator: %s' % r['by_actor'],
         'Matriz solver->heurística: %s' % r['confusion'],
         '', 'LEAK PASSIVO (heurística CHECK, solver APOSTA):']
    for c, n in r['leak_passivo_heur_check_solver_bet'].items():
        L.append('  %-14s %d' % (c, n))
    L.append('LEAK AGRESSIVO (heurística APOSTA, solver CHECK):')
    for c, n in r['leak_agressivo_heur_bet_solver_check'].items():
        L.append('  %-14s %d' % (c, n))
    return '\n'.join(L)


def _fmt(report):
    L = ['=== HOMOLOGAÇÃO PÓS-FLOP: heurística vs solver (c-bet BTN, flop btn_vs_bb_25) ===',
         'Decisões comparadas (combo×flop): %d' % report['total'],
         'Concordância CHECK-vs-APOSTA (todos os nós): %s%% (%d/%d)' % (
             report['agreement_pct'], report['agree'], report['total']),
         'Concordância em nós DECISIVOS do solver (>=80%% um lado): %s%% (%d/%d)' % (
             report['decisive_agreement_pct'], report['decisive_agree'], report['decisive_total']),
         'Nós MISTOS do solver (mescla check/aposta, ambos plausíveis): %d (%s%%)' % (
             report['mixed_nodes'], report['mixed_pct']),
         'Matriz solver->heurística: %s' % report['confusion'],
         '',
         'LEAK PASSIVO (heurística dá CHECK onde o solver APOSTA), por categoria:']
    for cat, n in report['leak_passivo_heur_check_solver_bet'].items():
        L.append('  %-14s %d' % (cat, n))
    L.append('')
    L.append('LEAK AGRESSIVO (heurística APOSTA onde o solver dá CHECK), por categoria:')
    for cat, n in report['leak_agressivo_heur_bet_solver_check'].items():
        L.append('  %-14s %d' % (cat, n))
    L.append('')
    L.append('Exemplos (flop, combo, freq solver [check,b33,b50,b70,allin]):')
    for k, exs in report['examples'].items():
        L.append('  [%s]' % k)
        for flop, combo, fr in exs:
            L.append('     %s %s -> %s' % (flop, combo, fr))
    return '\n'.join(L)


if __name__ == '__main__':
    import sys
    if '--turn' in sys.argv:
        rep = run_turn()
        print(json.dumps(rep, ensure_ascii=False, indent=2) if '--json' in sys.argv else _fmt_turn(rep))
    else:
        rep = run()
        print(json.dumps(rep, ensure_ascii=False, indent=2) if '--json' in sys.argv else _fmt(rep))
