"""STACK EFETIVO em blind war / steal (Eduardo 24/11): shove de stack grande vs um shortie só RISCA
o efetivo (excedente volta) -> vs um BB de ~6bb a linha é OPEN-SHOVE (range de push do bucket
efetivo), NÃO min-raise. Deep vs deep = raise normal. Hero curto = lógica de shove-zone por stack
do hero (sem duplicar)."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from assistir_suprema import load_advisor

_ADV = load_advisor()


def _st(hero_stack, bb_stack):
    return dict(positions={'hero': 'SB', 'v': 'BB'},
                seats={'hero': {'stack_bb': hero_stack, 'occupied': True},
                       'v': {'stack_bb': bb_stack, 'occupied': True}},
                bets=[{'seat': 'v', 'bet_bb': 1.0}], to_call={'to_call_bb': 0.5},
                pot={'pot_bb': 1.5}, phase='mid', street='PREFLOP', board=[])


def _advise(hero_stack, bb_stack, cards):
    return _ADV.advise_from_reading(_st(hero_stack, bb_stack), cards, mode='chip_ev', stage='mid')


def test_blind_war_vs_bb_curto_shova():
    # hero FUNDO (25bb) vs BB CURTO (6bb): efetivo 6 -> open-shove (J4o/K2o jamam)
    for cards in (['Js', '4d'], ['Kd', '2c']):
        r = _advise(25, 6, cards)
        assert r.get('recommended') == 'all_in', (cards, r.get('recommended'))
        assert 'OPEN_SHOVE_STACK_EFETIVO_vs_SHORTIE' in r.get('caveats', [])
        assert r.get('effective_stack_bb') == 6


def test_deep_vs_deep_abre_normal():
    # hero 25 vs BB 25: efetivo = hero -> SEM reroute (raise normal, não shove de lixo)
    r = _advise(25, 25, ['Js', '4d'])
    assert r.get('recommended') == 'raise'
    assert 'OPEN_SHOVE_STACK_EFETIVO_vs_SHORTIE' not in r.get('caveats', [])


def test_hero_curto_usa_logica_existente():
    # hero 6 vs BB 25: efetivo == hero (6) -> NÃO entra no reroute (evita duplicar);
    # a lógica de shove-zone por stack do hero decide (J4o jama no blind war curto).
    r = _advise(6, 25, ['Js', '4d'])
    assert r.get('recommended') == 'all_in'
    assert 'OPEN_SHOVE_STACK_EFETIVO_vs_SHORTIE' not in r.get('caveats', [])


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n]()
            print('OK', n)
    print('TODOS PASSARAM')
