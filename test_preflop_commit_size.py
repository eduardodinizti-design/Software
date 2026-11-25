"""CEGUEIRA DE SIZE (bug 24/11, ao vivo): o Henrique cold-callou 30.71bb com JTo no SB como se
fosse um open de 2bb — o engine não olhava o TAMANHO da aposta. Fix: uma aposta que exige pagar
>= SHOVE_COMMIT_FRACTION do stack vira facing-shove (call-off por equity), não flat de range de
open. Resultado: lixo (JTo) FOLDA, premium (AA) paga o call-off, open normal (2.5bb) intacto."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import auditar_cobertura_preflop as aud
from preflop_advisor import PreflopAdvisor, infer_live_spot, _opener_is_shove

VAL = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'
_adv = PreflopAdvisor.from_files(VAL, DEEP)


def _state(bet, hero_stk, opener_behind):
    st = aud._table('SB', hero_stk, 'iguais', [('UTG', bet)])
    st['seats']['UTG']['stack_bb'] = opener_behind
    st['seats']['hero']['stack_bb'] = hero_stk
    return st


def test_jto_nao_cold_calla_aposta_gigante():
    # o caso REAL do log (17:25:09): JTo SB, aposta 30.71bb, hero 40bb -> FOLD (não flat 77% do stack)
    st = _state(30.71, 40, 10)
    assert _opener_is_shove(st, 'UTG', 30.71) is True
    assert infer_live_spot(st)['spot'] == 'vs_open_shove'
    r = _adv.advise_from_reading(st, ['Js', 'Td'], mode='chip_ev', stage='mid')
    assert r['recommended'] == 'fold', r['recommended']


def test_premium_paga_call_off_a_aposta_gigante():
    # mesma aposta, AA -> CALL (call-off por equity), não fold. Distingue por FORÇA, não por size cego.
    st = _state(30.71, 40, 10)
    r = _adv.advise_from_reading(st, ['Ac', 'Ad'], mode='chip_ev', stage='mid')
    assert r['recommended'] == 'call', r['recommended']


def test_open_normal_nao_vira_shove():
    # open de 2.5bb NUNCA é facing-shove (não pode quebrar o flat/decisão normal de vs_open)
    for hero_stk in (20, 30, 40, 100):
        st = _state(2.5, hero_stk, hero_stk - 2.5)
        assert _opener_is_shove(st, 'UTG', 2.5) is False
        assert infer_live_spot(st)['spot'] == 'vs_open'


def test_meia_stack_eh_commit():
    # pagar >= 50% do stack = commit -> facing-shove (ex.: aposta 20bb, hero 40bb)
    st = _state(20.0, 40, 20)
    assert _opener_is_shove(st, 'UTG', 20.0) is True


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n]()
            print('OK', n)
    print('TODOS PASSARAM')
