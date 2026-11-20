"""Regressão do BUG de multi-table: o protobuf CRUZAVA mesas — aplicava o estado da
mesa ATIVA (única fresca) a TODO crop, fazendo o AA ser jogado como a mão de outra mesa
([[nvt-multitable-tiled-bug]]). O fix exige CASAMENTO positivo (carta do hero) entre a
mesa fresca e o crop atual em multi-table; single-table fica idêntico.
"""
import json
import os
import time

import operar_mesa as om
import protobuf_state
from ppp_cards import decode_cards

# Duas mãos distintas (ranks diferentes p/ não colidir). Decodificamos com a própria
# decode_cards p/ não depender do SUIT_MAP.
CARDS_A = [3 * 256 + 11, 1 * 256 + 8]    # ~Js 8x  (mesa BINGO)  — naipes 1..4 válidos
CARDS_B = [2 * 256 + 14, 4 * 256 + 14]   # ~Ax Ax  (mesa SMALL PKO = o "AA")
HERO_A = decode_cards(CARDS_A)
HERO_B = decode_cards(CARDS_B)


def _table(room, cards, *, fresh=True):
    return {
        "ts": time.time() if fresh else 0.0,
        "room": room,
        "table": {"dealer": 0, "sbseat": 1, "bbseat": 2, "sb": 100,
                  "minraise": 200, "maxraise": 5000, "board": [], "stage": 0,
                  "tocall": 100, "pot": 150},
        "players": [
            {"seat": 0, "uid": 111, "name": "hero", "stack": 10000, "sit": 0,
             "bet": 0, "act": 0, "hascard": 1, "cards": cards},
            {"seat": 1, "uid": 222, "name": "vil", "stack": 9000, "sit": 0,
             "bet": 50, "act": 0, "hascard": 1, "cards": []},
        ],
    }


def _write(tmp_path, data):
    p = os.path.join(str(tmp_path), "estado_mesa.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return p


def _patch_sel(monkeypatch):
    """advise_from_protobuf devolve qual mesa (hero cards) foi selecionada."""
    monkeypatch.setattr(protobuf_state, "advise_from_protobuf",
                        lambda entry, adv, **kw: {"status": "ADVICE",
                                                  "sel_hero": om._entry_hero_cards(entry)})


def test_entry_hero_cards_le_as_cartas():
    assert om._entry_hero_cards(_table("BINGO", CARDS_A)) == HERO_A


def test_multitable_nao_cruza_o_AA(tmp_path, monkeypatch):
    """SÓ a mesa A (BINGO/JsBx) está fresca; o crop atual é o AA (OCR=HERO_B), 2 mesas.
    DEVE retornar None (OCR reserva), NUNCA o ADVICE da mesa A -> sem cruzamento."""
    _patch_sel(monkeypatch)
    data = {"A": _table("BINGO", CARDS_A, fresh=True),
            "B": _table("SMALL PKO", CARDS_B, fresh=False)}  # B velha
    path = _write(tmp_path, data)
    out = om._protobuf_advice(object(), "chip_ev", "mid", estado_path=path,
                              match_hero=HERO_B, n_crops=2)
    assert out is None


def test_multitable_casa_a_mesa_certa(tmp_path, monkeypatch):
    """Ambas frescas; o crop é o AA (HERO_B) -> seleciona a mesa B, não a A."""
    _patch_sel(monkeypatch)
    data = {"A": _table("BINGO", CARDS_A), "B": _table("SMALL PKO", CARDS_B)}
    path = _write(tmp_path, data)
    out = om._protobuf_advice(object(), "chip_ev", "mid", estado_path=path,
                              match_hero=HERO_B, n_crops=2)
    assert out is not None and out["sel_hero"] == HERO_B


def test_multitable_sem_cartas_casa_por_sala(tmp_path, monkeypatch):
    """Cartas do crop desconhecidas (OCR falhou) -> casa pela SALA."""
    _patch_sel(monkeypatch)
    data = {"A": _table("BINGO", CARDS_A), "B": _table("SMALL PKO", CARDS_B)}
    path = _write(tmp_path, data)
    out = om._protobuf_advice(object(), "chip_ev", "mid", estado_path=path,
                              match_hero=[], match_room="SMALL PKO", n_crops=2)
    assert out is not None and out["sel_hero"] == HERO_B


def test_single_table_mantem_comportamento(tmp_path, monkeypatch):
    """SINGLE-TABLE (n_crops=1, 1 fresca): usa a mesa mesmo sem match (sem regressão)."""
    _patch_sel(monkeypatch)
    data = {"A": _table("BINGO", CARDS_A)}
    path = _write(tmp_path, data)
    out = om._protobuf_advice(object(), "chip_ev", "mid", estado_path=path, n_crops=1)
    assert out is not None and out["sel_hero"] == HERO_A


def test_single_table_duas_frescas_sem_match_abstem(tmp_path, monkeypatch):
    """SINGLE-TABLE com 2 frescas e SEM pista (cartas/sala) = ambíguo -> None."""
    _patch_sel(monkeypatch)
    data = {"A": _table("BINGO", CARDS_A), "B": _table("SMALL PKO", CARDS_B)}
    path = _write(tmp_path, data)
    out = om._protobuf_advice(object(), "chip_ev", "mid", estado_path=path, n_crops=1)
    assert out is None


def test_single_table_com_mesa_morta_casa_por_carta(tmp_path, monkeypatch):
    """SINGLE-TABLE (1 crop) mas com mesa MORTA ainda fresca no estado (len(fresh)=2):
    casa a mesa certa pela carta do hero do crop -> protobuf segue ÚTIL (refino 20/11)."""
    _patch_sel(monkeypatch)
    data = {"VIVA": _table("BINGO", CARDS_A), "MORTA": _table("BINGO", CARDS_B)}
    path = _write(tmp_path, data)
    out = om._protobuf_advice(object(), "chip_ev", "mid", estado_path=path,
                              match_hero=HERO_A, n_crops=1)
    assert out is not None and out["sel_hero"] == HERO_A
