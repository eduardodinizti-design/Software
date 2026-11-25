"""Fiação do bounty no conselho: advise_from_suprema com hunt_bounty injeta state['bounties']
(cabeça=base+acumulado por vilão) + bounty_bb no advise_from_reading, só em pko/pko_icm."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from suprema_state import advise_from_suprema


class _FakeTable:
    def __init__(self, state, hero):
        self._r = (state, hero)

    def to_table_state(self):
        return self._r


class _CaptureAdvisor:
    def __init__(self):
        self.state = self.kwargs = None

    def advise_from_reading(self, state, hero, **kwargs):
        self.state, self.kwargs = state, kwargs
        return {"status": "ADVICE", "recommended": "call"}


def _state():
    return dict(bb_chips=2000.0, pot={'pot_bb': 5.0}, to_call={'to_call_bb': 4.0},
                positions={'hero': 'BTN', 'seat3': 'SB'},
                mtt=dict(bounty_base=4.4, avg_stack=100000, players_left=100, players_total=200, rebuys=0),
                seats={'hero': dict(stack_bb=80, bounty_raw=6.6, ko=4),
                       'seat3': dict(stack_bb=4, bounty_raw=6.6, ko=3)})   # vilão curto bountiado


def test_hunt_bounty_injeta_cabeca_no_calloff():
    adv = _CaptureAdvisor()
    advise_from_suprema(_FakeTable(_state(), ['As', 'Ks']), adv, mode='pko', stage='mid',
                        hunt_bounty=True, starting_stack=50000)
    assert 'bounties' in adv.state and adv.state['bounties'].get('seat3'), adv.state.get('bounties')
    assert adv.state['bounties']['seat3'] > 0
    assert isinstance(adv.kwargs.get('bounty_bb'), (int, float)) and adv.kwargs['bounty_bb'] > 0


def test_off_nao_injeta():
    adv = _CaptureAdvisor()
    advise_from_suprema(_FakeTable(_state(), ['As', 'Ks']), adv, mode='pko', stage='mid',
                        hunt_bounty=False, starting_stack=50000)
    assert 'bounties' not in (adv.state or {}) and 'bounty_bb' not in (adv.kwargs or {})


class _FoldOpenAdvisor:
    """Devolve open-fold com RAISE misto (o GTO abre às vezes) -> o widen pode promover."""
    def advise_from_reading(self, state, hero, **kwargs):
        return {'status': 'ADVICE', 'recommended': 'fold', 'hand': 'K9s',
                'mix': [{'action': 'raise', 'frequency': 0.2}, {'action': 'fold', 'frequency': 0.8}]}


def test_open_widen_caca_promove_fold_para_raise():
    st = _state()
    st['board'] = []
    st['to_call'] = {'to_call_bb': 0.5}       # spot de OPEN (enfrenta só os blinds)
    out = advise_from_suprema(_FakeTable(st, ['Ks', '9s']), _FoldOpenAdvisor(), mode='pko',
                              stage='mid', hunt_bounty=True, starting_stack=50000)
    # vilão seat3 curto (4bb) coberto + bounty injetado -> incentivo -> abre
    assert out['recommended'] == 'raise' and 'BOUNTY_OPEN_WIDEN' in out.get('caveats', []), out


def test_chip_ev_nao_injeta():
    adv = _CaptureAdvisor()
    advise_from_suprema(_FakeTable(_state(), ['As', 'Ks']), adv, mode='chip_ev', stage='mid',
                        hunt_bounty=True, starting_stack=50000)
    assert 'bounties' not in (adv.state or {})      # bounty só em pko/pko_icm


if __name__ == "__main__":
    for name in list(globals()):
        if name.startswith("test_"):
            globals()[name]()
            print("OK", name)
    print("TODOS PASSARAM")
