"""ESQUEMA DE CLASSES do detector YOLO (F0).

Fonte única da verdade das classes que a rede detecta. O índice de cada classe é
a POSIÇÃO na lista `CLASSES` (é o `id` que o YOLO/ultralytics usa no dataset.yaml
e nos rótulos .txt). Nunca reordene sem regerar o dataset — um teste trava a
ordem e a contagem.

Dois grupos:
  1) 52 CARTAS — nome = rank+suit no MESMO formato do ppp_cards ('As','Td','2c'),
     pra o vision_state casar direto com decode_cards/encode_card sem tradução.
  2) OBJETOS da mesa — verso de carta, botões de ação, botão do dealer, indicador
     do hero e pilha de fichas.

Os NÚMEROS (stack/pote/aposta) NÃO são classes YOLO: a rede acha a REGIÃO
(chip_stack/bet_chips/pot) e o OCR lê o valor no recorte (F3). Isso evita pedir
à rede o que ela faz mal (dígitos pequenos) e usa cada ferramenta no seu forte.
"""
from __future__ import annotations

# Ordem canônica (estável). Ranks e naipes idênticos ao ppp_cards.
RANKS_ORDER = "23456789TJQKA"          # 13
SUITS_ORDER = "cdhs"                     # clubs, diamonds, hearts, spades — 4

# 52 cartas: 'As','Ah',... geradas deterministicamente (rank externo, naipe interno).
CARD_CLASSES = [r + s for r in RANKS_ORDER for s in SUITS_ORDER]

# Objetos da mesa (não-carta). Ordem fixa; acrescente SEMPRE no fim (preserva ids).
OBJECT_CLASSES = [
    "card_back",        # carta virada p/ baixo (vilão com cartas, sem valor visível)
    "btn_fold",
    "btn_check",
    "btn_call",
    "btn_raise",
    "btn_allin",
    "btn_confirm",      # confirmação de aposta / "tem certeza?"
    "dealer_button",    # o disco "D" (ancora as posições — ver protobuf_state.assign_positions)
    "hero_indicator",   # marcador do assento do hero (quando houver)
    "chip_stack",       # pilha de fichas de um jogador (stack) -> OCR lê o número
    "bet_chips",        # fichas apostadas à frente de um assento -> OCR lê a aposta
    "pot",              # fichas/label do pote central -> OCR lê o pote
]

CLASSES = CARD_CLASSES + OBJECT_CLASSES

# mapas id<->nome
NAME_TO_ID = {name: i for i, name in enumerate(CLASSES)}
ID_TO_NAME = {i: name for i, name in enumerate(CLASSES)}

# conjuntos úteis p/ o adaptador
CARD_IDS = frozenset(NAME_TO_ID[c] for c in CARD_CLASSES)
BUTTON_CLASSES = ("btn_fold", "btn_check", "btn_call", "btn_raise", "btn_allin", "btn_confirm")
BUTTON_IDS = frozenset(NAME_TO_ID[b] for b in BUTTON_CLASSES)
NUMERIC_REGION_CLASSES = ("chip_stack", "bet_chips", "pot")


def is_card(cls_id: int) -> bool:
    return cls_id in CARD_IDS


def is_button(cls_id: int) -> bool:
    return cls_id in BUTTON_IDS


def card_name(cls_id: int) -> str | None:
    """id de classe -> 'As' se for carta; None caso contrário."""
    name = ID_TO_NAME.get(cls_id)
    return name if name in NAME_TO_ID and cls_id in CARD_IDS else None


def num_classes() -> int:
    return len(CLASSES)
