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


def read_live_players(path):
    """Lê live_seats_rich.json {ref:{room,players:[{uid,name,...}]}} e devolve a
    UNIÃO dos players (uid+name) de todas as mesas — o casamento por nick nos
    assentos do operador já isola a mesa certa. [] se faltar."""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return []
    out = []
    if isinstance(data, dict):
        for info in data.values():
            for p in (info or {}).get('players', []) or []:
                if p.get('uid') is not None and p.get('name'):
                    out.append({'uid': p['uid'], 'name': p['name']})
    return out


def _norm(s):
    """Normaliza nick/nameplate p/ casar (minúsculas, só alfanumérico)."""
    return ''.join(ch for ch in (s or '').lower() if ch.isalnum())


def hud_from_table(seats, players, db, *, min_hands=MIN_HANDS):
    """{seat_key: entry} chaveado pelos ASSENTOS DO OPERADOR (state['seats']),
    casando o NICK do emissor (players: [{uid,name}]) com o nameplate lido (raw)
    de cada assento. Evita a geometria _seatId->tela: usa o nick, que é único.

    `seats`: {seat_key: {'raw': '<nameplate OCR>', ...}} do read_table_state.
    `players`: lista do emissor (live_seats_rich), uid+name. `db`: exploit_db."""
    out = {}
    if not seats or not players or not db:
        return out
    cand = []
    for pl in players:
        nick = _norm(pl.get('name'))
        uid = pl.get('uid')
        if len(nick) >= 3 and uid is not None:
            cand.append((nick, str(uid)))
    if not cand:
        return out
    for seat, info in seats.items():
        raw = _norm((info or {}).get('raw'))
        if len(raw) < 3:
            continue
        # casa o nick que é substring do nameplate (nick único na mesa)
        hit = next((uid for nick, uid in cand if nick in raw or raw in nick), None)
        if not hit:
            continue
        rec = db.get(hit)
        if not rec or not isinstance(rec.get('stats'), dict):
            continue
        if int(rec.get('hands', 0) or 0) < min_hands:
            continue
        out[seat] = {'stats': rec['stats'], 'confidence': 'high', '_age': 0,
                     'category': rec.get('category'), 'tags': rec.get('tags', []),
                     'hands': rec.get('hands'), '_source': 'field_db', '_uid': hit}
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
