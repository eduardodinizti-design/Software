"""PADRÃO DE JOGO (Eduardo 23/11): mão ISO-WORTHY (premium/strong) enfrentando LIMPERS NUNCA joga
passivo (limp/call/check) — ou isola (raise), ou shova (curto), ou folda. Trava o gap #1 que
apareceu ao vivo (AQo no SB vs limpers virou limp). Lixo (72o) PODE ser passivo/fold (guard cirúrgico,
não force-aggress). Pula se os packs reais não existem (lab sem ranges)."""
import os
import sys
import pytest

sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from preflop_advisor import PreflopAdvisor
import auditar_cobertura_preflop as aud

VAL = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'
_PACKS = [p for p in (VAL, DEEP) if os.path.exists(p)]
pytestmark = pytest.mark.skipif(not _PACKS, reason="packs de range reais ausentes (lab)")

PASSIVO = ('limp', 'call', 'check')
AQo = ['Ad', 'Qc']
LIXO = ['7c', '2d']


def _adv():
    return PreflopAdvisor.from_files(*_PACKS)


def _rec(adv, hero_pos, stk, cards, limpers, mode):
    st = aud._table(hero_pos, stk, 'iguais', [(lp, 1.0) for lp in limpers])
    r = adv.advise_from_reading(st, cards, mode=mode, stage='mid')
    return (r.get('recommended') if isinstance(r, dict) else None), r


@pytest.mark.parametrize("mode", ['chip_ev', 'icm', 'pko'])
@pytest.mark.parametrize("hero_pos,stk,limpers", [
    ('SB', 40, ['CO']),
    ('SB', 40, ['LJ', 'CO']),
    ('SB', 12, ['CO']),          # curto -> shove, jamais completar
    ('CO', 40, ['LJ']),
])
def test_isoworthy_vs_limpers_nunca_passivo(mode, hero_pos, stk, limpers):
    adv = _adv()
    rec, r = _rec(adv, hero_pos, stk, AQo, limpers, mode)
    assert rec not in PASSIVO, (
        "AQo %s %dbb vs limp%s [%s] jogou PASSIVO (%s) — viola o Padrão. caveats=%s"
        % (hero_pos, stk, limpers, mode, rec, (r.get('caveats') if isinstance(r, dict) else None)))


@pytest.mark.parametrize("mode", ['chip_ev', 'pko'])
def test_curto_isoworthy_vs_limpers_shova(mode):
    # na zona de shove, iso-worthy enfrentando limper = all_in (fold-equity + equity)
    adv = _adv()
    rec, _ = _rec(adv, 'SB', 12, AQo, ['CO'], mode)
    assert rec == 'all_in', "AQo curto vs limper deveria shovar, veio %s" % rec


def test_lixo_vs_limpers_nao_e_forcado_a_agredir():
    # guard é CIRÚRGICO: 72o (fora da range de iso) NÃO vira raise/all_in por causa do guard
    adv = _adv()
    rec, _ = _rec(adv, 'SB', 40, LIXO, ['CO'], 'chip_ev')
    assert rec not in ('raise', 'all_in'), "72o não deveria ser agredido pelo guard, veio %s" % rec


# ---------------------------------------------------------------------------
# REGRESSÃO DO FIX 24/11 (_iso_worthy cego ao regime de shove + spread ICM):
# a sonda media 358 LEAKS de default passivo — mão iso-worthy LIMPANDO no SB/CO vs
# limpers — porque a régua do upgrade (_iso_worthy, strict) só consultava nós
# `open_raise` com spread=None. No regime CURTO (<~15bb) só existe `open_shove`, e
# os nós ICM/PKO-ICM moram em spread 'iguais' -> a régua nunca casava -> False ->
# o upgrade do passivo não disparava. Fix: _iso_worthy soma a freq agressiva de
# open_raise OU open_shove, tenta spread 'iguais'/None, e empresta bucket vizinho.
# Estes testes TRAVAM que a classe inteira (não só AQo) nunca joga passivo.
ISO_WORTHY = {'KQs': ['Ks', 'Qs'], 'AQs': ['As', 'Qs'], 'TT': ['Td', 'Tc'],
              '99': ['9d', '9c'], 'AJs': ['As', 'Js'], 'AJo': ['Ad', 'Jc']}


@pytest.mark.parametrize("mode,stage", [('chip_ev', 'mid'), ('icm', 'bubble'),
                                        ('icm', 'ft'), ('pko', 'mid'), ('pko_icm', 'bubble')])
@pytest.mark.parametrize("stk", [12, 15, 20, 25])
@pytest.mark.parametrize("hlabel", list(ISO_WORTHY))
def test_isoworthy_classe_sb_vs_limpers_nunca_passivo(mode, stage, stk, hlabel):
    """A classe toda (KQs/AQs/TT/99/AJs/AJo) no SB vs limper NUNCA completa passivo —
    isola (deep) ou shova (curto). Era o buraco invisível do auditor (gap #1 real)."""
    adv = _adv()
    st = aud._table('SB', stk, 'iguais', [('CO', 1.0), ('BB', 1.0)])
    r = adv.advise_from_reading(st, ISO_WORTHY[hlabel], mode=mode, stage=stage)
    rec = r.get('recommended') if isinstance(r, dict) else None
    assert rec not in PASSIVO, (
        "%s SB %dbb vs CO-limp %s/%s jogou PASSIVO (%s) — viola o Padrão. caveats=%s"
        % (hlabel, stk, mode, stage, rec, (r.get('caveats') if isinstance(r, dict) else None)))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
