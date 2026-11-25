"""Homologação pós-flop dos packs SRP (btn_vs_bb_40/100): mede, combo-a-combo no nó de
c-bet do flop, onde a HEURÍSTICA concorda com o SOLVER e tabula os leaks sistemáticos.
Offline, nunca executa. Igual ao `postflop_homologation` do 25bb, mas ciente do formato
srp (agg_actions por flop, stack do pack).

Uso: python homologate_srp.py [strategy_data/postflop_solver/btn_vs_bb_40.json]
"""
import json
import os
import sys
from collections import Counter, defaultdict

from postflop_advisor import advise_postflop
from postflop_eval import hand_strength

DECISIVE = 0.80
_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'strategy_data', 'postflop_solver', 'btn_vs_bb_40.json')


def _parse_flop(s):
    return [s[i:i + 2] for i in (0, 2, 4)]


def _combo_to_cards(combo):
    return [combo[:2], combo[2:]]


def _state(pot_bb, stack_bb):
    return {'positions': {'hero': 'BTN', 'bb': 'BB'},
            'seats': {'hero': {'occupied': True, 'stack_bb': stack_bb},
                      'bb': {'occupied': True, 'stack_bb': stack_bb}},
            'pot': {'pot_bb': pot_bb}, 'to_call': {'to_call_bb': 0}}


def _solver_coarse(actions, freq):
    """'check'/'bet' (argmax check vs soma apostas) e decisividade ('check'/'bet'/'mix')."""
    idx_ck = actions.index('check') if 'check' in actions else 0
    check = freq[idx_ck]
    bet = sum(f for i, f in enumerate(freq) if i != idx_ck)
    coarse = 'check' if check >= bet else 'bet'
    if check >= DECISIVE:
        dec = 'check'
    elif bet >= DECISIVE:
        dec = 'bet'
    else:
        dec = 'mix'
    return coarse, dec


def _heuristic_coarse(hero, board, pot_bb, stack_bb):
    adv = advise_postflop(_state(pot_bb, stack_bb), hero, board, street='FLOP',
                          mode='chip_ev', aggressor='hero', pot_type='single_raised')
    rec = (adv.get('recommended') or '').lower()
    return 'bet' if rec in ('bet', 'raise', 'all_in') else 'check'


def run(data_path=None):
    path = data_path or _DEFAULT
    with open(path, encoding='utf-8') as fh:
        pack = json.load(fh)
    pot_bb, stack_bb = pack.get('pot_bb') or 5.5, pack.get('stack_bb') or 38.0
    total = agree = dec_total = dec_agree = mix_n = 0
    confusion = Counter()
    passivo = Counter()      # heurística check, solver aposta (leak passivo = "morre")
    agressivo = Counter()    # heurística aposta, solver passa
    examples = defaultdict(list)
    for entry in pack['flops']:
        board = _parse_flop(entry['flop'])
        actions = entry.get('agg_actions') or pack.get('our_sizes') or []
        if 'check' not in actions:
            continue
        for combo, freq in (entry.get('agg') or {}).items():
            hero = _combo_to_cards(combo)
            if hero[0] in board or hero[1] in board:
                continue
            s, dec = _solver_coarse(actions, freq)
            h = _heuristic_coarse(hero, board, pot_bb, stack_bb)
            total += 1
            confusion[(s, h)] += 1
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
            cat = (st or {}).get('made', 'unknown')
            if s == 'bet' and h == 'check':
                passivo[cat] += 1
                if len(examples[('passivo', cat)]) < 4:
                    examples[('passivo', cat)].append((entry['flop'], combo))
            else:
                agressivo[cat] += 1
                if len(examples[('agressivo', cat)]) < 4:
                    examples[('agressivo', cat)].append((entry['flop'], combo))
    return dict(
        spot=pack.get('spot'), flops=len(pack['flops']), pot_bb=pot_bb, stack_bb=stack_bb,
        total=total, agree=agree,
        agreement_pct=round(100.0 * agree / total, 2) if total else None,
        decisive_total=dec_total, decisive_agree=dec_agree,
        decisive_agreement_pct=round(100.0 * dec_agree / dec_total, 2) if dec_total else None,
        mixed_nodes=mix_n, mixed_pct=round(100.0 * mix_n / total, 2) if total else None,
        confusion={'solver_%s->heur_%s' % k: v for k, v in sorted(confusion.items())},
        leak_passivo=dict(passivo.most_common()),
        leak_agressivo=dict(agressivo.most_common()),
        examples={'%s/%s' % k: v for k, v in examples.items()})


def main(argv=None):
    a = argv or sys.argv[1:]
    r = run(a[0] if a else None)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
