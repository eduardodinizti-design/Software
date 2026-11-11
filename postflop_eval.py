"""Avaliação pós-flop pura: textura/estrutura do board e força da mão do hero.

Sem captura e sem clique. Reaproveita o avaliador exato de 7 cartas (`eval7`) e o
parser de cartas do motor de equity. A classificação de board segue o vocabulário
de estudo (skill poker-fundamentos-posflop): textura (monotone/two-tone/rainbow,
pareado, trinca), estrutura por famílias A/H/M/L (A=Á, H=K-T, M=9-6, L=5-2) e
"straightness" (quantas cartas do board entram numa janela de 5 ranks). A força da
mão combina o rótulo relativo ao board (set, overpair, top pair, dois pares...) com
as GAVETAS clássicas de draws e suas contagens de outs (flush=9, OESD=8, gutshot=4,
combo≤15). Nada aqui decide a jogada — isso é do postflop_advisor.
"""
from collections import Counter

from preflop_equity import parse_card, eval7, SUITS

CATEGORY_NAMES = {8: 'straight_flush', 7: 'quads', 6: 'full_house', 5: 'flush',
                  4: 'straight', 3: 'trips', 2: 'two_pair', 1: 'pair', 0: 'high_card'}


def _cards(seq):
    """Normaliza strings/tuplas em tuplas (rank:int, naipe:str). Levanta ValueError."""
    return [parse_card(c) if isinstance(c, str) else (int(c[0]), c[1]) for c in seq]


def _family(rank):
    """Família estrutural de um rank: A / H (K-T) / M (9-6) / L (5-2)."""
    if rank == 14:
        return 'A'
    if rank >= 10:
        return 'H'
    if rank >= 6:
        return 'M'
    return 'L'


def _has_straight(rank_set):
    """Há uma sequência de 5 ranks consecutivos no conjunto? (Á conta como 1 e 14.)"""
    rs = set(rank_set)
    if 14 in rs:
        rs.add(1)
    for top in range(14, 4, -1):
        if all(x in rs for x in range(top, top - 5, -1)):
            return True
    return False


def classify_board(board):
    """Descreve o board (3 a 5 cartas) por textura e estrutura. Dict com:

    - `texture`: 'monotone'/'two_tone'/'rainbow' no flop; 'flush_N' no turn/river
      (N = maior naipe presente).
    - `paired`/`trips`/`quads`: multiplicidade máxima de rank no board.
    - `flush_count`: maior nº de cartas de um mesmo naipe (3 já = flush possível).
    - `flush_possible`/`straight_on_board`: o board já completa flush/sequência.
    - `straightish`: máximo de ranks do board dentro de uma janela de 5 (3 = board
      coordenado; 4 = muito molhado). Indica potencial de sequência.
    - `structure`: famílias A/H/M/L dos ranks distintos, do mais alto ao mais baixo.
    - `high_rank`: rank mais alto do board.
    """
    cards = _cards(board)
    if not 3 <= len(cards) <= 5:
        raise ValueError('board precisa de 3 a 5 cartas: %r' % (board,))
    ranks = [r for r, _ in cards]
    suits = [s for _, s in cards]
    rc, sc = Counter(ranks), Counter(suits)
    flush_count = max(sc.values())
    mult = sorted(rc.values(), reverse=True)
    n = len(cards)
    if n == 3:
        texture = {3: 'monotone', 2: 'two_tone', 1: 'rainbow'}[flush_count]
    else:
        texture = 'flush_%d' % flush_count
    rset = set(ranks)
    straightish = 0
    probe = rset | ({1} if 14 in rset else set())
    for top in range(14, 4, -1):
        straightish = max(straightish, sum(1 for r in range(top, top - 5, -1) if r in probe))
    distinct_desc = sorted(set(ranks), reverse=True)
    return dict(
        cards=list(board), n=n, flush_count=flush_count,
        paired=mult[0] >= 2, trips=mult[0] >= 3, quads=mult[0] >= 4,
        texture=texture, flush_possible=flush_count >= 3,
        straight_on_board=_has_straight(rset), straightish=straightish,
        structure=[_family(r) for r in distinct_desc], high_rank=max(ranks),
    )


def _straight_out_cards(hero_cards, board_cards):
    """Nº de CARTAS que completam uma sequência (0 se já é sequência). OESD=8, gutshot=4."""
    present = hero_cards + board_cards
    ranks = {r for r, _ in present}
    if _has_straight(ranks):
        return 0
    seen = set(present)
    cnt = 0
    for r in range(2, 15):
        if r in ranks:
            continue
        if _has_straight(ranks | {r}):
            cnt += sum(1 for s in SUITS if (r, s) not in seen)
    return cnt


