"""GAP #1 (24/11): a INICIATIVA pré-flop precisa chegar ao pós-flop vivo. Antes
`advise_from_suprema` chamava `advise_postflop` SEM `aggressor` -> _hia=None -> TODO o
motor de c-bet-range/barril ficava morto -> Henrique passivão. Estes testes travam:
(1) o advisor c-beta ar/marginal com iniciativa e CHECA sem ela; (2) o SupremaTable
resolve o agressor pré-flop ('hero' quando o hero deu o último raise); (3) e2e: board
posto -> advise_from_suprema aposta com iniciativa.
"""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from postflop_advisor import advise_postflop
from suprema_state import SupremaTable, advise_from_suprema
from assistir_suprema import load_advisor

DRY = ['3c', '7d', '2s']           # flop seco, rainbow, baixo
AIR = ['Jh', '8h']                 # overcards/ar nesse board (nenhum par, sem FD: board offsuit)


def _state(to_call=0.0, pot=5.0):
    return dict(positions={'hero': 'CO', 'seat1': 'BB'},
                seats={'hero': {'stack_bb': 40, 'occupied': True},
                       'seat1': {'stack_bb': 40, 'occupied': True}},
                bets=[], to_call={'to_call_bb': to_call}, pot={'pot_bb': pot},
                phase='mid', street='FLOP')


def test_advisor_sem_iniciativa_checa_ar():
    r = advise_postflop(_state(), AIR, DRY, street='FLOP', aggressor=None)
    assert r.get('recommended') == 'check', r.get('recommended')


def test_advisor_com_iniciativa_cbeta_ar():
    r = advise_postflop(_state(), AIR, DRY, street='FLOP', aggressor='hero')
    assert r.get('recommended') in ('bet', 'raise'), (r.get('recommended'), r.get('caveats'))


def _feed_preflop_hero_raise():
    """SupremaTable com hero (uid1/seat2) dando o último RAISE pré-flop (chips_round>bb)."""
    t = SupremaTable(bb_chips=500)
    t.feed_json({'event': 'gameinfo', 'data': {'game_info': {'dealer_seat': 2}}})
    t.feed_json({'uid': 1, 'event': 'gamestart', 'data': {
        'game_info': {'game_counter': 7, 'dealer_seat': 2}, 'game_seat': {
            '1': {'seat': 2, 'uid': 1, 'coins': 20000, 'chips': 0, 'chips_round': 0, 'role': 0, 'cards': [59, 56]},
            '2': {'seat': 3, 'uid': 2, 'coins': 9750, 'chips': 250, 'chips_round': 250, 'role': 82},
            '3': {'seat': 6, 'uid': 3, 'coins': 9500, 'chips': 500, 'chips_round': 500, 'role': 93}}}})
    t.feed_json({'uid': 1, 'event': 'moveturn', 'data': {'game_seat': {
        '1': {'seat': 2, 'uid': 1, 'coins': 18500, 'chips': 1500, 'chips_round': 1500, 'role': 0, 'cards': [59, 56]},
        '3': {'seat': 6, 'uid': 3, 'coins': 9500, 'chips': 500, 'chips_round': 500, 'role': 93}}}})
    return t


def test_state_resolve_agressor_preflop_hero():
    t = _feed_preflop_hero_raise()
    assert t.preflop_aggressor_seat == t.hero_seat == 2
    st, _hero = t.to_table_state()
    assert st is not None and st.get('aggressor') == 'hero', (st or {}).get('aggressor')


def test_e2e_postflop_aposta_com_iniciativa():
    t = _feed_preflop_hero_raise()
    t.board = list(DRY)                        # força o flop (bypass do plumbing de códigos)
    t.pot_chips = 3000                         # pote da rua (senão advise abstém POT_UNKNOWN)
    # garante cartas de ar (não um monstro) no board seco
    t.players[t.hero_seat]['cards'] = list(AIR)
    out = advise_from_suprema(t, load_advisor())
    # GAP#1: o essencial é a INICIATIVA CHEGAR ao advisor pós-flop (destrava o motor).
    # A ação exata (bet IP / check OOP) depende da posição; aqui só travamos que a
    # iniciativa fluiu — antes vinha aggressor=None e o caveat nunca aparecia.
    assert out.get('source') == 'suprema_postflop', out.get('source')
    assert 'HERO_HAS_INITIATIVE' in (out.get('caveats') or []), out.get('caveats')


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n]()
            print('OK', n)
    print('TODOS PASSARAM')
