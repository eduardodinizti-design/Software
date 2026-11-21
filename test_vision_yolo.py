"""Testes OFFLINE do F0 da visão/YOLO: esquema de classes + adaptador vision_state.
Puro: sem modelo, sem screenshot, sem Windows."""
from vision_yolo import classes as C
from vision_yolo import vision_state as V
from vision_yolo.vision_state import Detection

import ppp_cards
import protobuf_state


# -------------------- esquema de classes --------------------
def test_52_cartas_unicas_e_formato_ppp_cards():
    assert len(C.CARD_CLASSES) == 52
    assert len(set(C.CARD_CLASSES)) == 52
    # toda carta decodifica no ppp_cards (mesmo formato) e volta igual
    for name in C.CARD_CLASSES:
        code = ppp_cards.encode_card(name)
        assert ppp_cards.decode_card(code) == name


def test_ids_estaveis_e_contiguos():
    assert C.ID_TO_NAME[0] == C.CLASSES[0]
    assert len(C.CLASSES) == C.num_classes()
    assert all(C.NAME_TO_ID[C.ID_TO_NAME[i]] == i for i in range(C.num_classes()))
    # cartas vêm antes dos objetos
    assert C.CLASSES[:52] == C.CARD_CLASSES


def test_helpers_card_button():
    assert C.is_card(C.NAME_TO_ID["As"])
    assert not C.is_card(C.NAME_TO_ID["btn_fold"])
    assert C.is_button(C.NAME_TO_ID["btn_raise"])
    assert C.card_name(C.NAME_TO_ID["Td"]) == "Td"
    assert C.card_name(C.NAME_TO_ID["pot"]) is None


# -------------------- clustering espacial --------------------
def _card(name, cx, cy, s=20):
    cid = C.NAME_TO_ID[name]
    return Detection(cid, 0.9, (cx - s, cy - s, cx + s, cy + s))


def test_cluster_por_regiao_separa_tiles():
    # duas mesas tiladas lado a lado; cada carta cai na sua região
    regions = [(0, 0, 500, 1000), (500, 0, 1000, 1000)]
    dets = [_card("As", 100, 900), _card("Kd", 150, 900),   # mesa esquerda (hero)
            _card("2c", 700, 900), _card("7h", 750, 900)]   # mesa direita (hero)
    tables = V.cluster_by_region(dets, regions)
    assert len(tables) == 2
    assert {d.name for d in tables[0]} == {"As", "Kd"}
    assert {d.name for d in tables[1]} == {"2c", "7h"}


def test_cluster_por_proximidade_fallback():
    dets = [_card("As", 100, 900), _card("Kd", 140, 900),
            _card("2c", 800, 900), _card("7h", 840, 900)]
    groups = V.cluster_by_proximity(dets, gap=120.0)
    assert len(groups) == 2


# -------------------- separação hero/board --------------------
def test_split_hero_board_por_geometria():
    box = (0, 0, 1000, 1000)
    dets = [
        _card("As", 480, 900), _card("Kd", 540, 900),        # hero: baixo-centro
        _card("2c", 400, 450), _card("7h", 500, 450), _card("Qs", 600, 450),  # board: meio
    ]
    hero, board = V.split_hero_board(dets, box)
    assert hero == ["As", "Kd"]
    assert board == ["2c", "7h", "Qs"]


def test_card_back_nunca_vira_carta():
    box = (0, 0, 1000, 1000)
    dets = [_card("As", 480, 900), _card("Kd", 540, 900),
            Detection(C.NAME_TO_ID["card_back"], 0.9, (380, 430, 420, 470))]  # vilão virado
    hero, board = V.split_hero_board(dets, box)
    assert hero == ["As", "Kd"]
    assert board == []          # card_back ignorado


# -------------------- ações / street --------------------
def test_available_actions_ordem_estavel():
    dets = [Detection(C.NAME_TO_ID["btn_raise"], 0.9, (0, 0, 1, 1)),
            Detection(C.NAME_TO_ID["btn_fold"], 0.9, (0, 0, 1, 1)),
            Detection(C.NAME_TO_ID["btn_call"], 0.9, (0, 0, 1, 1))]
    assert V.available_actions(dets) == ["fold", "call", "raise"]


def test_street_do_board():
    assert V.street_from_board([]) == "PREFLOP"
    assert V.street_from_board(["2c", "7h", "Qs"]) == "FLOP"
    assert V.street_from_board(["2c", "7h", "Qs", "Kd"]) == "TURN"
    assert V.street_from_board(["2c", "7h", "Qs", "Kd", "As"]) == "RIVER"


# -------------------- contrato table_state --------------------
def test_table_state_tem_as_mesmas_chaves_do_protobuf():
    box = (0, 0, 1000, 1000)
    dets = [_card("As", 480, 900), _card("Kd", 540, 900)]
    ro = V.build_table_state(dets, box)
    assert ro.table_state is not None
    chaves_protobuf = {"positions", "seats", "bets", "phase", "board", "street", "to_call", "pot"}
    assert chaves_protobuf.issubset(set(ro.table_state))
    # formato de to_call/pot igual ao protobuf
    assert "to_call_bb" in ro.table_state["to_call"]
    assert "pot_bb" in ro.table_state["pot"]


def test_sem_posicao_marca_parcial_nao_chuta():
    box = (0, 0, 1000, 1000)
    dets = [_card("As", 480, 900), _card("Kd", 540, 900)]
    ro = V.build_table_state(dets, box)           # sem resolver de posição (F0)
    assert ro.ready is False
    assert "positions" in ro.missing
    assert ro.table_state["positions"] == {}      # vazio, não inventado


def test_hero_sem_duas_cartas_aborta_igual_protobuf():
    box = (0, 0, 1000, 1000)
    dets = [_card("As", 480, 900)]                # só 1 carta do hero
    ro = V.build_table_state(dets, box)
    assert ro.table_state is None
    assert ro.reason == "HERO_CARDS_UNKNOWN"      # mesma semântica do protobuf_state


def test_resolver_de_posicao_injetado_preenche():
    box = (0, 0, 1000, 1000)
    dets = [_card("As", 480, 900), _card("Kd", 540, 900)]
    ro = V.build_table_state(dets, box, resolve_positions=lambda d, b: {"hero": "BTN"})
    assert ro.ready is True
    assert ro.table_state["positions"]["hero"] == "BTN"


def test_read_window_multi_mesa():
    regions = [(0, 0, 500, 1000), (500, 0, 1000, 1000)]
    dets = [_card("As", 240, 900), _card("Kd", 260, 900),
            _card("2c", 740, 900), _card("7h", 760, 900)]
    outs = V.read_window(dets, regions=regions)
    assert len(outs) == 2
    assert outs[0].hero_cards == ["As", "Kd"]
    assert outs[1].hero_cards == ["2c", "7h"]


def test_protobuf_contract_referencia_existe():
    # garante que a referência de contrato que copiamos ainda existe (trava anti-drift)
    assert hasattr(protobuf_state, "build_table_state")