def _draws(hero_cards, board_cards):
    """Gavetas de draw do hero e contagem de outs (cartas), com contribuição do hero.

    Só conta flush/sequência em que o hero PARTICIPA (não draw que é só do board). O
    combo (FD + straight) é limitado a 15 outs, descontando a interseção exata. No
    RIVER (board com 5 cartas) NÃO há draw: não vem mais carta -> tudo zero.
    """
    if len(board_cards) >= 5:
        return dict(flush_draw=False, backdoor_flush=False, flush_outs=0,
                    straight_outs=0, oesd=False, gutshot=False, combo=False, outs=0)
    present = hero_cards + board_cards
    suits = Counter(s for _, s in present)
    hero_suits = Counter(s for _, s in hero_cards)
    flush_draw = False
    backdoor_flush = False
    flush_suit = None
    for s, ct in suits.items():
        if ct == 4 and hero_suits.get(s, 0) >= 1:
            flush_draw, flush_suit = True, s
        elif ct == 3 and hero_suits.get(s, 0) >= 1 and len(board_cards) == 3:
            backdoor_flush = True
    made_flush = any(ct >= 5 for ct in suits.values())
    seen = set(present)
    flush_out_cards = 0
    if flush_draw and not made_flush:
        flush_out_cards = sum(1 for r in range(2, 15) if (r, flush_suit) not in seen)
    straight_out_cards = _straight_out_cards(hero_cards, board_cards)
    # Interseção: cartas do naipe do flush que TAMBÉM completam a sequência não devem
    # ser contadas duas vezes no total do combo.
    overlap = 0
    if flush_draw and straight_out_cards:
        ranks = {r for r, _ in present}
        for r in range(2, 15):
            if r in ranks or (r, flush_suit) in seen:
                continue
            if _has_straight(ranks | {r}):
                overlap += 1  # a carta (r, flush_suit) conta em ambos
    oesd = straight_out_cards >= 8
    gutshot = straight_out_cards == 4
    total = flush_out_cards + straight_out_cards - overlap
    return dict(flush_draw=flush_draw, backdoor_flush=backdoor_flush,
                flush_outs=flush_out_cards, straight_outs=straight_out_cards,
                oesd=oesd, gutshot=gutshot,
                combo=bool(flush_draw and straight_out_cards >= 4),
                outs=min(total, 15))


def _relative_label(hero_cards, board_cards, category):
    """Rótulo da força relativa ao board, SEMPRE exigindo contribuição do hero.

    Quando a categoria vem SÓ do board (dois pares/trinca/sequência/flush no próprio
    board, ou o hero não supera o que o board já faz), o rótulo é fraco
    ('board_two_pair', 'board_trips', 'plays_board', 'board_pair_only') — o hero não
    tem a mão forte, só valor de showdown. Caso contrário distingue set/trinca,
    overpair/underpair, top/second/third pair e nomeia straight+ de fato do hero.
    """
    c = category[0]
    board_desc = sorted({r for r, _ in board_cards}, reverse=True)
    board_counts = Counter(r for r, _ in board_cards)
    hero_ranks = sorted((r for r, _ in hero_cards), reverse=True)
    hero_set = set(hero_ranks)
    pocket_pair = hero_ranks[0] == hero_ranks[1]
    top = board_desc[0] if board_desc else 0
    board_best = eval7(board_cards)
    hero_improves = category > board_best       # o hero supera o que o board já faz?

    if c >= 4:
        # sequência / flush / full house / quadra / straight flush: se o hero não
        # supera o board (todo mundo "joga o board"), é só valor de showdown.
        return CATEGORY_NAMES[c] if hero_improves else 'plays_board'
    if c == 3:
        trip_rank = next((r for r, ct in board_counts.items() if ct >= 3), None)
        if trip_rank is not None:
            return 'board_trips'                # trinca no próprio board
        return 'set' if pocket_pair else 'trips'
    if c == 2:
        board_pairs = [r for r, ct in board_counts.items() if ct >= 2]
        if len(board_pairs) >= 2:
            return 'board_two_pair'             # dois pares no próprio board (hero só kicker)
        return 'two_pair'
    if c == 1:
        if pocket_pair:
            return 'overpair' if hero_ranks[0] > top else 'underpair'
        matched = [r for r in board_desc if r in hero_set and board_counts[r] >= 1]
        if not matched:
            return 'board_pair_only'            # par só do board; hero não pareou
        m = max(matched)
        if m == board_desc[0]:
            return 'top_pair'
        if len(board_desc) >= 2 and m == board_desc[1]:
            return 'second_pair'
        if len(board_desc) >= 3 and m == board_desc[2]:
            return 'third_pair'
        return 'low_pair'
    # carta alta
    if board_desc and all(h > top for h in hero_ranks):
        return 'overcards'
    return 'air'


def hand_strength(hero, board):
    """Força da mão do hero no board. hero: 2 strings; board: 3-5 strings.

    Dict: `category`/`category_name`/`score` (do eval7), `made` (rótulo relativo),
    `draws` (gavetas + outs) e `outs`. Levanta ValueError para entrada inválida e
    retorna None se houver carta repetida entre hero e board (leitura inconsistente).
    """
    hc, bc = _cards(hero), _cards(board)
    if len(hc) != 2 or not 3 <= len(bc) <= 5:
        raise ValueError('hero precisa de 2 cartas e board de 3-5')
    if len(set(hc) | set(bc)) != len(hc) + len(bc):
        return None
    score = eval7(hc + bc)
    draws = _draws(hc, bc)
    return dict(category=score[0], category_name=CATEGORY_NAMES[score[0]], score=score,
                made=_relative_label(hc, bc, score), draws=draws, outs=draws['outs'])
