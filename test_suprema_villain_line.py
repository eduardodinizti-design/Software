"""VILLAIN_LINE derivado AO VIVO (Eduardo 24/11): o suprema_state rastreia a sequência de ação por
rua (max chips_round por rua = detecta CHECK-CHECK) e deriva villain_line p/ LIGAR as linhas de
agressão que estavam MORTAS (probe, delayed c-bet, valor fino bet-check-bet). TRAVA anti-spew: só
afirma check-check se a rua foi OBSERVADA (entrada em _street_bet)."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from suprema_state import SupremaTable, advise_from_suprema
from assistir_suprema import load_advisor

_ADV = load_advisor()
TURN = ['Kd', '7s', '2c', '9h']
RIVER = ['Kd', '7s', '2c', '9h', '3d']


def _hu(hero_raises, cards, board, street_bet):
    """Heads-up SB(hero)/BB(vilão). `hero_raises`=hero é o PFR. Monta a rua `board` com o rastro
    de ação `street_bet` ({rua: {max, first}}) e cartas do hero."""
    t = SupremaTable(bb_chips=500)
    t.feed_json({'event': 'gameinfo', 'data': {'game_info': {'dealer_seat': 2}}})
    t.feed_json({'uid': 1, 'event': 'gamestart', 'data': {
        'game_info': {'game_counter': 7, 'dealer_seat': 2}, 'game_seat': {
            '1': {'seat': 2, 'uid': 1, 'coins': 20000, 'chips': 250, 'chips_round': 250, 'role': 82, 'cards': [59, 56]},
            '2': {'seat': 6, 'uid': 3, 'coins': 9500, 'chips': 500, 'chips_round': 500, 'role': 93, 'cards': []}}}})
    hcr, vcr = (1500, 500) if hero_raises else (250, 1500)
    t.feed_json({'uid': 1, 'event': 'moveturn', 'data': {'game_seat': {
        '1': {'seat': 2, 'uid': 1, 'coins': 20000 - hcr, 'chips': hcr, 'chips_round': hcr, 'role': 82, 'cards': [59, 56]},
        '2': {'seat': 6, 'uid': 3, 'coins': 10000 - vcr, 'chips': vcr, 'chips_round': vcr, 'role': 93}}}})
    t.board = list(board)
    t.pot_chips = 3000
    t.players[t.hero_seat]['cards'] = list(cards)
    for p in t.players.values():
        p['chips_round'] = 0.0          # rua nova: sem apostas ainda (hero lidera)
    t._street_bet = street_bet
    return t


def _line(hero_raises, cards, board, street_bet):
    st, _ = _hu(hero_raises, cards, board, street_bet).to_table_state()
    return (st or {}).get('villain_line')


def _advise(hero_raises, cards, board, street_bet):
    return advise_from_suprema(_hu(hero_raises, cards, board, street_bet), _ADV)


FLOP_CC = {3: {'max': 0.0, 'first': None}}
FLOP_BET_TURN_CC = {3: {'max': 600.0, 'first': 2}, 4: {'max': 0.0, 'first': None}}


# ---- derivação ----
def test_deriva_delayed_hero_pfr():
    assert _line(True, ['Kh', 'Td'], TURN, FLOP_CC) == 'delayed'


def test_deriva_checked_back_villain_pfr():
    assert _line(False, ['Kh', 'Td'], TURN, FLOP_CC) == 'checked_back'


def test_deriva_checked_turn_bet_check():
    assert _line(True, ['Kh', 'Td'], RIVER, FLOP_BET_TURN_CC) == 'checked_turn'


# ---- TRAVA anti-spew ----
def test_trava_flop_nao_observado_sem_linha():
    # _street_bet vazio = nunca viu o flop -> NÃO inventa check-check
    assert _line(False, ['Kh', 'Td'], TURN, {}) is None


def test_trava_flop_com_aposta_sem_linha():
    assert _line(False, ['Kh', 'Td'], TURN, {3: {'max': 600.0, 'first': 6}}) is None


# ---- e2e: as linhas DISPARAM (agressão viva) ----
def test_probe_dispara_bet():
    r = _advise(False, ['Kh', 'Td'], TURN, FLOP_CC)
    assert r.get('recommended') == 'bet'
    assert 'PROBE_WIDE' in r.get('caveats', [])


def test_delayed_dispara_bet():
    r = _advise(True, ['Kh', 'Td'], TURN, FLOP_CC)
    assert r.get('recommended') == 'bet'
    assert 'DELAYED_CBET_WIDE' in r.get('caveats', [])


def test_bet_check_bet_dispara_bet():
    r = _advise(True, ['Kh', 'Td'], RIVER, FLOP_BET_TURN_CC)
    assert r.get('recommended') == 'bet'
    assert 'BET_CHECK_BET_RIVER_THIN_VALUE' in r.get('caveats', [])


def test_sem_sinal_check_oop_preservado():
    # turn normal (flop teve aposta, sem check-check) OOP marginal -> segue checando (não quebrou)
    r = _advise(True, ['Qh', 'Jd'], TURN, {3: {'max': 600.0, 'first': 2}})
    assert r.get('recommended') == 'check'
    assert 'CBET_OOP_CHECK_MARGINAL' in r.get('caveats', [])


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n]()
            print('OK', n)
    print('TODOS PASSARAM')
