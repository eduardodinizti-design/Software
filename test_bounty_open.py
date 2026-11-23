"""Alargar o OPEN pra caçar bounty (bounty_open): bounded (só promove mão que o GTO abre misto),
só em spot de open, só com alvo curto bountiado coberto."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import bounty_open as BO


def _adv(rec='fold', raise_freq=0.15):
    return {'status': 'ADVICE', 'recommended': rec, 'hand': 'K9s',
            'mix': [{'action': 'raise', 'frequency': raise_freq},
                    {'action': 'fold', 'frequency': 1 - raise_freq}]}


def _state(hero=80, vill=6, bounty=40, board=None, tocall=0.5):
    return dict(board=board or [], to_call={'to_call_bb': tocall},
                seats={'hero': {'stack_bb': hero}, 'seat3': {'stack_bb': vill}},
                bounties={'seat3': bounty} if bounty else {})


def test_incentivo_vilao_curto_coberto_bountiado():
    assert BO.has_hunt_incentive(_state(80, 6, 40)) is True


def test_sem_incentivo_vilao_cobre_hero():
    assert BO.has_hunt_incentive(_state(hero=5, vill=80, bounty=40)) is False


def test_sem_incentivo_sem_bounty_ou_nao_curto():
    assert BO.has_hunt_incentive(_state(80, 6, 0)) is False       # sem bounty
    assert BO.has_hunt_incentive(_state(80, 50, 40)) is False      # não curto (50bb)


def test_widen_promove_fold_para_raise():
    out = BO.widen_open(_adv('fold', 0.15), _state())
    assert out['recommended'] == 'raise' and 'BOUNTY_OPEN_WIDEN' in out.get('caveats', [])


def test_widen_nao_force_fora_do_range():
    out = BO.widen_open(_adv('fold', 0.0), _state())              # GTO nunca abre -> não força
    assert out['recommended'] == 'fold'


def test_widen_so_em_spot_de_open():
    assert BO.widen_open(_adv('fold'), _state(board=['8d', '3c', '9h']))['recommended'] == 'fold'  # pós-flop
    assert BO.widen_open(_adv('fold'), _state(tocall=4.0))['recommended'] == 'fold'                 # enfrenta raise


def test_widen_sem_incentivo_nao_mexe():
    assert BO.widen_open(_adv('fold'), _state(bounty=0))['recommended'] == 'fold'


def test_widen_nao_mexe_quando_nao_e_fold():
    assert BO.widen_open(_adv('call'), _state())['recommended'] == 'call'


if __name__ == "__main__":
    for name in list(globals()):
        if name.startswith("test_"):
            globals()[name]()
            print("OK", name)
    print("TODOS PASSARAM")
