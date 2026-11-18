"""PONTE field->decisao AO VIVO: transforma nossa DB de exploit (exploit_db.json,
~389k maos, CHAVEADA POR ID numerico) no formato que o advisor ja consome em
`state['hud']` — para o bot explorar usando NOSSA base, instantaneo, em vez do
HUD lido na tela.

O advisor (table_advisor) exploita assim: `state['hud'] = {seat: entry}` onde
`entry = {'stats': {...8 stats...}, 'confidence': 'high', '_age': 0}`. So usa a
leitura com confidence='high' e _age falsy. Este modulo produz EXATAMENTE isso a
partir de um mapa seat->ID + a DB.

O mapa seat->ID vem do TRACKER (protobuf; o operador so le nick por OCR, e a DB e
por ID). Enquanto o feed vivo nao existe, o operador passa um mapa vazio e nada
muda (seguro). Este modulo e PURO e testavel.
"""
from __future__ import annotations

import json

MIN_HANDS = 30            # nao exploita com amostra pequena (ruido)


def load_exploit_db(path):
    """Carrega o exploit_db.json (dict {id: registro}). {} se faltar/invalido."""
    try:
        with open(path, encoding='utf-8') as f:
            db = json.load(f)
        return db if isinstance(db, dict) else {}
    except Exception:                               # noqa: BLE001
        return {}


def hud_from_seats(seat_to_id, db, *, min_hands=MIN_HANDS):
    """{seat: entry} no formato do advisor, p/ os assentos cujo ID esta na DB com
    amostra suficiente. Assento sem ID / ID fora da DB / amostra pequena = omitido
    (o advisor cai na base, honesto). Stats vem prontos do registro.

    `seat_to_id`: {seat_key: player_id}. `db`: exploit_db carregado."""
    out = {}
    if not seat_to_id or not db:
        return out
    for seat, pid in seat_to_id.items():
        rec = db.get(str(pid)) if pid is not None else None
        if not rec:
            continue
        stats = rec.get('stats')
        if not isinstance(stats, dict) or not stats:
            continue
        if int(rec.get('hands', 0) or 0) < min_hands:
            continue
        out[seat] = {
            'stats': stats,
            'confidence': 'high',       # DB pre-computada = leitura confiavel
            '_age': 0,                  # nao e um refresh falho
            'category': rec.get('category'),
            'tags': rec.get('tags', []),
            'hands': rec.get('hands'),
            '_source': 'field_db',      # proveniencia: nossa DB, nao o HUD da tela
        }
    return out


def read_live_seats(path, table_key=None):
    """Le o mapa seat->ID que o tracker escreve em logs/live_seats.json.
    Formato: {table_key: {seat: id}} (ou {seat: id} plano). Devolve {seat: id} p/
    a mesa pedida, ou {} se faltar. Tolerante a arquivo ausente/meio-escrito."""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except Exception:                               # noqa: BLE001
        return {}
    if not isinstance(data, dict):
        return {}
    if table_key is not None and table_key in data and isinstance(data[table_key], dict):
        return data[table_key]
    # formato plano {seat: id} (uma mesa so)
    if all(not isinstance(v, dict) for v in data.values()):
        return data
    return {}
