"""AUDITORIA TOTAL do pré-flop: enumera TODAS as situações (spot × posição × stack ×
modo × mão) e conta os ABSTÉM de verdade (status ABSTAIN / sem ação). OUT_OF_RANGE e
ADVICE (mesmo não-validado) CONTAM como AÇÃO (fold/decisão). Eduardo 19/11: "NÃO PODE
HAVER ABSTÉM". Lista cada abstenção real com o contexto — sem mentir que cobriu.
"""
from collections import Counter, defaultdict

from preflop_advisor import PreflopAdvisor

_VAL = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
_DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'

CORE = ['UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
STACKS = [5, 8, 10, 12, 15, 20, 25, 30, 40, 60, 100]
MODES = [('chip_ev', 'mid'), ('icm', 'bubble'), ('icm', 'ft'), ('pko', 'mid'),
         ('pko_icm', 'bubble')]
HANDS = [['As', 'Ad'], ['As', 'Ks'], ['Ah', 'Kd'], ['Qc', 'Qd'], ['7c', '7d'],
         ['Ad', '5d'], ['Kh', 'Qh'], ['Js', 'Ts'], ['9c', '8c'], ['7h', '2d'],
         ['Qd', '3c'], ['8s', '4h'], ['K2o'[0] + 'd', 'K2o'[1] + 'c']]


def _st(positions, stacks, bets):
    return dict(positions=positions,
                seats={s: dict(stack_bb=stacks.get(s), occupied=True) for s in positions},
                bets=[dict(seat=s, bet_bb=b) for s, b in bets.items()], phase='mid',
                pot={'pot_bb': sum(bets.values()) + 0.0},
                to_call={'to_call_bb': max(bets.values()) if bets else 0.0})


def _scenarios(hero_pos, stk):
    """Gera (nome, state) p/ o hero em `hero_pos` em todos os tipos de spot."""
    out = []
    S = {p: stk for p in CORE}
    # first-in (só blinds)
    out.append(('first_in', _st({'hero': hero_pos, 'sb': 'SB', 'bb': 'BB'},
                                dict(hero=stk, sb=stk, bb=stk), {'sb': 0.5, 'bb': 1.0})))
    # vs_open (um abridor antes do hero)
    for opener in ('UTG', 'LJ', 'HJ', 'CO', 'BTN'):
        if opener == hero_pos:
            continue
        out.append(('vs_open|%s' % opener,
                    _st({'hero': hero_pos, 'o': opener, 'sb': 'SB', 'bb': 'BB'},
                        dict(hero=stk, o=stk, sb=stk, bb=stk),
                        {'o': 2.0, 'sb': 0.5, 'bb': 1.0, 'hero': (1.0 if hero_pos == 'BB' else 0.5 if hero_pos == 'SB' else 0.0)})))
    # vs_3bet (hero abriu, um 3bet)
    for tb in ('BTN', 'SB', 'BB', 'CO'):
        if tb == hero_pos:
            continue
        out.append(('vs_3bet|by_%s' % tb,
                    _st({'hero': hero_pos, 't': tb, 'bb': 'BB'},
                        dict(hero=stk, t=stk, bb=stk), {'hero': 2.0, 't': 6.0, 'bb': 1.0})))
    # squeeze (abridor + caller, hero atrás)
    out.append(('squeeze',
                _st({'hero': hero_pos, 'o': 'UTG', 'c': 'HJ', 'sb': 'SB', 'bb': 'BB'},
                    dict(hero=stk, o=stk, c=stk, sb=stk, bb=stk),
                    {'o': 2.0, 'c': 2.0, 'sb': 0.5, 'bb': 1.0,
                     'hero': (1.0 if hero_pos == 'BB' else 0.0)})))
    # vs_limp (1-2 limpers, hero BB)
    if hero_pos == 'BB':
        out.append(('vs_limp1', _st({'hero': 'BB', 'l': 'CO', 'sb': 'SB'},
                                    dict(hero=stk, l=stk, sb=stk),
                                    {'l': 1.0, 'sb': 0.5, 'hero': 1.0})))
        out.append(('vs_limp2', _st({'hero': 'BB', 'l': 'LJ', 'l2': 'CO', 'sb': 'SB'},
                                    dict(hero=stk, l=stk, l2=stk, sb=stk),
                                    {'l': 1.0, 'l2': 1.0, 'sb': 0.5, 'hero': 1.0})))
    return out


def run():
    import os
    if not (os.path.exists(_VAL) and os.path.exists(_DEEP)):
        print('pacotes de range nao encontrados'); return
    adv = PreflopAdvisor.from_files(_VAL, _DEEP)
    total = 0
    abst = 0
    reasons = Counter()
    examples = defaultdict(list)
    for hero_pos in CORE:
        for stk in STACKS:
            for sname, st in _scenarios(hero_pos, stk):
                for mode, stage in MODES:
                    for hand in HANDS:
                        total += 1
                        try:
                            r = adv.advise_from_reading(st, hand, mode=mode, stage=stage,
                                                        players=9)
                        except Exception as e:                    # noqa: BLE001
                            abst += 1
                            reasons['EXCEPTION:%s' % type(e).__name__] += 1
                            if len(examples['EXCEPTION']) < 6:
                                examples['EXCEPTION'].append((mode, stage, hero_pos, stk, sname, str(e)[:40]))
                            continue
                        status = (r or {}).get('status')
                        # AÇÃO = ADVICE (mesmo validated=false) ou OUT_OF_RANGE (=fold).
                        if status not in ('ADVICE', 'OUT_OF_RANGE'):
                            abst += 1
                            why = (r or {}).get('reason') or status or 'NONE'
                            reasons[why] += 1
                            if len(examples[why]) < 8:
                                examples[why].append((mode, stage, hero_pos, stk, sname,
                                                      ''.join(hand)))
    print('=' * 70)
    print('AUDITORIA TOTAL PRE-FLOP: %d situacoes | ABSTEM: %d (%.2f%%)'
          % (total, abst, 100.0 * abst / total if total else 0))
    print('=' * 70)
    if abst:
        print('ABSTEM por motivo:')
        for why, n in reasons.most_common():
            print('  %-42s x%d' % (why, n))
        print('\nExemplos (mode, stage, heroPos, stack, spot, mao):')
        for why, exs in examples.items():
            print(' [%s]' % why)
            for e in exs:
                print('    ', e)
    else:
        print('>>> ZERO ABSTEM: toda situacao pre-flop tem acao. <<<')
    return dict(total=total, abstem=abst, reasons=dict(reasons))


if __name__ == '__main__':
    run()
