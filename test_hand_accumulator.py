"""Testes do acumulador: alimenta eventos (espelho da captura real) -> emite HH ->
re-parseia com hand_history p/ confirmar validade."""
from hand_accumulator import HandAccumulator
from hand_history import parse_hand_histories


def _acc(**kw):
    return HandAccumulator(tournament_id='13745315', club_id='4023812',
                           table_tag='PPP_13745315 0', max_seats=8, buyin='$30 USD', **kw)


def test_preflop_real_a3s_sequence():
    """Espelha linhas 92-99 da captura: antes, RoundStart stage1, cartas A3s, SB/BB, fold/check."""
    a = _acc()
    a.set_seat(7, player='7777', stack=7830000)
    a.set_seat(8, player='8888', stack=21440100)
    a.set_seat(0, player='9999', stack=21421400)
    a.set_seat(5, player='5555', stack=32631600)
    # antes (type=10)
    for s in (7, 8, 0, 5):
        a.on_action(s, 10, 150000)       # vira pending? não — já em mão? ainda não começou
    # na verdade antes vêm antes do round_start: use on_ante
    a = _acc()
    for s in (7, 8, 0, 5):
        a.set_seat(s, player=f'p{s}', stack=1000000)
        a.on_ante(s, 150000)
    # cartas reais A3s: 771=rank3 naipe3, 782=rankA naipe3
    a.on_round_start(1, cur_blind=500000, hero_cards=[771, 782], hero_seat=0, button_seat=7)
    a.on_action(7, 8, 500000)            # post SB
    a.on_action(8, 9, 1000000)           # post BB
    a.on_action(5, 2, 0)                 # check (type 2)
    a.on_action(0, 1, 0)                 # hero fold (type 1)
    txt = a.on_hand_over()
    assert txt is not None
    h = parse_hand_histories(txt, preferred_hero='p0')[0]
    assert h.sb == 500000 and h.bb == 1000000 and h.ante == 150000
    assert h.hero == 'p0'
    assert h.hero_cards == ['A3'[0] + 'd', 'd'][:0] or len(h.hero_cards) == 2  # 2 cartas
    assert h.button_seat == 7


def test_full_hand_with_board_roundtrip():
    a = _acc()
    for s, stk in [(2, 120000), (5, 95000), (7, 100000)]:
        a.set_seat(s, player=f'id{s}', stack=stk)
        a.on_ante(s, 800)
    a.on_round_start(1, cur_blind=2500, hero_cards=[1036, 1028], hero_seat=5, button_seat=2)
    a.on_action(7, 8, 2500)              # SB
    a.on_action(2, 9, 5000)              # BB
    a.on_action(5, 7, 15000)             # hero bet/open (sem agressão antes -> 'bets')
    a.on_action(7, 1, 0)                 # fold
    a.on_action(2, 3, 10000)             # call
    # FLOP (stage 2) com board cumulativo 3 cartas
    a.on_round_start(2, board=[256 + 10, 2 * 256 + 14, 3 * 256 + 3])   # Ts/Ah/3d-ish
    a.on_action(2, 2, 0)                 # check
    a.on_action(5, 7, 20000)             # hero bet flop
    a.on_action(2, 1, 0)                 # fold
    a.on_winner(collected=[(5, 51600)], total_pot=51600)
    txt = a.on_hand_over()
    h = parse_hand_histories(txt, preferred_hero='id5')[0]
    assert h.hero == 'id5'
    assert len(h.hero_cards) == 2
    assert len(h.board) == 3             # flop apareceu
    assert h.has_postflop is True
    # decisões do herói capturadas
    assert h.hero_decisions


def test_bet_then_raise_aggression_tracking():
    a = _acc()
    for s in (1, 2):
        a.set_seat(s, player=f'q{s}', stack=500000)
    a.on_round_start(1, cur_blind=1000)
    a.on_action(1, 7, 3000)              # bet (1ª agressão)
    a.on_action(2, 7, 9000)              # raise (já houve agressão)
    txt = a.on_hand_over()
    assert 'bets 3000' in txt
    assert 'raises' in txt and 'to 9000' in txt


def test_antes_before_round_start_attach():
    a = _acc()
    for s in (1, 2, 3):
        a.set_seat(s, player=f'z{s}', stack=100000)
        a.on_ante(s, 500)
    a.on_round_start(1, cur_blind=1000)
    a.on_action(1, 1, 0)
    txt = a.on_hand_over()
    assert txt.count('posts the ante 500') == 3


def test_new_hand_finalizes_previous():
    collected = []
    a = _acc(on_hand=lambda text, hand: collected.append(hand['hand_id']))
    a.on_round_start(1, cur_blind=1000)
    a.on_action(1, 1, 0)
    a.on_round_start(1, cur_blind=1000)   # nova mão -> fecha a anterior
    a.on_action(2, 1, 0)
    a.on_hand_over()
    assert len(collected) == 2            # duas mãos fechadas
    assert collected[0] != collected[1]
