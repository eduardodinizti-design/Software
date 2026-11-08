"""End-to-end: read one PPPoker table crop and produce an exploratory read-out.

Ties together the readers (hero cards, table state, hand id, board) and the
PreflopAdvisor so that, for one frame, the bot prints what it sees and what it
would do. Observation only: no capture, no clicks, execution never allowed. The
advice is preflop open-raise only for now (the spot is an explicit assumption)
and abstains post-flop or out of coverage.
"""
import argparse
import json

import cv2

from table_reading.pipeline import configure_ocr
from table_reading.ocr_runtime import ocr_frame
from table_reading.table_state import read_table_state
from table_reading.community_cards import read_board
from table_reading.hand_tracking import read_hand_id
from preflop_advisor import PreflopAdvisor


def read_hero_cards(crop):
    """Hero's two face-up cards, or None when not readable/duplicate."""
    from table_reading.inspect_cards import inspect
    reading = inspect(crop, (0, 0, crop.shape[1], crop.shape[0]))
    cards = [c.get('card_candidate') for c in reading.get('hero_rank_candidates', [])]
    if len(cards) != 2 or not all(cards) or cards[0] == cards[1]:
        return None
    return cards


def advise_table(crop, advisor, *, mode='chip_ev', stage='mid'):
    """Read the table and attach an exploratory recommendation. Pure read; the
    caller wraps it in an ocr_frame so one snapshot reuses OCR."""
    state = read_table_state(crop)
    hand = read_hand_id(crop)
    hero = read_hero_cards(crop)
    board = read_board(crop, hero_cards=hero or [None, None])
    if board.get('cards'):
        advice = dict(status='ABSTAIN', reason='POSTFLOP_NOT_COVERED', exploratory=True, execution_allowed=False)
    elif hero is None:
        advice = dict(status='ABSTAIN', reason='HERO_CARDS_UNKNOWN', exploratory=True, execution_allowed=False)
    else:
        advice = advisor.advise_from_reading(state, hero, mode=mode, stage=stage)
        if isinstance(advice, dict):
            advice.setdefault('caveats', []).append('SPOT_INFERRED_FROM_BETS')
    return dict(hand=hand, hero_cards=hero, board=board, table_state=state, advice=advice)


def _summary(result):
    st = result['table_state']
    occ = [s for s, d in st['seats'].items() if d['occupied']]
    lines = ['=== LEITURA DA MESA (observacao, sem cliques) ===',
             'Mao: %s | Dealer: %s | Pote: %s BB | Pagar: %s BB' % (
                 result['hand'].get('hand_number'), st['dealer'].get('seat'),
                 st['pot'].get('pot_bb'), st['to_call'].get('to_call_bb')),
             'Hero: %s' % (result['hero_cards'] or 'nao identificado'),
             'Assentos ocupados: %d' % len(occ)]
    for seat in occ:
        d = st['seats'][seat]
        lines.append('  %-9s pos=%-5s stack=%s BB%s' % (
            seat, st['positions'].get(seat, '-'), d['stack_bb'],
            ' [DEALER]' if st['dealer'].get('seat') == seat else ''))
    adv = result['advice']
    lines.append('=== RECOMENDACAO (exploratoria, nao-executar) ===')
    if adv.get('status') == 'ADVICE':
        mix = ', '.join('%s %d%%' % (m['action'], round(m['frequency'] * 100)) for m in adv['mix'])
        lines.append('ACAO: %s | mix: %s | stack usado: %sbb | no: %s' % (
            adv['recommended'].upper(), mix, adv['stack_bucket'], adv['node_id']))
    else:
        lines.append('ABSTEM: %s' % adv.get('reason'))
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ranges', required=True, help='nvt-ranges-validados.json')
    p.add_argument('--imagem', required=True, help='Recorte de uma mesa (PNG)')
    p.add_argument('--mode', default='chip_ev')
    p.add_argument('--stage', default='mid')
    p.add_argument('--json', action='store_true')
    args = p.parse_args(argv)
    advisor = PreflopAdvisor.from_file(args.ranges)
    crop = cv2.imread(args.imagem)
    if crop is None:
        raise SystemExit('Nao consegui ler a imagem: ' + args.imagem)
    configure_ocr()
    with ocr_frame():
        result = advise_table(crop, advisor, mode=args.mode, stage=args.stage)
    if args.json:
        print(json.dumps({k: v for k, v in result.items() if k != 'table_state'}, ensure_ascii=False, indent=2, default=str))
    else:
        print(_summary(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
