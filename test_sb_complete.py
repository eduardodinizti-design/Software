"""SB-complete NUNCA foldar por poucos blinds (Eduardo 25/11, pós-mortem): no SB pagando <=0,75bb
(complete vs BB, odds 5:1+) o hero JAMAIS folda -> abre (se o GTO abre misto) ou completa. Bounded:
fora do SB, com to_call de raise real, pós-flop, ou se o cérebro já não foldava -> nada muda."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import sb_complete as S

_MIX_OPEN = [{'action': 'raise', 'frequency': 0.9}, {'action': 'fold', 'frequency': 0.1}]
_MIX_FOLD = [{'action': 'fold', 'frequency': 1.0}]


def _adv(mix=None, rec='fold'):
    a = {'status': 'ADVICE', 'recommended': rec}
    if mix is not None:
        a['mix'] = mix
    return a


def _st(pos='SB', tocall=0.5, board=None):
    return dict(board=(board or []), positions={'hero': pos}, to_call={'to_call_bb': tocall})


def _r(adv, st):
    return S.never_fold_sb_complete(adv, st)


def test_kqo_sb_complete_abre_quando_gto_abre():
    r = _r(_adv(_MIX_OPEN), _st())
    assert r['recommended'] == 'raise'
    assert r.get('sizing', {}).get('multiplier') == S.OPEN_MULTIPLIER
    assert 'SB_COMPLETE_NEVER_FOLD_CHEAP' in r['caveats']


def test_sem_mix_completa_nunca_folda():
    # no-node (default fold, sem mix) -> COMPLETA por <=0,75bb
    r = _r(_adv(None), _st(tocall=0.75))
    assert r['recommended'] == 'call'
    assert 'SB_COMPLETE_NEVER_FOLD_CHEAP' in r['caveats']


def test_mix_fold_puro_ainda_completa():
    # LEI: por <=0,75bb jamais folda (direção segura); sem ação agressiva no mix -> completa
    r = _r(_adv(_MIX_FOLD), _st())
    assert r['recommended'] == 'call'


def test_nao_mexe_fora_do_sb():
    assert _r(_adv(_MIX_OPEN), _st(pos='BB'))['recommended'] == 'fold'
    assert _r(_adv(_MIX_OPEN), _st(pos='BTN'))['recommended'] == 'fold'


def test_nao_mexe_se_enfrenta_raise_real():
    # to_call >= 1,5bb = raise real vs o SB -> fold legítimo, não é "poucos blinds"
    assert _r(_adv(_MIX_OPEN), _st(tocall=2.5))['recommended'] == 'fold'
    assert _r(_adv(_MIX_OPEN), _st(tocall=1.5))['recommended'] == 'fold'


def test_nao_mexe_posflop():
    assert _r(_adv(_MIX_OPEN), _st(board=['As', 'Kd', '2c']))['recommended'] == 'fold'


def test_nao_mexe_tocall_zero():
    # to_call=0 (já pode checar) não é o spot de complete -> não força
    assert _r(_adv(_MIX_OPEN), _st(tocall=0.0))['recommended'] == 'fold'


def test_bounded_so_toca_fold():
    for rec in ('call', 'raise', 'check', 'all_in'):
        assert _r(_adv(_MIX_OPEN, rec=rec), _st())['recommended'] == rec


def test_ignora_sem_advice():
    a = {'status': 'ABSTAIN', 'reason': 'x'}
    assert S.never_fold_sb_complete(a, _st()) is a


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n]()
            print('OK', n)
    print('TODOS PASSARAM')
