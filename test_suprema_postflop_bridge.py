"""PONTE PÓS-FLOP da Suprema (religada 23/11): board>=3 cartas roteia para advise_postflop, não para
a lógica PRÉ-FLOP. Regressão da mão real de QQ (H2N #61) que supervalorizava o underpair. Prova:
(a) QQ em K-alto vs all-in -> FOLD (não call-off); (b) QQ no flop pode apostar -> CHECK (não c-beta);
(c) pré-flop (board vazio) segue no advise_from_reading; (d) pós-flop vem SHADOW (validated=False)."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from suprema_state import advise_from_suprema


class _FakeTable:
    def __init__(self, state, hero):
        self._s = (state, hero)

    def to_table_state(self):
        return self._s


def _pf(board, to_call, pot, stack=30.0):
    return dict(positions={'hero': 'SB'}, seats={'hero': {'stack_bb': stack}},
                board=board, street='flop',
                to_call={'to_call_bb': to_call}, pot={'pot_bb': pot})


def test_qq_underpair_vs_allin_folda():
    # o erro da #61: QQ em [Th 8s Kc] (underpair ao K) enfrentando all-in -> FOLD, nunca call-off
    t = _FakeTable(_pf(['Th', '8s', 'Kc'], 17.0, 74.0), ['Qs', 'Qd'])
    adv = advise_from_suprema(t, None, mode='chip_ev', stage='mid')
    assert adv['source'] == 'suprema_postflop'
    assert adv['recommended'] == 'fold'
    assert adv.get('made') == 'underpair'


def test_qq_underpair_cbet_node_checa():
    # QQ em K-alto, pode apostar (to_call=0) -> CHECK (não c-beta o underpair pra encrenca)
    t = _FakeTable(_pf(['Th', '8s', 'Kc'], 0.0, 40.0), ['Qs', 'Qd'])
    adv = advise_from_suprema(t, None, mode='chip_ev', stage='mid')
    assert adv['source'] == 'suprema_postflop'
    assert adv['recommended'] == 'check'


def test_posflop_eh_shadow_validated_false():
    t = _FakeTable(_pf(['Th', '8s', 'Kc'], 0.0, 40.0), ['Qs', 'Qd'])
    adv = advise_from_suprema(t, None, mode='chip_ev', stage='mid')
    assert adv.get('validated') is False


def test_preflop_board_vazio_vai_pro_preflop():
    # board vazio NÃO toca o motor pós-flop: continua no advise_from_reading
    seen = {}

    class _Adv:
        def advise_from_reading(self, state, hero, **kw):
            seen['called'] = True
            return dict(status='ADVICE', recommended='raise', source='preflop')

    t = _FakeTable(dict(positions={'hero': 'BTN'}, seats={'hero': {'stack_bb': 40.0}},
                        board=[], to_call={'to_call_bb': 1.0}, pot={'pot_bb': 2.5}), ['As', 'Ks'])
    adv = advise_from_suprema(t, _Adv(), mode='chip_ev', stage='mid')
    assert seen.get('called') is True and adv['source'] == 'preflop'


def test_overpair_nao_eh_tratado_como_underpair():
    # sanidade: AA em board baixo (overpair) NÃO deve foldar a um all-in como o underpair
    t = _FakeTable(_pf(['9h', '7d', '2c'], 17.0, 74.0), ['As', 'Ad'])
    adv = advise_from_suprema(t, None, mode='chip_ev', stage='mid')
    assert adv['source'] == 'suprema_postflop'
    assert adv.get('made') == 'overpair' and adv['recommended'] != 'fold'


if __name__ == "__main__":
    for name in list(globals()):
        if name.startswith("test_"):
            globals()[name]()
            print("OK", name)
    print("TODOS PASSARAM")
