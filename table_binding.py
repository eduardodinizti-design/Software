"""Binding MESA-DA-TELA -> table_ref do protobuf por IDENTIDADE (nameplates dos vilões),
NÃO por carta do hero (que o OCR erra -> HERO_CARDS_UNKNOWN). Resolve o multi-table:
cada crop acha seu dado do protobuf casando os NOMES lidos na tela com os players de cada
mesa do emissor. Uma vez amarrado o ref, as cartas do hero (e todo o estado) vêm do
protobuf — sem depender do OCR das cartas. Ver [[nvt-multitable-tiled-bug]].

PURO: só compara strings; não captura, não clica.
"""
from field_live import _norm

__all__ = ["bind_crop_to_ref", "ref_hero_cards"]


def _crop_nameplates(crop_seats):
    """Nameplates normalizados (>=3 chars) lidos nos assentos do crop (state['seats'])."""
    out = []
    for info in (crop_seats or {}).values():
        raw = _norm((info or {}).get("raw"))
        if len(raw) >= 3:
            out.append(raw)
    return out


def _ref_names(entry):
    out = []
    for p in (entry or {}).get("players", []) or []:
        n = _norm(p.get("name"))
        if len(n) >= 3:
            out.append(n)
    return out


def bind_crop_to_ref(crop_seats, estado, *, min_matches=2):
    """Retorna o `table_ref` (chave de `estado`) cujos NOMES de jogador melhor casam com os
    nameplates lidos no crop, ou None se ninguém atinge `min_matches` OU se houver EMPATE no
    topo (ambíguo -> não arrisca cruzar mesa). Casamento: nick substring do nameplate ou
    vice-versa (robusto a OCR parcial)."""
    raws = _crop_nameplates(crop_seats)
    if not raws:
        return None
    scored = []
    for ref, entry in (estado or {}).items():
        if ref == "?":
            continue
        names = _ref_names(entry)
        if not names:
            continue
        score = sum(1 for r in raws if any(n in r or r in n for n in names))
        if score > 0:
            scored.append((score, ref))
    if not scored:
        return None
    scored.sort(reverse=True)
    top_score, top_ref = scored[0]
    if top_score < min_matches:
        return None
    if len(scored) > 1 and scored[1][0] == top_score:   # empate no topo = ambíguo
        return None
    return top_ref


def ref_hero_cards(entry):
    """Cartas do hero (strings) da entry do ref amarrado, ou [] (reusa a decodificação do
    protobuf_state: hero = assento com 2 cartas face-up)."""
    try:
        import protobuf_state as ps
        from ppp_cards import decode_cards
        players = (entry or {}).get("players", []) or []
        hs = ps.hero_seat(players)
        if hs is None:
            return []
        for p in players:
            if p.get("seat") == hs:
                return decode_cards(p.get("cards") or [])
    except Exception:
        pass
    return []
