"""MAPA DE LAYOUT da SUPREMA (frações 0..1 do client) p/ a auto-rotulagem (autolabel) e p/
ancorar posições. Caixas = (cx, cy, w, h).

CONFIANÇA:
  - buttons/presets: EXATOS (calibrados em suprema_click, validados visualmente 20/11).
  - seats: medidos da captura de mesa (raise_c_01, 922x1657) — bons p/ ancorar dealer/posição.
  - hero_card_slots/board_slots: ESTIMADOS (faltou captura com cartas+board nítidos); refinar
    quando tivermos 1 captura de mão viva (ou via Frida na F1-live). Marcado abaixo.

O layout é por FRAÇÃO -> sobrevive a resize/stake. Um cliente novo (PPPoker/X-Poker) ganha o
seu próprio mapa."""
from __future__ import annotations

# --- EXATO: botões da barra de ação (de suprema_click, validado) ---
BUTTONS = {
    'fold':  (0.185, 0.950, 0.30, 0.055),   # "Desistir"
    'check': (0.500, 0.950, 0.30, 0.055),   # "Passar"
    'call':  (0.500, 0.950, 0.30, 0.055),   # "Pagar X BB"
    'raise': (0.815, 0.950, 0.30, 0.055),   # "Aumentar"/"Apostar"
}

# --- EXATO: painel de size do raise (de suprema_click PRESET_LAYOUT, validado) ---
PRESETS = {
    '2X': (0.101, 0.949, 0.14, 0.05), '3X': (0.261, 0.949, 0.14, 0.05),
    '4X': (0.420, 0.949, 0.14, 0.05), 'all_in': (0.583, 0.949, 0.15, 0.05),
    'confirm': (0.816, 0.949, 0.18, 0.05),
    'plus': (0.618, 0.650, 0.14, 0.07), 'minus': (0.618, 0.724, 0.14, 0.07),
}

# --- MEDIDO: centros dos assentos (ancora dealer/posições). hero = bottom-center ---
SEATS = {
    'hero':      (0.50, 0.82),
    'top':       (0.50, 0.13),
    'top_left':  (0.11, 0.24), 'top_right': (0.89, 0.24),
    'mid_left':  (0.11, 0.53), 'mid_right': (0.89, 0.49),
    'low_left':  (0.11, 0.67), 'low_right': (0.89, 0.67),
}

# --- ESTIMADO (REFINAR com captura de mão viva): slots de carta ---
HERO_CARD_SLOTS = [(0.645, 0.805, 0.075, 0.055), (0.725, 0.805, 0.075, 0.055)]
BOARD_SLOTS = [(0.37, 0.40, 0.065, 0.05), (0.45, 0.40, 0.065, 0.05),
               (0.53, 0.40, 0.065, 0.05), (0.61, 0.40, 0.065, 0.05), (0.69, 0.40, 0.065, 0.05)]

# formato que autolabel.to_yolo_labels consome
LAYOUT = {
    'hero_card_slots': HERO_CARD_SLOTS,
    'board_slots': BOARD_SLOTS,
    'buttons': BUTTONS,
}
