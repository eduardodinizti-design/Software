"""Esquema de CLASSES do detector YOLO de mesa de poker (visão). Define o que o modelo
detecta; `vision_state` traduz as detecções no `table_state` genérico do cérebro.

Decisão 20/11 (ver memória nvt-visao-yolo-decisao): percepção padrão = VISÃO (crash-free,
universal nos 3 sites, multi-mesa por clustering), Frida = upgrade opcional / professor da
auto-rotulagem do dataset."""
from __future__ import annotations

# --- CARTAS: 52 classes (rank+suit) + verso (face-down) ---
RANKS = '23456789TJQKA'
SUITS = 'dchs'                       # bijeção; rótulo exato do naipe é indiferente p/ o cérebro
CARD_CLASSES = [r + s for r in RANKS for s in SUITS]   # 'Ad','Kc',... (52)
CARD_BACK = 'card_back'

# --- BOTÕES DE AÇÃO -> ação do cérebro ---
BUTTON_TO_ACTION = {
    'btn_fold': 'fold',
    'btn_check': 'check',
    'btn_call': 'call',
    'btn_bet': 'bet',
    'btn_raise': 'raise',
    'btn_allin': 'all_in',
    'btn_confirm': 'confirm',         # confirmar aumento (não é "ação legal", é passo de size)
}

# --- PRESETS DE SIZE (painel de aumento) ---
PRESET_CLASSES = ['preset_2x', 'preset_3x', 'preset_4x', 'preset_allin', 'slider_plus', 'slider_minus']

# --- ELEMENTOS DA MESA (p/ posições, apostas, OCR de números) ---
TABLE_ELEMENTS = [
    'dealer_button',                  # botão do dealer -> ancora as posições
    'hero_active',                    # indicador de que é a vez do herói (anel/timer)
    'seat_avatar',                    # assento ocupado -> localiza stack/nome p/ OCR
    'seat_stack',                     # caixa do stack (OCR do valor)
    'chip_bet',                       # fichas apostadas por assento (OCR do valor)
    'pot',                            # caixa do pote (OCR)
]

ALL_CLASSES = (CARD_CLASSES + [CARD_BACK] + list(BUTTON_TO_ACTION)
               + PRESET_CLASSES + TABLE_ELEMENTS)


def is_card(cls: str) -> bool:
    return cls in CARD_CLASSES


def class_count() -> int:
    return len(ALL_CLASSES)
