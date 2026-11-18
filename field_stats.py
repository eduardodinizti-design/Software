"""DB de ADVERSÁRIOS (estudo do field) a partir das hand histories em TEXTO (PPPoker/KK).

Por jogador, ao longo de todas as mãos, os stats de HUD:
  hands, VPIP%, PFR%, 3bet%, AF, STEAL%, FOLD3BET%, CBET%, FOLDCBET%  + TAG de perfil.

Puro texto -> stats. Uso:
    from field_stats import build_field
    f = build_field(open('corpus.txt', encoding='utf-8').read())
    print(f.report(top=20, min_hands=25, exclude=('11918386',)))
"""
from __future__ import annotations
import re
from collections import defaultdict

from hand_history import _HAND_SPLIT

_ACT_RE = re.compile(r'^(.+?):\s+(.+)$')
_SEAT_RE = re.compile(r'^Seat\s+(\d+):\s+(.+?)\s+\([\d,.]+\s+in\s+chips', re.I)
_BTN_RE = re.compile(r'Seat\s+#?(\d+)\s+is\s+the\s+button', re.I)
_POST_RE = re.compile(r'^posts\s+(?:small\s+blind|big\s+blind|the\s+ante)', re.I)
_POST_SB = re.compile(r'^posts\s+small\s+blind', re.I)
_POST_BB = re.compile(r'^posts\s+big\s+blind', re.I)


class _P:
    __slots__ = ('hands', 'vpip', 'pfr', 'faced_raise', 'threebet',
                 'post_aggr', 'post_call', 'post_check',
                 'steal_opp', 'steal_att', 'fold3bet_opp', 'fold3bet_made',
                 'cbet_opp', 'cbet_made', 'foldcbet_opp', 'foldcbet_made')

    def __init__(self):
        for s in self.__slots__:
            setattr(self, s, 0)


def _pct(num, den):
    return 100.0 * num / den if den else 0.0


def _tag(s):
    vpip, pfr, af, hands = s['vpip'], s['pfr'], s['af'], s['hands']
    if hands < 25:
        return '?'
    extra = []
    if s['foldcbet'] is not None and s['foldcbet'] >= 55:
        extra.append('folds_to_cbet')
    elif s['foldcbet'] is not None and 0 < s['foldcbet'] <= 35:
        extra.append('station')
    if s['cbet'] is not None and s['cbet'] >= 65:
        extra.append('cbet_heavy')
    if vpip < 16:
        base = 'nit' if pfr < 12 else 'TAG-nit'
    elif vpip <= 26:
        base = 'TAG' if pfr >= vpip * 0.6 else 'passivo'
    elif pfr >= vpip * 0.55:
        base = 'LAG' if af >= 2.0 else 'LAG-loose'
    else:
        base = 'maniac' if af >= 3.0 else 'fish-passivo'
    return base + ((' [' + ','.join(extra) + ']') if extra else '')


class Field:
    def __init__(self, players):
        self.players = players

    def stats(self, name):
        p = self.players.get(name)
        if not p or not p.hands:
            return None
        s = dict(
            hands=p.hands, vpip=_pct(p.vpip, p.hands), pfr=_pct(p.pfr, p.hands),
            threebet=_pct(p.threebet, p.faced_raise) if p.faced_raise else 0.0,
            af=(p.post_aggr / p.post_call) if p.post_call else float(p.post_aggr),
            steal=_pct(p.steal_att, p.steal_opp) if p.steal_opp else None,
            fold3bet=_pct(p.fold3bet_made, p.fold3bet_opp) if p.fold3bet_opp else None,
            cbet=_pct(p.cbet_made, p.cbet_opp) if p.cbet_opp else None,
            foldcbet=_pct(p.foldcbet_made, p.foldcbet_opp) if p.foldcbet_opp else None,
        )
        s['tag'] = _tag(s)
        return s

    def ranked(self, min_hands=25, exclude=()):
        rows = [(n, self.stats(n)) for n, p in self.players.items()
                if n not in exclude and p.hands >= min_hands]
        rows.sort(key=lambda r: r[1]['hands'], reverse=True)
        return rows

    def report(self, top=20, min_hands=25, exclude=()):
        def f(x):
            return '  -' if x is None else f"{x:>4.0f}"
        out = [f"{'JOGADOR':<16}{'MÃOS':>6}{'VPIP':>6}{'PFR':>6}{'3BET':>6}{'AF':>5}"
               f"{'STL':>6}{'F3B':>6}{'CB':>6}{'FCB':>6}  PERFIL", '-' * 86]
        for name, s in self.ranked(min_hands, exclude)[:top]:
            out.append(f"{name[:15]:<16}{s['hands']:>6}{s['vpip']:>5.0f}%{s['pfr']:>5.0f}%"
                       f"{s['threebet']:>5.0f}%{s['af']:>5.1f}{f(s['steal'])}{f(s['fold3bet'])}"
                       f"{f(s['cbet'])}{f(s['foldcbet'])}  {s['tag']}")
        return '\n'.join(out)

    def exploit_notes(self, top=10, min_hands=40, exclude=()):
        notes = []
        for name, s in self.ranked(min_hands, exclude)[:top]:
            tips = []
            if s['foldcbet'] is not None and s['foldcbet'] >= 55:
                tips.append('folda à c-bet → c-betar mais (blefe)')
            if s['foldcbet'] is not None and 0 < s['foldcbet'] <= 35:
                tips.append('station → não blefar, value bet maior')
            if s['vpip'] >= 30 and s['pfr'] < s['vpip'] * 0.5:
                tips.append('loose-passivo → isolar/value, sem blefe')
            if s['pfr'] < 10 and s['vpip'] < 18:
                tips.append('nit → roubar blinds')
            if s['af'] >= 3.0:
                tips.append('agressivo → pagar mais leve')
            if s['fold3bet'] is not None and s['fold3bet'] >= 60:
                tips.append('folda a 3bet → 3bet blefe mais')
            if tips:
                notes.append(f"{name[:15]} ({s['hands']}m): " + '; '.join(tips))
        return '\n'.join(notes)


