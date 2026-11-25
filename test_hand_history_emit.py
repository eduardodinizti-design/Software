"""Round-trip do emissor: emit_hand(mão) -> texto -> parse_hand_histories -> confere.
Garante que o que emitimos é Hand2Note válido e re-parseável pelo nosso parser."""
from hand_history_emit import emit_hand
from hand_history import parse_hand_histories


def _hand():
    return dict(
        hand_id='137453150000433', tournament_id='13745315', buyin='$30 USD',
        sb=2500, bb=5000, ante=800, datetime='2026/11/18 0:47:13',
        club_id='4023812', table_tag='PPP_13745315 0', max_seats=8, button_seat=2,
        seats=[
            {'seat': 1, 'player': '12357153', 'chips': 87500},
            {'seat': 2, 'player': '13094516', 'chips': 120000},
            {'seat': 5, 'player': '13797173', 'chips': 95000},   # herói
        ],
        hero='13797173', hero_cards=['Qh', '6h'],
        posts=[
            {'player': '12357153', 'kind': 'ante', 'amount': 800},
            {'player': '13094516', 'kind': 'ante', 'amount': 800},
            {'player': '13797173', 'kind': 'ante', 'amount': 800},
            {'player': '13094516', 'kind': 'sb', 'amount': 2500},
            {'player': '13797173', 'kind': 'bb', 'amount': 5000},
        ],
        streets={
            'preflop': [
                {'player': '12357153', 'action': 'raises', 'amount': 10000, 'to': 15000},
                {'player': '13094516', 'action': 'folds'},
                {'player': '13797173', 'action': 'calls', 'amount': 10000},
            ],
            'flop': [
                {'player': '13797173', 'action': 'checks'},
                {'player': '12357153', 'action': 'bets', 'amount': 12000},
                {'player': '13797173', 'action': 'calls', 'amount': 12000},
            ],
            'turn': [
                {'player': '13797173', 'action': 'checks'},
                {'player': '12357153', 'action': 'checks'},
            ],
            'river': [
                {'player': '13797173', 'action': 'bets', 'amount': 20000},
                {'player': '12357153', 'action': 'folds'},
            ],
        },
        board={'flop': ['Tc', 'Ac', '3h'], 'turn': ['Qd'], 'river': ['2s']},
        uncalled=(20000, '13797173'),
        collected=[{'player': '13797173', 'amount': 61400}],
        total_pot=61400, rake=0, end_datetime='2026/11/18 0:48:27',
    )


def test_emit_produces_text():
    txt = emit_hand(_hand())
    assert 'PPPoker Hand #137453150000433' in txt
    assert 'Dealt to 13797173 [Qh 6h]' in txt
    assert '*** FLOP *** [Tc Ac 3h]' in txt
    assert '*** TURN *** [Tc Ac 3h] [Qd]' in txt
    assert '*** RIVER *** [Tc Ac 3h Qd] [2s]' in txt
    assert '*** SUMMARY ***' in txt


def test_roundtrip_header_and_blinds():
    hands = parse_hand_histories(emit_hand(_hand()))
    assert len(hands) == 1
    h = hands[0]
    assert h.id == '#137453150000433'
    assert h.sb == 2500 and h.bb == 5000 and h.ante == 800
    assert h.button_seat == 2


def test_roundtrip_hero_and_cards():
    h = parse_hand_histories(emit_hand(_hand()), preferred_hero='13797173')[0]
    assert h.hero == '13797173'
    assert h.hero_cards == ['Qh', '6h']


def test_roundtrip_players_and_stacks():
    h = parse_hand_histories(emit_hand(_hand()))[0]
    assert set(h.players) == {'12357153', '13094516', '13797173'}
    assert h.players['12357153']['seat'] == 1
    assert h.players['12357153']['stack'] == 87500
    assert h.players['13797173']['seat'] == 5


def test_roundtrip_board():
    h = parse_hand_histories(emit_hand(_hand()))[0]
    assert h.board == ['Tc', 'Ac', '3h', 'Qd', '2s']
    assert h.has_postflop is True


def test_roundtrip_hero_decisions():
    h = parse_hand_histories(emit_hand(_hand()), preferred_hero='13797173')[0]
    acts = [(d.get('action'), d.get('street')) for d in h.hero_decisions] \
        if h.hero_decisions and isinstance(h.hero_decisions[0], dict) else None
    # hero_decisions pode ser lista de dicts ou objetos; valide que capturou ações do herói
    assert h.hero_decisions, "nenhuma decisão do herói parseada"


def test_board_only_to_reached_street():
    hand = _hand()
    hand['board'] = {'flop': ['Tc', 'Ac', '3h']}   # mão parou no flop
    hand['streets'] = {'preflop': hand['streets']['preflop'],
                       'flop': [{'player': '13797173', 'action': 'folds'}]}
    txt = emit_hand(hand)
    assert '*** FLOP ***' in txt
    assert '*** TURN ***' not in txt
    assert '*** RIVER ***' not in txt
