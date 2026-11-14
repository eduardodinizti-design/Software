"""Parser de histórico de mãos (.txt do PPPoker / formato PokerStars) + replay.

PURO: lê texto, não captura tela nem clica. Porta a lógica do `handParser.ts` do
estudo VisualPilot 2.0 para Python e acrescenta (1) normalização de fichas->BB pelo
nível de blinds do cabeçalho e (2) extração dos PONTOS DE DECISÃO PÓS-FLOP do hero
(pote/aposta a pagar/stack em BB, board, cartas, nº de oponentes, tipo de pote,
iniciativa e linha do vilão) para o auditor de leaks (`leak_audit.py`) graduar contra
o cérebro pós-flop. NÃO decide nada — só reconstrói o estado.

Dado de ENTRADA é conteúdo do usuário (export dele): tratado como texto, nunca
executado; parsing tolerante a linhas malformadas (pula o que não casa).
"""
import re

_RANK = set('23456789TJQKA')
_SUIT = set('shdc')
_HAND_SPLIT = re.compile(r'(?=(?:PPPoker Hand #|Hand #|Mão #|PokerStars Hand #|Game #))', re.I)


def _cards_in_brackets(s):
    out = []
    for m in re.findall(r'\[([^\]]+)\]', s):
        for tok in m.split():
            tok = tok.strip()
            if len(tok) == 2 and tok[0].upper() in _RANK and tok[1].lower() in _SUIT:
                out.append(tok[0].upper() + tok[1].lower())
    return out


def _amount(s):
    cleaned = re.sub(r'[^\d.]', '', s.replace(',', ''))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def _parse_blinds(header):
    """(sb, bb, ante) em fichas a partir de '(100/200, Ante 25)'; sb/bb=None se não achar.
    O Ante é buscado à parte para o número do BB não engolir a vírgula delimitadora."""
    m = re.search(r'\(\s*([\d,.]+)\s*/\s*([\d,.]+)', header)
    sb = _amount(m.group(1)) if m else None
    bb = _amount(m.group(2)) if m else None
    ma = re.search(r'Ante\s*([\d,.]+)', header, re.I)
    ante = _amount(ma.group(1)) if ma else 0.0
    return sb, bb, ante