def _positions(active_seats, button_seat, sb_seat):
    """Devolve o conjunto de assentos de ROUBO (BTN/SB/CO)."""
    steal = set()
    if button_seat is not None:
        steal.add(button_seat)
    if sb_seat is not None:
        steal.add(sb_seat)
    if button_seat is not None and active_seats:
        below = [s for s in active_seats if s < button_seat]
        co = max(below) if below else max(active_seats)
        if co != button_seat:
            steal.add(co)
    return steal


def _accumulate(players, block):
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    seat_of = {}            # name -> seat num
    seated = []
    button_seat = None
    for ln in lines:
        m = _SEAT_RE.match(ln)
        if m:
            seat_of[m.group(2).strip()] = int(m.group(1))
            seated.append(m.group(2).strip())
            continue
        mb = _BTN_RE.search(ln)
        if mb:
            button_seat = int(mb.group(1))
    if not seated:
        return
    seated_set = set(seated)

    # descobre SB
    sb_name = None
    for ln in lines:
        m = _ACT_RE.match(ln)
        if m and m.group(1).strip() in seated_set and _POST_SB.match(m.group(2).strip()):
            sb_name = m.group(1).strip(); break
    steal_seats = _positions(sorted(seat_of.values()), button_seat,
                             seat_of.get(sb_name) if sb_name else None)

    # flags por mão (contar 1x por mão onde aplicável)
    f_vpip, f_pfr, f_faced, f_3bet = set(), set(), set(), set()
    steal_opp, steal_att = set(), set()
    opened = False
    pf_raises = 0
    opener = None            # 1º raiser (2bet)
    three_bettor = None      # 2º raiser
    fold3bet_opp = fold3bet_made = None  # p/ o opener
    street = 'PRE'
    pfr = None               # último raiser pré (c-bettor em potencial)
    folded_pre = set()
    saw_flop = False
    # flop
    flop_first_bet_by = None
    cbet_counted = False
    fcb_seen = set()

    for ln in lines:
        if ln.startswith('*** HOLE CARDS'):
            street = 'PRE'; continue
        if ln.startswith('*** FLOP'):
            street = 'FLOP'; saw_flop = True; continue
        if ln.startswith(('*** TURN', '*** RIVER')):
            street = 'POST'; continue       # c-bet só mede no flop
        if ln.startswith(('*** SUMMARY', '*** SHOW')):
            break
        if ln.startswith('Uncalled'):
            continue
        m = _ACT_RE.match(ln)
        if not m:
            continue
        actor, body = m.group(1).strip(), m.group(2).strip()
        if actor not in seated_set or 'collected' in body:
            continue
        if _POST_RE.match(body):
            continue
        p = players[actor]
        is_raise = bool(re.match(r'^raises', body, re.I))
        is_call = bool(re.match(r'^calls', body, re.I))
        is_bet = bool(re.match(r'^bets', body, re.I))
        is_check = bool(re.match(r'^checks', body, re.I))
        is_fold = bool(re.match(r'^folds', body, re.I))

        if street == 'PRE':
            faced = pf_raises >= 1
            # STEAL: assento de roubo, pote ainda não aberto, 1ª ação dele
            if seat_of.get(actor) in steal_seats and not opened and actor not in steal_opp:
                steal_opp.add(actor)
                if is_raise:
                    steal_att.add(actor)
            if faced:
                f_faced.add(actor)
            if is_raise:
                f_vpip.add(actor); f_pfr.add(actor)
                if faced:
                    f_3bet.add(actor)
                pf_raises += 1
                if opener is None:
                    opener = actor
                elif three_bettor is None and actor != opener:
                    three_bettor = actor       # 3bet ocorreu
                    if opener is not None:
                        fold3bet_opp = opener  # o opener agora enfrentará o 3bet
                pfr = actor
                opened = True
            elif is_call:
                f_vpip.add(actor); opened = True
            elif is_bet:
                f_vpip.add(actor); opened = True
            elif is_fold:
                folded_pre.add(actor)
                if actor == fold3bet_opp and fold3bet_made is None:
                    fold3bet_made = True       # opener foldou ao 3bet
            # opener que enfrentou 3bet e NÃO foldou (call/raise) -> made=False
            if three_bettor is not None and actor == opener and not is_fold and fold3bet_made is None:
                fold3bet_made = False
        elif street == 'FLOP':
            # 1º a apostar/raise no flop
            if flop_first_bet_by is None and (is_bet or is_raise):
                flop_first_bet_by = actor
                if actor == pfr and is_bet:
                    cbet_counted = True       # pfr fez a c-bet (1ª aposta do flop)
            # fold-to-cbet: encara a c-bet do pfr (1x por jogador)
            if cbet_counted and pfr is not None and actor != pfr and actor not in fcb_seen:
                fcb_seen.add(actor)
                players[actor].foldcbet_opp += 1
                if is_fold:
                    players[actor].foldcbet_made += 1

    # ---- consolida a mão ----
    for n in seated:
        players[n].hands += 1
    for n in f_vpip:
        players[n].vpip += 1
    for n in f_pfr:
        players[n].pfr += 1
    for n in f_faced:
        players[n].faced_raise += 1
    for n in f_3bet:
        players[n].threebet += 1
    for n in steal_opp:
        players[n].steal_opp += 1
    for n in steal_att:
        players[n].steal_att += 1
    if fold3bet_opp is not None:
        players[fold3bet_opp].fold3bet_opp += 1
        if fold3bet_made:
            players[fold3bet_opp].fold3bet_made += 1
    # c-bet: o pfr teve oportunidade se chegou ao flop
    if pfr is not None and pfr not in folded_pre and saw_flop:
        players[pfr].cbet_opp += 1
        if cbet_counted:
            players[pfr].cbet_made += 1

    # post-flop AF (agressão) — recomputa percorrendo flop/turn/river
    _accumulate_postflop_af(players, lines, seated_set)


