"""Testes do binding crop->table_ref por nameplate (multi-table sem depender de carta hero)."""
import table_binding as tb
from ppp_cards import decode_cards


def _entry(names, hero_cards=None, hero_seat=0):
    players = []
    for i, n in enumerate(names):
        p = {"seat": i, "uid": 1000 + i, "name": n, "cards": []}
        if i == hero_seat and hero_cards:
            p["cards"] = hero_cards
        players.append(p)
    return {"players": players}


def _crop(raws):
    return {"seat%d" % i: {"raw": r} for i, r in enumerate(raws)}


ESTADO = {
    "111": _entry(["safeguard15", "Top quality", "Ragnar", "perkks"]),
    "222": _entry(["LPFofao", "Sparktohuga", "NiceBroO", "Broca1000"]),
}


def test_bind_mesa_A_por_nameplates():
    crop = _crop(["safeguard15 69,4BB", "Top quality 45BB", "perkks 12BB"])
    assert tb.bind_crop_to_ref(crop, ESTADO) == "111"


def test_bind_mesa_B_por_nameplates():
    crop = _crop(["LPFofao 30BB", "Broca1000 48BB", "NiceBroO 71BB"])
    assert tb.bind_crop_to_ref(crop, ESTADO) == "222"


def test_um_casamento_so_nao_amarra():
    # só 1 nameplate casa -> abaixo do min_matches (2) -> None (não arrisca)
    crop = _crop(["safeguard15 69BB", "jogador_desconhecido 10BB"])
    assert tb.bind_crop_to_ref(crop, ESTADO) is None


def test_empate_e_ambiguo_none():
    # nameplates que casam igual nas duas mesas -> ambíguo -> None
    est = {"A": _entry(["joao", "maria"]), "B": _entry(["joao", "maria"])}
    crop = _crop(["joao 10BB", "maria 20BB"])
    assert tb.bind_crop_to_ref(crop, est) is None


def test_sem_nameplate_none():
    assert tb.bind_crop_to_ref({}, ESTADO) is None
    assert tb.bind_crop_to_ref(_crop(["ab", "x"]), ESTADO) is None   # <3 chars


def test_ref_hero_cards_do_protobuf():
    cards = [3 * 256 + 14, 1 * 256 + 13]     # Ah, Kd (mapa confirmado idx3=h idx1=d)
    entry = _entry(["safeguard15", "Top quality"], hero_cards=cards, hero_seat=0)
    assert tb.ref_hero_cards(entry) == decode_cards(cards)