class Hand:
    """Uma mão parseada. Campos em FICHAS, exceto os *_bb nos decision points."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def parse_hand_histories(raw_text, preferred_hero=None):
    """Lista de `Hand` a partir do texto. `preferred_hero`: nick do hero (senão detecta
    por 'Dealt to' / assento 'Hero')."""
    text = (raw_text or '').strip()
    if not text:
        return []
    blocks = [b.strip() for b in _HAND_SPLIT.split(text) if len(b.strip()) > 20]
    hands = []
    for idx, block in enumerate(blocks):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        hands.append(_parse_block(lines, idx, preferred_hero))
    return hands


def _parse_block(lines, idx, preferred_hero):
    header = lines[0]
    m_id = re.search(r'#(\d+)', header)
    hand_id = '#%s' % (m_id.group(1) if m_id else idx + 1)
    sb, bb, ante = _parse_blinds(header)

    players = {}          # name -> dict(seat, stack, bounty)
    order = []
    button_seat = None
    table = 'Mesa PPPoker'
    hero = (preferred_hero or '').strip()
    hero_cards = []

    for ln in lines:
        mt = re.search(r"Table\s+'([^']+)'", ln, re.I)
        if mt:
            table = mt.group(1)
        mb = re.search(r'Seat\s+#(\d+)\s+is\s+the\s+button', ln, re.I)
        if mb:
            button_seat = int(mb.group(1))
        ms = re.match(r'^Seat\s+(\d+):\s+(.+?)\s+\(([^)]+)\)', ln, re.I)
        if ms:
            name = ms.group(2).strip()
            paren = ms.group(3)
            mstack = re.search(r'([\d,.]+)\s+in\s+chips', paren, re.I)
            stack = _amount(mstack.group(1)) if mstack else _amount(paren)
            mbounty = re.search(r'Bounty\s+([^,)]+)', paren, re.I)
            players[name] = dict(seat=int(ms.group(1)), stack=stack,
                                 bounty=mbounty.group(1).strip() if mbounty else None)
            order.append(name)
        md = re.match(r'^Dealt\s+to\s+(.+?)\s+\[([^\]]+)\]', ln, re.I)
        if md and (not preferred_hero or md.group(1).strip().lower() == hero.lower()):
            hero = md.group(1).strip()
            hero_cards = _cards_in_brackets('[%s]' % md.group(2))

    if not hero:
        hero = 'Hero' if 'Hero' in players else (order[0] if order else 'Hero')

    # Fallback: cartas do hero reveladas no showdown ('shows'/'mucks hand') quando não
    # houve linha 'Dealt to' (comum quando o export só mostra as cartas no showdown).
    if not hero_cards:
        for ln in lines:
            msh = re.match(r'^(.+?):\s+(?:shows|mucks\s+hand)\s+\[([^\]]+)\]', ln, re.I)
            if msh and msh.group(1).strip().lower() == hero.lower():
                hero_cards = _cards_in_brackets('[%s]' % msh.group(2))
                break

    decisions, board = _replay(lines, players, hero, bb)
    return Hand(id=hand_id, header=header, table=table, button_seat=button_seat,
                sb=sb, bb=bb, ante=ante, hero=hero, hero_cards=hero_cards,
                players=players, board=board, hero_decisions=decisions,
                has_postflop=len(board) >= 3)


_STREET_OF = {0: 'PREFLOP', 3: 'FLOP', 4: 'TURN', 5: 'RIVER'}


def _replay(lines, players, hero, bb):
    """Reconstrói pote/apostas e devolve (decisions, board_final). Cada decision é um
    ponto de ação PÓS-FLOP do hero com contexto em BB."""
    stacks = {n: p['stack'] for n, p in players.items()}
    paid_total = {n: 0.0 for n in players}      # fichas pagas no total (todas as ruas)
    street_bet = {n: 0.0 for n in players}      # fichas pagas NESTA rua
    folded = {n: False for n in players}
    pot = 0.0
    board = []
    street = 'PREFLOP'
    preflop_raises = 0
    last_pf_raiser = None
    # Linha do vilão por rua: quem foi passivo (check/call) e quem agrediu.
    passive_ever = {n: False for n in players}
    decisions = []
    saw_flop = set()        # jogadores que chegaram ao flop (não foldaram pré)

    def new_street(cards):
        nonlocal street, board
        board = cards
        street = _STREET_OF.get(len(cards), street)
        for n in street_bet:
            street_bet[n] = 0.0

    for ln in lines:
        if ln.startswith('*** FLOP ***'):
            new_street(_cards_in_brackets(ln)[:3])
            saw_flop.update(n for n in players if not folded[n])
            continue
        if ln.startswith('*** TURN ***'):
            new_street(_cards_in_brackets(ln)[:4])
            continue
        if ln.startswith('*** RIVER ***'):
            new_street(_cards_in_brackets(ln)[:5])
            continue
        if ln.startswith('*** SHOW') or ln.startswith('*** SUMMARY'):
            street = 'SHOWDOWN'
            continue
        mu = re.match(r'^Uncalled\s+bet\s+\(([\d,.]+)\)\s+returned\s+to\s+(.+)$', ln, re.I)
        if mu:
            amt, who = _amount(mu.group(1)), mu.group(2).strip()
            pot = max(0.0, pot - amt)
            if who in stacks:
                stacks[who] += amt
                street_bet[who] = max(0.0, street_bet[who] - amt)
                paid_total[who] = max(0.0, paid_total[who] - amt)
            continue
        if re.search(r'collected\s+[\d,.]+\s+from\s+pot', ln, re.I):
            continue
        ma = re.match(r'^(.+?):\s+(.+)$', ln)
        if not ma:
            continue
        actor, body = ma.group(1).strip(), ma.group(2).strip()
        if actor not in stacks:
            continue

        # Blinds / ante: entram no pote; blinds contam como aposta da rua.
        if re.match(r'^posts\s+(small|big)\s+blind', body, re.I) or re.match(r'^posts\s+the\s+ante', body, re.I):
            amt = min(stacks[actor], _amount(body))
            stacks[actor] -= amt
            paid_total[actor] += amt
            pot += amt
            if not re.search(r'ante', body, re.I):
                street_bet[actor] += amt
            continue

        is_hero = actor == hero
        max_street = max(street_bet.values()) if street_bet else 0.0
        to_call = max(0.0, max_street - street_bet[actor])

        # Captura o CONTEXTO do hero ANTES de aplicar a ação (pós-flop apenas).
        if is_hero and street in ('FLOP', 'TURN', 'RIVER'):
            action, amount = _classify_action(body)
            if action:
                # Vilão que foi passivo antes (check/call) e agora JÁ colocou fichas nesta
                # rua (bet/check-raise) = passivo->agressivo (tell forte no pool).
                aggro_after_passive = any(
                    passive_ever[n] and not folded[n] and street_bet[n] > 0
                    for n in players if n != hero)
                decisions.append(_decision_context(
                    street=street, board=list(board), hero=hero,
                    pot_chips=pot, to_call_chips=to_call,
                    hero_stack_chips=stacks[actor], bb=bb,
                    players=players, folded=folded, saw_flop=saw_flop,
                    preflop_raises=preflop_raises, last_pf_raiser=last_pf_raiser,
                    aggro_after_passive=aggro_after_passive, actor=actor,
                    action=action, amount_chips=amount))

        # Aplica a ação ao estado.
        if re.match(r'^folds', body, re.I):
            folded[actor] = True
        elif re.match(r'^checks', body, re.I):
            pass
        elif re.match(r'^calls', body, re.I):
            paid = min(stacks[actor], _amount(body))
            stacks[actor] -= paid
            street_bet[actor] += paid
            paid_total[actor] += paid
            pot += paid
            if street != 'PREFLOP':
                passive_ever[actor] = passive_ever[actor]  # call = passivo nessa rua
        elif re.match(r'^bets', body, re.I):
            paid = min(stacks[actor], _amount(body))
            stacks[actor] -= paid
            street_bet[actor] += paid
            paid_total[actor] += paid
            pot += paid
        elif re.match(r'^raises', body, re.I):
            mto = re.search(r'to\s+([\d,.]+)', body, re.I)
            target = _amount(mto.group(1)) if mto else street_bet[actor] + _amount(body)
            add = max(0.0, target - street_bet[actor])
            paid = min(stacks[actor], add)
            stacks[actor] -= paid
            street_bet[actor] += paid
            paid_total[actor] += paid
            pot += paid
            if street == 'PREFLOP':
                preflop_raises += 1
                last_pf_raiser = actor

        # Marca passividade pós-flop (check/call) para detectar passivo->agressivo.
        if street in ('FLOP', 'TURN', 'RIVER') and re.match(r'^(checks|calls)', body, re.I):
            passive_ever[actor] = True

    return decisions, board


def _classify_action(body):
    """(action, amount_chips) a partir do corpo da linha; (None, 0) se não for ação."""
    if re.match(r'^folds', body, re.I):
        return 'fold', 0.0
    if re.match(r'^checks', body, re.I):
        return 'check', 0.0
    if re.match(r'^calls', body, re.I):
        return 'call', _amount(body)
    if re.match(r'^bets', body, re.I):
        return 'bet', _amount(body)
    if re.match(r'^raises', body, re.I):
        mto = re.search(r'to\s+([\d,.]+)', body, re.I)
        return 'raise', _amount(mto.group(1)) if mto else _amount(body)
    return None, 0.0


def _decision_context(*, street, board, hero, pot_chips, to_call_chips,
                      hero_stack_chips, bb, players, folded, saw_flop,
                      preflop_raises, last_pf_raiser, aggro_after_passive, actor,
                      action, amount_chips):
    """Monta o contexto de uma decisão do hero, normalizando fichas->BB."""
    scale = bb if isinstance(bb, (int, float)) and bb > 0 else 1.0
    opponents = sum(1 for n in players if n != hero and not folded[n])
    # Nº que viram o flop define multiway; 3bet pot se houve 2+ raises pré.
    if len(saw_flop) > 2:
        pot_type = 'multiway'
    elif preflop_raises >= 2:
        pot_type = 'three_bet'
    else:
        pot_type = None
    aggressor = 'hero' if last_pf_raiser == hero else ('villain' if last_pf_raiser else None)
    # Linha do vilão: passivo antes que agora agride (bet/check-raise) e o hero paga.
    villain_line = ('passive_turned_aggressive'
                    if to_call_chips > 0 and aggro_after_passive else None)
    return dict(
        street=street, board=board, hero=hero,
        pot_bb=round(pot_chips / scale, 2), to_call_bb=round(to_call_chips / scale, 2),
        hero_stack_bb=round(hero_stack_chips / scale, 2),
        opponents=opponents, pot_type=pot_type, aggressor=aggressor,
        villain_line=villain_line, hero_action=action,
        hero_amount_bb=round(amount_chips / scale, 2),
        bb_chips=scale)
