"""TRAP pré-flop com premium vs resteal curto (Eduardo 24/11): AA/KK/QQ DEEP vs OPEN com um short de
RESTEAL (~12-25bb) ATRÁS que o hero COBRE -> FLAT (induz o short a shovar fraco; o hero atola). Fora
desse spot exato -> 3bet normal (bounded, não trapa à toa)."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import trap_premium as T

_ADV = {'status': 'ADVICE', 'recommended': 'raise'}


def _st(hero_pos, hero_stack, behind):
    positions = {'hero': hero_pos, 'op': 'UTG'}
    seats = {'hero': {'stack_bb': hero_stack}, 'op': {'stack_bb': 40}}
    for i, (pos, stk) in enumerate(behind.items()):
        positions['b%d' % i] = pos
        seats['b%d' % i] = {'stack_bb': stk}
    return dict(positions=positions, seats=seats, board=[], to_call={'to_call_bb': 2.0})


def _rec(hero_pos, hero_stack, behind, cards):
    return T.trap_flat(dict(_ADV), _st(hero_pos, hero_stack, behind), cards).get('recommended')


def test_trap_aa_vs_resteal_curto_atras():
    assert _rec('BTN', 40, {'SB': 15, 'BB': 40}, ['Ac', 'Ad']) == 'call'


def test_trap_kk_qq():
    assert _rec('BTN', 40, {'SB': 40, 'BB': 18}, ['Kc', 'Kd']) == 'call'
    assert _rec('CO', 50, {'BTN': 20, 'SB': 40, 'BB': 40}, ['Qc', 'Qd']) == 'call'


def test_nao_trapa_sem_short_atras():
    assert _rec('BTN', 40, {'SB': 40, 'BB': 45}, ['Ac', 'Ad']) == 'raise'


def test_nao_trapa_hero_curto():
    # hero não-deep (15bb) -> 3bet-jam normal, não flat
    assert _rec('BTN', 15, {'SB': 15, 'BB': 40}, ['Ac', 'Ad']) == 'raise'


def test_nao_trapa_sem_cobrir_o_short():
    # short atrás com MAIS stack que o hero -> hero não cobre -> não trapa
    assert _rec('BTN', 14, {'SB': 20, 'BB': 40}, ['Ac', 'Ad']) == 'raise'


def test_nao_trapa_mao_nao_premium():
    assert _rec('BTN', 40, {'SB': 15, 'BB': 40}, ['Ac', 'Kd']) == 'raise'
    assert _rec('BTN', 40, {'SB': 15, 'BB': 40}, ['Jc', 'Jd']) == 'raise'   # JJ não é premium p/ trap


def test_nao_trapa_short_na_frente():
    # short à FRENTE do hero (já agiu) não pode ser induzido a shovar -> não trapa
    # opener UTG=short; hero BTN atrás; blinds deep -> sem short ATRÁS
    s = dict(positions={'hero': 'BTN', 'op': 'UTG'}, seats={'hero': {'stack_bb': 40}, 'op': {'stack_bb': 15}},
             board=[], to_call={'to_call_bb': 2.0})
    assert T.trap_flat(dict(_ADV), s, ['Ac', 'Ad']).get('recommended') == 'raise'


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n]()
            print('OK', n)
    print('TODOS PASSARAM')
