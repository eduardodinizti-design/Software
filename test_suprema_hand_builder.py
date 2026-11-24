"""Regressão do SupremaHandBuilder: SIDE POTS. O builder antigo lia só allpots[0] e descartava os
potes laterais, gerando chip_imbalance em all-in multiway desigual (bug ao vivo 23/11, mão #111:
pote principal 249000 + side pot 43000, builder só via 249000 -> saldo -43000). _pot_total soma TODOS."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from suprema_hand_builder import _pot_total


def test_mao_111_side_pot_fecha():
    # exatamente a mão #111: principal 249000 + lateral 43000 = 292000 (antes vinha 249000)
    assert _pot_total([249000, 43000], {}) == 292000


def test_multi_pote_soma_todos_os_potes():
    # dump real 21/11 (4 potes, amounts individuais, não-monotônico = não cumulativo)
    assert _pot_total([39185, 78272, 74973, 53728], {}) == 246158


def test_um_pote_identico_ao_antigo():
    # 1 pote: comportamento inalterado (não regride as mãos simples que já passavam)
    assert _pot_total([249000], {}) == 249000


def test_sem_allpots_cai_no_fallback_por_chips():
    latest_gs = {"a": {"chips": 1000}, "b": {"chips": 500}, "c": {"chips": 0}}
    assert _pot_total([], latest_gs) == 1500
    assert _pot_total(None, latest_gs) == 1500


def test_fallback_tolera_chips_ausente():
    assert _pot_total([], {"a": {}, "b": {"chips": 200}}) == 200


if __name__ == "__main__":
    for name in list(globals()):
        if name.startswith("test_"):
            globals()[name]()
            print("OK", name)
    print("TODOS PASSARAM")
