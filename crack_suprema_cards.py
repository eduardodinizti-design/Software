r"""CRACKER do encoding de cartas >59 da Suprema — OFFLINE, por EVIDÊNCIA, SEM CHUTAR.

Carta normal = `code = rank*4 + suit`, 8..59 (2d..As). Mas alguns códigos aparecem >59
(ex. 60,62,66) nos MESMOS campos de carta (board/mãos reveladas/melhor-jogo) e o decoder
padrão não os mapeia. Em vez de adivinhar (carta errada é pior que ausente), cruzamos:

ESTRUTURA real do evento (descoberta no dump):
  data.game_info.shared_cards            -> BOARD (comunitárias), ordem de saída
  data.game_seat[uid].cards              -> mão (herói vem em código PADRÃO; vilão oculto)
  data.game_result.seats[uid].cards      -> mãos REVELADAS no showdown (pode ter >59)
  data.game_result.cards / .lightcards   -> melhor jogo de 5 (desordenado / ordenado)
  (NÃO são cartas: sidepots, preop, prize, chipsDiff, allpots, room_status.seats, patterns…)

LÓGICA (nunca chuta):
  - ANTI-RESTRIÇÃO: um código alt, numa mão, é uma carta física; logo ≠ qualquer carta
    PADRÃO presente na MESMA mão (board/holes revelados). Isso tira candidatos. Acumulando
    mãos, cada código alt converge; quando sobra 1 candidato, está PROVADO (forçado).
  - PIN DO HERÓI: quando o herói vai ao showdown, suas 2 cartas são conhecidas (código
    padrão no game_seat) E aparecem em game_result.seats[uid].cards (podendo vir em alt);
    então cada alt dessa dupla ∈ {as 2 cartas reais do herói}. Co-conjunto forte (≤2).
  - BIJEÇÃO: fixado um código, a carta sai dos candidatos dos demais.

Uso:
    python -I crack_suprema_cards.py logs\suprema_raw\suprema_2026-11-21.jsonl
    python -I crack_suprema_cards.py <dump.jsonl> --write       # grava os PROVADOS
"""
import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_RANKS = {2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9',
          10: 'T', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
_SUITS = {0: 'd', 1: 'c', 2: 'h', 3: 's'}
_FULL = frozenset(_RANKS[r] + _SUITS[s] for r in _RANKS for s in _SUITS)


def std_card(code):
    if isinstance(code, int) and 8 <= code <= 59:
        r, s = code // 4, code % 4
        if r in _RANKS:
            return _RANKS[r] + _SUITS[s]
    return None


def is_alt(code):
    return isinstance(code, int) and code > 59 and code < 256


def iter_events(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            msg = rec.get("msg", rec)
            if isinstance(msg, dict):
                yield msg


def segment_hands(events):
    hands, cur = [], []
    for m in events:
        cur.append(m)
        if m.get("event") == "gameover":
            hands.append(cur)
            cur = []
    if cur:
        hands.append(cur)
    return hands


def _as_card_lists(val):
    """Normaliza um campo de cartas: aceita [c,c,..] ou [[c,..],[c,..]] -> lista de listas."""
    out = []
    if isinstance(val, list):
        if val and all(isinstance(x, int) for x in val):
            out.append(val)
        else:
            for sub in val:
                if isinstance(sub, list) and all(isinstance(x, int) for x in sub):
                    out.append(sub)
    return out


def hand_cards(hand):
    """Extrai SÓ campos de carta da mão. Retorna dict com board, holes_std(uid->[cartas]),
    reveals(uid->[códigos]), best5(listas), prompt_uid, e todos os códigos de carta vistos."""
    board = []
    holes_std = {}      # uid -> códigos (2) do game_seat (herói em padrão)
    reveals = {}        # uid -> códigos revelados no gameover
    best5 = []
    prompt_uid = None
    codes = set()
    for m in hand:
        d = m.get("data") or {}
        if m.get("event") == "prompt" and m.get("uid") is not None:
            prompt_uid = m["uid"]
        gi = d.get("game_info") or {}
        sc = gi.get("shared_cards")
        if isinstance(sc, list) and all(isinstance(x, int) for x in sc) and len(sc) > len(board):
            board = list(sc)
        gs = d.get("game_seat") or gi.get("game_seat")
        if isinstance(gs, dict):
            for u, p in gs.items():
                cc = p.get("cards") or []
                if isinstance(cc, list) and len(cc) == 2 and all(isinstance(x, int) and x > 0 for x in cc):
                    holes_std[u] = list(cc)
        if m.get("event") == "gameover":
            gr = d.get("game_result") or {}
            for u, p in (gr.get("seats") or {}).items():
                cc = p.get("cards") or []
                if isinstance(cc, list) and len(cc) >= 2 and all(isinstance(x, int) and x > 0 for x in cc):
                    reveals[u] = list(cc)
            for key in ("lightcards", "cards", "shared_cardsMulti"):
                for lst in _as_card_lists(gr.get(key)):
                    best5.append(lst)
    for src in [board] + list(holes_std.values()) + list(reveals.values()) + best5:
        for c in src:
            if isinstance(c, int) and c > 0:
                codes.add(c)
    return {"board": board, "holes_std": holes_std, "reveals": reveals,
            "best5": best5, "prompt_uid": prompt_uid, "codes": codes}


def crack(hands):
    cand = {}                      # alt_code -> set de cartas possíveis
    pins = 0
    anti = 0
    for hand in hands:
        hc = hand_cards(hand)
        known_real = {std_card(c) for c in hc["codes"] if std_card(c)}
        alts = {c for c in hc["codes"] if is_alt(c)}
        for c in alts:
            cand.setdefault(c, set(_FULL))
            before = len(cand[c])
            cand[c] -= known_real          # ANTI: não pode ser uma carta padrão da mesma mão
            if len(cand[c]) != before:
                anti += 1
        # PIN do herói: cartas reais (padrão) × revelação no showdown
        hu = hc["prompt_uid"]
        if hu and hu in hc["holes_std"] and hu in hc["reveals"]:
            real = [std_card(c) for c in hc["holes_std"][hu]]
            if all(real):
                hset = set(real)
                for c in hc["reveals"][hu]:
                    if is_alt(c):
                        cand.setdefault(c, set(_FULL))
                        cand[c] &= hset
                        pins += 1
    # BIJEÇÃO: fixa singletons e remove-os dos demais, iterando
    proven = {}
    changed = True
    while changed:
        changed = False
        for code, cards in list(cand.items()):
            if len(cards) == 1:
                card = next(iter(cards))
                if code not in proven:
                    proven[code] = card
                    changed = True
                for o, oc in cand.items():
                    if o != code and card in oc and len(oc) > 1:
                        oc.discard(card)
                        changed = True
    return proven, cand, pins, anti


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.dump):
        print("dump não encontrado:", a.dump)
        return 2
    events = list(iter_events(a.dump))
    hands = segment_hands(events)

    # histograma dos códigos de carta (revela a faixa/forma do baralho)
    allc = set()
    n_showdown = 0
    for h in hands:
        hc = hand_cards(h)
        allc |= hc["codes"]
        if hc["reveals"]:
            n_showdown += 1
    std = sorted(c for c in allc if std_card(c))
    alt = sorted(c for c in allc if is_alt(c))
    print("eventos=%d | mãos=%d | com showdown=%d" % (len(events), len(hands), n_showdown))
    print("códigos de carta vistos: %d padrão (8..59) + %d alt (>59)" % (len(std), len(alt)))
    print("  alt vistos:", alt)

    proven, cand, pins, anti = crack(hands)
    print("\npins(herói)=%d | anti-restrições aplicadas=%d" % (pins, anti))
    print("PROVADOS: %d de %d códigos alt" % (len(proven), len(alt)))
    for c in sorted(proven):
        print("   %3d -> %s" % (c, proven[c]))
    pend = [c for c in alt if c not in proven]
    if pend:
        print("ainda não provados (precisam de mais mãos/showdowns):")
        for c in pend:
            n = len(cand.get(c, _FULL))
            print("   %3d : %d candidatos%s" % (c, n, (" -> " + str(sorted(cand[c])) if n <= 6 else "")))

    if a.write and proven:
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suprema_card_alt_map.json")
        prev = {}
        if os.path.exists(out):
            try:
                prev = json.load(open(out, encoding="utf-8"))
            except Exception:
                prev = {}
        prev.update({str(k): v for k, v in proven.items()})
        json.dump(prev, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
        print("\ngravado %d pares em %s" % (len(prev), out))
    elif a.write:
        print("\nnada PROVADO ainda — nada gravado (nunca chutamos).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