def _accumulate_postflop_af(players, lines, seated_set):
    street = 'PRE'
    for ln in lines:
        if ln.startswith('*** HOLE CARDS'):
            street = 'PRE'; continue
        if ln.startswith(('*** FLOP', '*** TURN', '*** RIVER')):
            street = 'POST'; continue
        if ln.startswith(('*** SUMMARY', '*** SHOW')):
            break
        if ln.startswith('Uncalled'):
            continue
        m = _ACT_RE.match(ln)
        if not m or street != 'POST':
            continue
        actor, body = m.group(1).strip(), m.group(2).strip()
        if actor not in seated_set or 'collected' in body:
            continue
        if re.match(r'^(bets|raises)', body, re.I):
            players[actor].post_aggr += 1
        elif re.match(r'^calls', body, re.I):
            players[actor].post_call += 1
        elif re.match(r'^checks', body, re.I):
            players[actor].post_check += 1


def build_field(raw_text):
    players = defaultdict(_P)
    for block in (b.strip() for b in _HAND_SPLIT.split(raw_text or '') if len(b.strip()) > 20):
        _accumulate(players, block)
    return Field(players)


def _main():
    import argparse, glob, os, sys
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    ap = argparse.ArgumentParser(description='DB de adversários a partir de HHs em texto.')
    ap.add_argument('arquivos', nargs='+')
    ap.add_argument('--top', type=int, default=25)
    ap.add_argument('--min-hands', type=int, default=25)
    ap.add_argument('--exclude', default='')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    paths = [p for pat in a.arquivos for p in glob.glob(pat)] or a.arquivos
    raw = []
    for p in paths:
        try:
            raw.append(open(p, encoding='utf-8', errors='replace').read())
        except OSError as e:
            print('[field] erro lendo', p, e)
    f = build_field('\n'.join(raw))
    ex = tuple(x.strip() for x in a.exclude.split(',') if x.strip())
    rep = (f.report(top=a.top, min_hands=a.min_hands, exclude=ex)
           + '\n\n=== EXPLORAÇÃO ===\n' + f.exploit_notes(top=12, min_hands=max(60, a.min_hands), exclude=ex))
    print(rep)
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(rep + '\n')
        print('\n[field] salvo em', a.out)


if __name__ == '__main__':
    _main()
