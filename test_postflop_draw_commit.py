"""NÃO MATAR A MATEMÁTICA (Eduardo 24/11): x/r light com DRAW FORTE (OESD/combo/FD) que toma um
SHOVE — num CAMPO MOLE (vilão sobre-shova light) a equity real supera a nominal -> ATOLA (não folda
com equity). Campo DURO (value-shove) respeita. Overbet gigante folda sempre (pote capa). Draw
FRACO (gutshot) não ganha o bônus. Odds ótimas (shove curto) pagam em qualquer campo."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from postflop_advisor import advise_postflop

BOARD = ['8h', '7s', '2c']       # flop
OESD = ['9d', 'Td']              # projeto de dois lados (7-8-9-T, precisa 6/J = 8 outs)
GUTSHOT = ['Qd', 'Jd']           # projeto fraco (só gutshot)


def _st(pot, to_call, hero_stack=25):
    return dict(positions={'hero': 'BB', 'v': 'BTN'},
                seats={'hero': {'stack_bb': hero_stack, 'occupied': True},
                       'v': {'stack_bb': 0.0, 'occupied': True}},   # vilão all-in (shove)
                bets=[{'seat': 'v', 'bet_bb': to_call}], to_call={'to_call_bb': to_call},
                pot={'pot_bb': pot}, phase='mid')


def _rec(cards, pot, to_call, soft, hero_stack=25):
    return advise_postflop(_st(pot, to_call, hero_stack), cards, BOARD, street='FLOP',
                           aggressor='v', pot_type='single_raised', soft_field=soft).get('recommended')


def test_oesd_atola_shove_medio_campo_mole():
    # pot_odds 0.40: OESD nominal 32% foldaria; campo mole (over-shove) -> ATOLA
    assert _rec(OESD, 30, 20, soft=True) == 'call'


def test_oesd_folda_shove_medio_campo_duro():
    # campo duro (value-shove) -> respeita a aposta, folda o OESD curto de odds
    assert _rec(OESD, 30, 20, soft=False) == 'fold'


def test_oesd_folda_overbet_gigante_ambos():
    # overbet gigante (pot_odds 0.60): nem o campo mole atola (pote capa o bônus)
    assert _rec(OESD, 20, 30, soft=True) == 'fold'
    assert _rec(OESD, 20, 30, soft=False) == 'fold'


def test_oesd_paga_odds_otimas_ambos():
    # shove curto / xr grande + shove curto (odds ótimas) paga em qualquer campo
    assert _rec(OESD, 40, 10, soft=True) == 'call'
    assert _rec(OESD, 40, 10, soft=False) == 'call'


def test_gutshot_nao_atola():
    # draw FRACO não ganha o bônus -> folda mesmo no campo mole (não é spew de qualquer draw)
    assert _rec(GUTSHOT, 30, 20, soft=True) == 'fold'


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n]()
            print('OK', n)
    print('TODOS PASSARAM')
