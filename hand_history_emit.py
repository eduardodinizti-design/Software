"""Emissor de HAND HISTORY no formato PokerStars-style que o Hand2Note importa
(espelha os .txt reais de C:\\Hand2Note4Hh\\PPPoker). Recebe uma mão estruturada (o
acumulador da fase 2 do tracker preenche a partir dos dados IL2CPP) e devolve o TEXTO.

PURO: só formata. Valida com `hand_history.parse_hand_histories` (round-trip).

Mão esperada (dict), fichas em CHIPS:
  hand_id, tournament_id, buyin='$30 USD', sb, bb, ante, datetime='YYYY/MM/DD H:MM:SS',
  club_id, table_tag='PPP_13745315 0', max_seats=8, button_seat=2,
  seats=[{seat,player,chips}], hero=<player>, hero_cards=['Qh','6h'],
  posts=[{player,kind('ante'|'sb'|'bb'),amount}],
  streets={'preflop':[{player,action,amount?,to?}], 'flop':[...], 'turn':[...], 'river':[...]},
  board={'flop':['Tc','Ac','3h'],'turn':['Qd'],'river':['2s']},
  uncalled=(amount,player)|None, collected=[{player,amount}], total_pot, rake=0,
  end_datetime
"""
_STREETS = ('preflop', 'flop', 'turn', 'river')


def _cards(cs):
    return ' '.join(cs or [])


def _street_header(street, board):
    if street == 'flop':
        return '*** FLOP *** [%s]' % _cards(board.get('flop'))
    if street == 'turn':
        return '*** TURN *** [%s] [%s]' % (_cards(board.get('flop')), _cards(board.get('turn')))
    if street == 'river':
        return '*** RIVER *** [%s] [%s]' % (
            _cards((board.get('flop') or []) + (board.get('turn') or [])), _cards(board.get('river')))
    return None


def _action_line(a):
    p, act = a['player'], a['action']
    if act in ('folds', 'checks'):
        return '%s: %s' % (p, act)
    if act == 'calls':
        return '%s: calls %s' % (p, a['amount'])
    if act == 'bets':
        return '%s: bets %s' % (p, a['amount'])
    if act == 'raises':
        return '%s: raises %s to %s' % (p, a.get('amount', a.get('to')), a['to'])
    if act == 'all-in':
        return '%s: bets %s and is all-in' % (p, a['amount'])
    return '%s: %s' % (p, act)


def emit_hand(h):
    """Devolve o texto da mão no formato do Hand2Note (uma mão)."""
    L = []
    buyin = h.get('buyin', '$0 USD')
    L.append("PPPoker Hand #%s:  Tournament #%s, %s Hold'em No Limit - Level  (%s/%s - Ante %s) - %s UTC"
             % (h['hand_id'], h.get('tournament_id', ''), buyin, h['sb'], h['bb'],
                h.get('ante', 0), h.get('datetime', '')))
    L.append("Table 'ClubId:%s,Table:%s' %d-max Seat #%d is the button"
             % (h.get('club_id', ''), h.get('table_tag', ''), h.get('max_seats', 8), h['button_seat']))
    for s in h['seats']:
        L.append('Seat %d: %s (%s in chips)' % (s['seat'], s['player'], s['chips']))
    for post in h.get('posts', []):
        kind = {'ante': 'the ante', 'sb': 'small blind', 'bb': 'big blind'}.get(post['kind'], post['kind'])
        L.append('%s: posts %s %s' % (post['player'], kind, post['amount']))
    L.append('*** HOLE CARDS ***')
    if h.get('hero') and h.get('hero_cards'):
        L.append('Dealt to %s [%s]' % (h['hero'], _cards(h['hero_cards'])))
    board = h.get('board', {})
    for street in _STREETS:
        if street != 'preflop':
            hdr = _street_header(street, board)
            if not board.get(street):
                continue                       # rua não alcançada
            L.append(hdr)
        for a in (h.get('streets', {}).get(street) or []):
            L.append(_action_line(a))
    if h.get('uncalled'):
        amt, who = h['uncalled']
        L.append('Uncalled bet (%s) returned to %s' % (amt, who))
    for c in h.get('collected', []):
        L.append('%s collected %s from pot' % (c['player'], c['amount']))
    L.append('*** SUMMARY ***')
    L.append('Total pot %s | Rake %s' % (h.get('total_pot', 0), h.get('rake', 0)))
    allb = [c for cs in (board.get('flop'), board.get('turn'), board.get('river')) for c in (cs or [])]
    if allb:
        L.append('Board [%s]' % _cards(allb))
    if h.get('end_datetime'):
        L.append('Hand ended at %s' % h['end_datetime'])
    return '\n'.join(L)
