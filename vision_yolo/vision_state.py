"""ADAPTADOR de percepção por VISÃO: detecções YOLO -> table_state (F0 = interface).

Produz o MESMO `table_state` que `protobuf_state.build_table_state` entrega ao
cérebro (mesmas chaves: positions/seats/bets/phase/board/street/to_call/pot),
só que a FONTE é screenshot+YOLO, não a memória do jogo. Assim o cérebro
(cobertura/Nash/ICM/pós-flop) fica INTOCADO — troca-se só o adaptador.

O que o F0 já resolve de verdade (testável offline, sem modelo):
  • modelo de Detection (caixa + classe + confiança) e utilidades;
  • CLUSTERING ESPACIAL multi-mesa (o grande motivo pró-YOLO): numa janela com N
    mesas tiladas, agrupa as detecções por REGIÃO (cada tile = uma mesa) — resolve
    o cruzamento de mesas que o protobuf tinha (ver nvt-multitable-tiled-bug);
  • separação HERO vs BOARD por geometria (hero = cartas FACE-UP embaixo-centro —
    regra de domínio do VisualPilot);
  • ações disponíveis a partir dos botões detectados;
  • a MONTAGEM do table_state no contrato certo, com POSIÇÕES e NÚMEROS (stack/
    pote/aposta) como dependências INJETÁVEIS (ficam pro F3/F4), sem chutar.

Nada aqui injeta no jogo nem clica. Percepção pura.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Callable

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)          # _repo_software (onde moram ppp_cards/protobuf_state)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from . import classes as C

Box = tuple[float, float, float, float]   # (x1, y1, x2, y2) em pixels


# ---------------------------------------------------------------------------
# Modelo de detecção
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Detection:
    cls_id: int
    conf: float
    box: Box

    @property
    def name(self) -> str:
        return C.ID_TO_NAME.get(self.cls_id, "?")

    @property
    def cx(self) -> float:
        return (self.box[0] + self.box[2]) / 2.0

    @property
    def cy(self) -> float:
        return (self.box[1] + self.box[3]) / 2.0

    @property
    def is_card(self) -> bool:
        return C.is_card(self.cls_id)

    @property
    def is_button(self) -> bool:
        return C.is_button(self.cls_id)


def _center_in(box: Box, region: Box) -> bool:
    cx = (box[0] + box[2]) / 2.0
    cy = (box[1] + box[3]) / 2.0
    return region[0] <= cx <= region[2] and region[1] <= cy <= region[3]


# ---------------------------------------------------------------------------
# Clustering espacial multi-mesa
# ---------------------------------------------------------------------------
def cluster_by_region(dets: list[Detection], regions: list[Box]) -> list[list[Detection]]:
    """Caso TILES CONHECIDOS (o normal: temos os retângulos das janelas/tiles).
    Cada detecção vai p/ a região que contém o SEU CENTRO; fora de todas = descartada.
    Devolve uma lista de mesas, uma por região (mesma ordem de `regions`)."""
    buckets: list[list[Detection]] = [[] for _ in regions]
    for d in dets:
        for i, reg in enumerate(regions):
            if _center_in(d.box, reg):
                buckets[i].append(d)
                break
    return buckets


def cluster_by_proximity(dets: list[Detection], gap: float) -> list[list[Detection]]:
    """Caso SEM tiles conhecidos: agrupa por vizinhança (single-linkage) — duas
    detecções no mesmo grupo se seus centros estão a <= `gap` em X e Y. Fallback
    simples e determinístico (une-find); prefira cluster_by_region quando possível."""
    n = len(dets)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if abs(dets[i].cx - dets[j].cx) <= gap and abs(dets[i].cy - dets[j].cy) <= gap:
                union(i, j)
    groups: dict[int, list[Detection]] = {}
    for i, d in enumerate(dets):
        groups.setdefault(find(i), []).append(d)
    # ordena por posição (cima->baixo, esq->dir) p/ estabilidade
    out = list(groups.values())
    out.sort(key=lambda g: (min(d.cy for d in g), min(d.cx for d in g)))
    return out


# ---------------------------------------------------------------------------
# Leitura de uma mesa (dentro do seu tile)
# ---------------------------------------------------------------------------
def split_hero_board(table_dets: list[Detection], table_box: Box) -> tuple[list[str], list[str]]:
    """Separa CARTAS do hero (face-up, embaixo-centro) das do BOARD (meio).

    Regra de domínio (VisualPilot): o hero fica no bottom-center e suas 2 cartas
    estão FACE-UP (as únicas decodificáveis dele). `card_back` nunca entra —
    é vilão virado. Board = cartas face-up na faixa central (não-hero).
    """
    x1, y1, x2, y2 = table_box
    h = max(1.0, y2 - y1)
    w = max(1.0, x2 - x1)
    cx_mid = x1 + w / 2.0
    cards = [d for d in table_dets if d.is_card]           # só face-up (card_back não é carta)
    hero, board = [], []
    for d in cards:
        rely = (d.cy - y1) / h
        relx_off = abs(d.cx - cx_mid) / w                  # 0 = centro
        if rely >= 0.62 and relx_off <= 0.33:              # faixa de baixo, perto do centro
            hero.append(d)
        else:
            board.append(d)
    hero.sort(key=lambda d: d.cx)
    board.sort(key=lambda d: d.cx)
    return [d.name for d in hero][:2], [d.name for d in board][:5]


def available_actions(table_dets: list[Detection]) -> list[str]:
    """Ações ofertadas na tela AGORA, a partir dos botões detectados ('fold','call'...)."""
    out = []
    for d in table_dets:
        if d.is_button:
            out.append(d.name[len("btn_"):])
    # ordem estável e sem repetição
    order = ["fold", "check", "call", "raise", "allin", "confirm"]
    return [a for a in order if a in set(out)]


def street_from_board(board: list[str]) -> str:
    n = len(board)
    return "RIVER" if n >= 5 else "TURN" if n == 4 else "FLOP" if n == 3 else "PREFLOP"


# dependências injetáveis (F3/F4 preenchem; F0 usa stubs que NÃO chutam)
PositionResolver = Callable[[list[Detection], Box], dict]   # -> {seat_key: pos, 'hero': pos}
NumberReader = Callable[[Box], float | None]                 # crop -> valor em fichas


def _no_positions(table_dets, table_box) -> dict:
    return {}


def _no_number(box) -> float | None:
    return None


@dataclass
class VisionReadout:
    """Resultado da leitura de UMA mesa pela visão."""
    table_state: dict | None
    hero_cards: list[str]
    ready: bool
    missing: list[str] = field(default_factory=list)
    reason: str = ""


def build_table_state(
    table_dets: list[Detection],
    table_box: Box,
    resolve_positions: PositionResolver = _no_positions,
    read_number: NumberReader = _no_number,
    bb_chips: float | None = None,
) -> VisionReadout:
    """Monta o table_state (contrato de protobuf_state) a partir das detecções de
    UMA mesa. F0: estrutura + o que a visão já dá (cartas/board/street/ações);
    posições e números vêm dos resolvers injetados (F3/F4). Marca `ready`/`missing`
    com honestidade — NÃO inventa posição nem número (mesma disciplina do protobuf).
    """
    hero_cards, board = split_hero_board(table_dets, table_box)
    if len(hero_cards) != 2:
        return VisionReadout(None, hero_cards, ready=False, reason="HERO_CARDS_UNKNOWN")

    street = street_from_board(board)
    actions = available_actions(table_dets)
    positions = resolve_positions(table_dets, table_box) or {}

    missing: list[str] = []
    if "hero" not in positions:
        missing.append("positions")

    # pilhas e apostas: a visão acha a REGIÃO; o número vem do OCR (F3). Monta a
    # estrutura e deixa stack_bb/bet_bb = None quando não há leitor (sem chutar).
    seats: dict[str, dict] = {}
    bets: list[dict] = []
    stacks = [d for d in table_dets if d.name == "chip_stack"]
    betchips = [d for d in table_dets if d.name == "bet_chips"]
    if stacks and read_number is _no_number:
        missing.append("numbers")

    def _to_bb(v):
        if v is None or not bb_chips:
            return None
        return round(float(v) / bb_chips, 2)

    # hero sempre existe como assento (temos as cartas dele)
    seats["hero"] = dict(stack_bb=None, occupied=True, source="vision")

    pot_region = next((d for d in table_dets if d.name == "pot"), None)
    pot_bb = _to_bb(read_number(pot_region.box)) if pot_region else None

    state = dict(
        positions=positions,
        seats=seats,
        bets=bets,
        phase="mid",
        source="vision",
        scope=("POSTFLOP_VISION" if len(board) >= 3 else "PREFLOP_VISION"),
        board=board,
        street=street,
        to_call={"to_call_bb": None},     # F3: OCR do botão call / maior aposta - aposta do hero
        pot={"pot_bb": pot_bb},
        actions=actions,
    )
    ready = not missing
    return VisionReadout(state, hero_cards, ready=ready, missing=missing,
                         reason="" if ready else "PARCIAL:" + ",".join(missing))


def read_window(
    dets: list[Detection],
    regions: list[Box] | None = None,
    proximity_gap: float = 120.0,
    **kw,
) -> list[VisionReadout]:
    """Lê uma JANELA inteira (pode ter N mesas tiladas): clusteriza e lê cada mesa.
    `regions` = retângulos dos tiles quando conhecidos (preferível); senão agrupa
    por proximidade. Devolve um VisionReadout por mesa encontrada."""
    if regions:
        tables = cluster_by_region(dets, regions)
        boxes = regions
    else:
        tables = cluster_by_proximity(dets, proximity_gap)
        boxes = []
        for g in tables:
            boxes.append((min(d.box[0] for d in g), min(d.box[1] for d in g),
                          max(d.box[2] for d in g), max(d.box[3] for d in g)))
    out = []
    for tdets, box in zip(tables, boxes):
        if not tdets:
            continue
        out.append(build_table_state(tdets, box, **kw))
    return out
