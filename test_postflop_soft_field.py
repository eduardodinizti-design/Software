"""CAMPO MOLE por STAGE (Eduardo 24/11): no início (play money ruim que sobre-blefa) o
bluff-catch defende mais largo (paga o lixo deles); no FT/bolha (callstation value-heavy)
fica conservador. Gated por `soft_field` (default False = conservador -> testes antigos intactos).
GUARDA anti-spew: MULTIWAY, OVERBET e RIVER-aposta-grande FOLDAM mesmo no campo mole (leak de 50k)."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from postflop_advisor import advise_postflop


def state(pot, to_call, stack=40.0):
    return dict(positions={'hero': 'BTN', 'v': 'BB'},
                seats={'hero': {'stack_bb': stack, 'occupied': True}, 'v': {'stack_bb': stack, 'occupied': True}},
                bets=[], to_call={'to_call_bb': to_call}, pot={'pot_bb': pot}, phase='mid')


SECOND_PAIR = (['9s', 'Qc'], ['Ah', '9h', '3d'])     # 2º par
UNDERPAIR = (['Qs', 'Qd'], ['Th', '8s', 'Kc'])       # QQ underpair ao K


def _rec(hand_board, soft, pot=10.0, to_call=4.0, villains=None):
    h, b = hand_board
    r = advise_postflop(state(pot, to_call), h, b, street='FLOP', soft_field=soft, villains=villains)
    return r.get('recommended')


def test_marginal_campo_mole_defende_barril_normal():
    assert _rec(SECOND_PAIR, soft=True, pot=10, to_call=4) == 'call'      # 0.44, barril normal


def test_marginal_campo_duro_folda():
    assert _rec(SECOND_PAIR, soft=False, pot=10, to_call=4) == 'fold'


def test_underpair_hu_folda_mesmo_no_campo_mole():
    # UNDERPAIR é o bluff-catcher mais fraco (hand do leak de 50k): NÃO entra no soft-defense,
    # folda sem range mesmo no campo mole (protege o call-off). Vale HU, campo mole ou duro.
    assert _rec(UNDERPAIR, soft=True, pot=10, to_call=4) == 'fold'
    assert _rec(UNDERPAIR, soft=False, pot=10, to_call=4) == 'fold'


def test_underpair_multiway_folda_ate_no_campo_mole():
    # leak de 50k: multiway folda SEMPRE, campo mole ou não.
    assert _rec(UNDERPAIR, soft=True, pot=10, to_call=4, villains=2) == 'fold'


def test_underpair_overbet_folda_ate_no_campo_mole():
    # overbet (pot_odds > 0.55) folda SEMPRE (all-in/overbet polarizada), campo mole ou não.
    assert _rec(UNDERPAIR, soft=True, pot=10, to_call=30) == 'fold'       # 0.75


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n]()
            print('OK', n)
    print('TODOS PASSARAM')
