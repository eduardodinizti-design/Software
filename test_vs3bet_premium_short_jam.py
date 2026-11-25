"""REGRESSÃO (Eduardo 24/11, "atacar os curtos primeiro"): premium CURTO (<20bb) que
ABRIU e enfrenta um 3bet NÃO-all-in deve 4bet-JAMAR (commit), nunca cold-callar passivo
(o leak medido: 496 cold-calls). Invariantes:
  1. premium curto vs 3bet NÃO-shove (fallback val=False) -> all_in (jam), nunca call;
  2. premium curto vs 3bet-SHOVE de verdade (vilão all-in) -> call/fold (call-off), não jam;
  3. premium DEEP (>=20) com nó vs_3bet VALIDADO -> inalterado (a range manda, pode ser call);
  4. o guard é só p/ premium: não carimba o jam-caveat em não-premium.
Pula se os packs reais não existem (lab sem ranges)."""
import os
import sys
import pytest

sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import auditar_cobertura_preflop as aud
from preflop_advisor import PreflopAdvisor

VAL = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'
_PACKS = [p for p in (VAL, DEEP) if os.path.exists(p)]
pytestmark = pytest.mark.skipif(not _PACKS, reason="packs de range reais ausentes (lab)")

JAM_CAVEAT = 'PREMIUM_SHORT_4BET_JAM_VS_3BET'
PREMIUM = {'AA': ['Ac', 'Ad'], 'KK': ['Kc', 'Kd'], 'QQ': ['Qc', 'Qd'],
           'TT': ['Tc', 'Td'], 'AKs': ['As', 'Ks'], 'AKo': ['Ad', 'Kc']}


def _adv():
    return PreflopAdvisor.from_files(*_PACKS)


def _shove_state(hero_pos, stk):
    """3bet-SHOVE real: vilão 3beta p/ ~o stack do hero (all-in)."""
    st = aud._table(hero_pos, stk, 'iguais', [(hero_pos, 2.0), ('BTN', float(stk))])
    st['pot'] = {'pot_bb': 2.0 + stk + 1.5}
    st['to_call'] = {'to_call_bb': float(stk) - 2.0}
    return st


@pytest.mark.parametrize("mode,stage", [('chip_ev', 'mid'), ('icm', 'bubble'),
                                        ('icm', 'ft'), ('pko', 'mid'), ('pko_icm', 'bubble')])
@pytest.mark.parametrize("stk", [10, 12, 15])
@pytest.mark.parametrize("hand", list(PREMIUM))
def test_premium_curto_vs_3bet_naoshove_jama(mode, stage, stk, hand):
    adv = _adv()
    st = aud.st_vs_3bet('CO', 'BTN', stk)      # BTN 3beta p/ 6bb (NÃO all-in)
    r = adv.advise_from_reading(st, PREMIUM[hand], mode=mode, stage=stage)
    assert r.get('recommended') == 'all_in', (
        "%s CO vs BTN-3bet %dbb %s/%s deveria 4bet-JAMAR, veio %s (spot=%s caveats=%s)"
        % (hand, stk, mode, stage, r.get('recommended'), r.get('spot'), r.get('caveats')))


@pytest.mark.parametrize("hand", list(PREMIUM))
def test_premium_curto_vs_3bet_SHOVE_real_nao_forca_jam(hand):
    """Vilão JÁ all-in: não dá p/ raisar -> call-off (call/fold), nunca o 4bet-jam sintético."""
    adv = _adv()
    st = _shove_state('CO', 12)
    r = adv.advise_from_reading(st, PREMIUM[hand], mode='chip_ev', stage='mid')
    assert r.get('recommended') in ('call', 'fold'), (
        "%s vs 3bet-SHOVE real deveria ser call-off, veio %s" % (hand, r.get('recommended')))
    assert JAM_CAVEAT not in (r.get('caveats') or []), (
        "%s vs shove real NÃO pode carregar o jam-caveat (não dá p/ 4betar um all-in)" % hand)


@pytest.mark.parametrize("mode,stage", [('chip_ev', 'mid'), ('icm', 'bubble')])
def test_premium_deep_vs_3bet_node_validado_inalterado(mode, stage):
    """>=20bb com nó vs_3bet VALIDADO: a range manda (pode ser call). O guard NÃO atua
    (é só <20bb) -> o jam-caveat sintético nunca aparece sobre um nó validado."""
    adv = _adv()
    st = aud.st_vs_3bet('CO', 'BTN', 25)
    r = adv.advise_from_reading(st, PREMIUM['AA'], mode=mode, stage=stage)
    assert JAM_CAVEAT not in (r.get('caveats') or []), (
        "deep AA não pode receber o 4bet-jam sintético (guard é só curto); veio %s" % r.get('caveats'))


@pytest.mark.parametrize("hand", [['As', 'Js'], ['Kd', 'Qs'], ['9c', '9d']])
def test_guard_so_premium_nao_carimba_naopremium(hand):
    """O jam-caveat do guard é EXCLUSIVO de premium (_hand_tier=='premium')."""
    adv = _adv()
    st = aud.st_vs_3bet('CO', 'BTN', 12)
    r = adv.advise_from_reading(st, hand, mode='chip_ev', stage='mid')
    assert JAM_CAVEAT not in (r.get('caveats') or []), (
        "%s (não-premium) não pode receber o 4bet-jam de premium" % hand)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
