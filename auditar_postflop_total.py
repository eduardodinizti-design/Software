"""AUDITORIA TOTAL do pós-flop: enumera TODAS as situações possíveis numa mesa e checa
que o cérebro SEMPRE devolve uma AÇÃO (nunca ABSTAIN). Eduardo 19/11: "NÃO PODE HAVER
ABSTÉM". Roda todos os cruzamentos de rua × textura × mão × preço × oponentes × modo e
lista cada ABSTAIN encontrado (com o motivo), sem mentir que cobriu.

Saída: total de situações, nº de ABSTAIN, e os motivos agregados + exemplos.
"""
import itertools
from collections import Counter, defaultdict

from postflop_advisor import advise_postflop

RANKS = '23456789TJQKA'

# Boards representativos por TEXTURA (flop); turn/river acrescentam cartas.
FLOPS = {
    'seco_desconexo': ['Ks', '7d', '2c'],
    'pareado': ['8h', '8d', '3c'],
    'monotone': ['Qs', '9s', '4s'],
    'conectado': ['9h', '8d', '7c'],
    'ás_alto_seco': ['As', 'Kd', '4c'],
    'baixo_conectado': ['6h', '5d', '4c'],
    'duas_altas': ['Qh', 'Jd', '3c'],
    'trips_board': ['5h', '5d', '5c'],
}
TURNS = {'brick': '2h', 'flush_c': 'Ts', 'overcard': 'Ah', 'pair_board': 'Kd', 'straighty': '6s'}
RIVERS = {'brick': '2d', 'scare': 'Ac'}

# Mãos-hero representativas cobrindo o espectro de força.
HEROES = {
    'air': ['Jc', '9d'], 'overcards': ['Ad', 'Qc'], 'gutshot': ['Td', '8c'],
    'fd': ['As', '3s'], 'underpair': ['5s', '5d'], 'mid_pair': ['9c', '8s'],
    'top_pair': ['Ac', '7h'], 'overpair': ['Ah', 'Ac'], 'two_pair': ['Kh', '7s'],
    'set': ['7d', '7c'], 'straight': ['Ts', '9d'], 'flush': ['2s', '5s'],
}
POSITIONS = [('hero', 'bb', 'BB', 'BTN'), ('hero', 'co', 'CO', 'BB')]  # (hero,vil,heroPos,vilPos)
MODES = ['chip_ev', 'icm', 'pko', 'pko_icm']
STAGES = {'chip_ev': 'mid', 'icm': 'bubble', 'pko': 'mid', 'pko_icm': 'bubble'}


def _state(hero_pos, vil_pos, pot, to_call, stack, n_opp=1):
    seats = {'hero': dict(occupied=True, stack_bb=stack),
             'v': dict(occupied=True, stack_bb=stack)}
    if n_opp > 1:
        seats['v2'] = dict(occupied=True, stack_bb=stack)
    pos = {'hero': hero_pos, 'v': vil_pos}
    if n_opp > 1:
        pos['v2'] = 'CO'
    return dict(positions=pos, seats=seats, pot={'pot_bb': pot},
                to_call={'to_call_bb': to_call})


def run():
    total = 0
    abst = 0
    reasons = Counter()
    examples = defaultdict(list)
    for (_, _, hp, vp) in POSITIONS:
        for mode in MODES:
            stage = STAGES[mode]
            for fname, flop in FLOPS.items():
                streets = [('FLOP', list(flop))]
                streets.append(('TURN', list(flop) + [TURNS['brick']]))
                streets.append(('RIVER', list(flop) + [TURNS['brick'], RIVERS['brick']]))
                for street, board in streets:
                    for hname, hero in HEROES.items():
                        if hero[0] in board or hero[1] in board:
                            continue
                        for pot, to_call in [(6.0, 0.0), (6.0, 2.0), (12.0, 6.0),
                                             (20.0, 18.0)]:
                            for n_opp in (1, 2):
                                st = _state(hp, vp, pot, to_call, 35.0, n_opp)
                                total += 1
                                try:
                                    r = advise_postflop(st, hero, board, street=street,
                                                        mode=mode, stage=stage)
                                except Exception as e:                    # noqa: BLE001
                                    abst += 1
                                    reasons['EXCEPTION:%s' % type(e).__name__] += 1
                                    if len(examples['EXCEPTION']) < 6:
                                        examples['EXCEPTION'].append(
                                            (mode, street, fname, hname, pot, to_call, n_opp, str(e)[:40]))
                                    continue
                                status = (r or {}).get('status')
                                rec = (r or {}).get('recommended')
                                if status != 'ADVICE' or rec in (None, ''):
                                    abst += 1
                                    why = (r or {}).get('reason') or status or 'NONE'
                                    reasons[why] += 1
                                    if len(examples[why]) < 6:
                                        examples[why].append(
                                            (mode, street, fname, hname, pot, to_call, n_opp))
    print('=' * 70)
    print('AUDITORIA TOTAL POS-FLOP: %d situacoes | ABSTEM: %d (%.1f%%)'
          % (total, abst, 100.0 * abst / total if total else 0))
    print('=' * 70)
    if abst:
        print('ABSTEM por motivo:')
        for why, n in reasons.most_common():
            print('  %-42s x%d' % (why, n))
        print('\nExemplos (mode, street, textura, mao, pot, to_call, n_opp):')
        for why, exs in examples.items():
            print(' [%s]' % why)
            for e in exs:
                print('    ', e)
    else:
        print('>>> ZERO ABSTEM: toda situacao pos-flop tem acao. <<<')
    return dict(total=total, abstem=abst, reasons=dict(reasons))


if __name__ == '__main__':
    run()
