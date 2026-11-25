"""SIT-OUT ponto 2 (Eduardo 24/11): o hero ENFRENTA um open com um BLIND sit-out (dead money que o
opener rouba -> abre mais largo) -> o hero RE-STEALA mais largo (fold->3bet SÓ se o GTO já 3beta a
mão em freq mista). Bounded: não inventa resteal de lixo; sem blind sit-out ou fora do spot, nada muda."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import sitout_steal as S

_MIX_3BET = [{'action': 'three_bet', 'frequency': 0.3}, {'action': 'fold', 'frequency': 0.7}]
_MIX_PURE = [{'action': 'fold', 'frequency': 1.0}]


def _adv(mix):
    return {'status': 'ADVICE', 'recommended': 'fold', 'mix': mix}


def _st(sitout, tocall=2.5):
    return dict(board=[], to_call={'to_call_bb': tocall}, sitout_positions=sitout)


def _rec(mix, sitout, tocall=2.5):
    return S.widen_defense_vs_sitout(_adv(mix), _st(sitout, tocall)).get('recommended')


def test_resteala_vs_blind_sitout_quando_gto_3beta_misto():
    assert _rec(_MIX_3BET, ['BB']) == 'three_bet'
    assert _rec(_MIX_3BET, ['SB']) == 'three_bet'


def test_nao_resteala_lixo_gto_fold_puro():
    assert _rec(_MIX_PURE, ['BB']) == 'fold'


def test_nao_mexe_sem_blind_sitout():
    assert _rec(_MIX_3BET, ['UTG+1']) == 'fold'       # sit-out não-blind = sem dead money extra
    assert _rec(_MIX_3BET, []) == 'fold'


def test_nao_mexe_fora_do_spot_de_open():
    assert _rec(_MIX_3BET, ['BB'], tocall=1.0) == 'fold'   # não enfrenta raise real


def test_bounded_so_toca_fold():
    # se o GTO já manda 3bet/call, não sobrescreve
    a = {'status': 'ADVICE', 'recommended': 'call', 'mix': _MIX_3BET}
    assert S.widen_defense_vs_sitout(a, _st(['BB'])).get('recommended') == 'call'


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n]()
            print('OK', n)
    print('TODOS PASSARAM')
