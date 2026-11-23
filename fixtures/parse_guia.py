"""Parser dos exemplos do guia pós-flop -> fixtures JSON (ground-truth do Henrique).
Cada exemplo: board + mão do hero + classe + AÇÃO do guia (bet%/check/fold/call/all-in/raise) + nota,
tagueado com a SEÇÃO (c-bet IP/OOP/vs SB, probe, float, barris...). Formato do texto (pymupdf):
  <idx>\n <board>\n <mão(+classe)>\n [classe]\n <AÇÃO>\n <nota...>
A linha da MÃO é a 1ª (subindo da ação) que começa com 2 cartas; o board é a linha acima dela."""
from __future__ import annotations
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SCRATCH = r"C:\Users\tacao\AppData\Local\Temp\claude\14f5907446636a6c\7e811684-b06f-4aab-b355-4e902c3dcd41\scratchpad"
SRC = SCRATCH + r"\guia_posflop.txt"
OUT = SCRATCH + r"\guia_fixtures.json"

SUIT = {"\u2660": "s", "\u2665": "h", "\u2666": "d", "\u2663": "c"}
CARD = re.compile(r"(?:10|[2-9TJQKA])[shdc]")
HAND2 = re.compile(r"^((?:10|[2-9TJQKA])[shdc]){2}")
ACTION = re.compile(r"^(Aposta|Check-?raise|Check-?call|Check-?fold|Checa|Check|Folda|Fold|"
                    r"Desiste|Paga|Call|All-?in|Shove|Jam|Raise|Aumenta|Over\s?bet|Overbet)\b", re.I)
PCT = re.compile(r"(\d{2,3})\s*%")
SECTIONS = [  # (regex do título no corpo, rótulo)
    (r"C-bet em posi", "cbet_ip"), (r"C-bet fora de posi", "cbet_oop"),
    (r"C-bet contra o small blind|C-bet vs small", "cbet_vs_sb"),
    (r"Float", "float"), (r"Bet vs missed c-bet|missed c-bet", "bet_vs_missed_cbet"),
    (r"Probe", "probe"), (r"Delayed c-bet", "delayed_cbet"),
    (r"Bet-check-bet", "bet_check_bet"), (r"Tr[eê]s barris|barris", "triple_barrel"),
    (r"Bluff catcher|Bluff-catcher", "bluff_catch"), (r"Squeeze", "squeeze"),
    (r"Blind war", "blind_war"), (r"Potes multiway|multiway", "multiway"),
    (r"Fundamentos", "fundamentos"),
]


def translit(s):
    for u, a in SUIT.items():
        s = s.replace(u, a)
    return s


def norm_action(line):
    m = ACTION.match(line)
    if not m:
        return None
    kw = m.group(1).lower().replace(" ", "").replace("-", "")
    pct = PCT.search(line)
    size = int(pct.group(1)) if pct else None
    if kw == "checkcall":
        return ("check_call", None)
    if kw == "checkfold":
        return ("check_fold", None)
    if kw == "aposta":
        return ("bet", size)
    if kw in ("overbet",):
        return ("bet", size or 125)
    if kw in ("check",):
        return ("check", None)
    if kw in ("checkraise",):
        return ("check_raise", size)
    if kw in ("checa",):
        return ("check", None)
    if kw in ("fold", "folda", "desiste"):
        return ("fold", None)
    if kw in ("call", "paga"):
        return ("call", None)
    if kw in ("allin", "shove", "jam"):
        return ("all_in", None)
    if kw in ("raise", "aumenta"):
        return ("raise", size)
    return None


def cards(line):
    return CARD.findall(line)


def main():
    raw = translit(open(SRC, encoding="utf-8").read())
    # remove marcadores de página; mantém o fluxo de linhas
    raw = re.sub(r"===== PAGINA \d+ =====", "", raw)
    lines = [ln.rstrip() for ln in raw.splitlines()]
    # índice de seção por posição de linha
    sec_at = {}
    for i, ln in enumerate(lines):
        for rx, lab in SECTIONS:
            if re.search(rx, ln, re.I) and len(ln.strip()) <= 60:
                sec_at[i] = lab
    def section_for(idx):
        cur = "?"
        for i in sorted(sec_at):
            if i <= idx:
                cur = sec_at[i]
            else:
                break
        return cur

    # CENÁRIO por sub-tabela: linha "Situação:" ou "SOLVER NNbb" (posição/stack/linha/rua).
    scen_at = {}
    SCEN = re.compile(r"(Situa[cç][aã]o\s*:|SOLVER\s*\d+\s*bb)", re.I)
    STK = re.compile(r"(\d+)\s*bb", re.I)
    for i, ln in enumerate(lines):
        if SCEN.search(ln) and len(ln) <= 140:
            scen_at[i] = ln.strip()

    def scenario_for(idx):
        cur = None
        for i in sorted(scen_at):
            if i <= idx:
                cur = scen_at[i]
            else:
                break
        return cur

    fixtures = []
    i = 0
    n = len(lines)
    while i < n:
        t = lines[i].strip()
        hm = HAND2.match(t)
        # ÂNCORA = linha-MÃO: começa com 2 cartas E tem EXATAMENTE 2 cartas (board tem >=3).
        if hm and len(cards(t)) == 2:
            hand, klass = cards(t)[:2], (t[hm.end():].strip() or None)
            # board ACIMA (1-2 linhas, >=3 cartas)
            board = None
            for up in range(1, 3):
                if i - up < 0:
                    break
                bc = cards(lines[i - up].strip())
                if len(bc) >= 3:
                    board = bc[:5]
                    break
            # AÇÃO ABAIXO (1-4 linhas; pula linhas de classe "Você tem")
            act = ai = None
            for off in range(1, 5):
                if i + off >= n:
                    break
                a = norm_action(lines[i + off].strip())
                if a:
                    act, ai = a, i + off
                    break
            if board and act:
                note = lines[ai + 1].strip() if ai + 1 < n else ""
                scen = scenario_for(i)
                mstk = STK.search(scen or "")
                street = ("RIVER" if len(board) >= 5 else "TURN" if len(board) == 4 else "FLOP")
                fixtures.append(dict(section=section_for(i), scenario=scen,
                                     stack_bb=(int(mstk.group(1)) if mstk else None), street=street,
                                     board=board, hand=hand, hand_class=klass,
                                     action=act[0], size_pct=act[1], note=note[:120]))
                i = ai + 1
                continue
        i += 1
    fails = 0
    json.dump(fixtures, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    # relatório
    import collections
    by_sec = collections.Counter(f["section"] for f in fixtures)
    by_act = collections.Counter(f["action"] for f in fixtures)
    print("EXEMPLOS parseados: %d  (falhas de bloco: %d)" % (len(fixtures), fails))
    print("por AÇÃO:", dict(by_act))
    print("por SEÇÃO:", dict(by_sec.most_common()))
    print("--- amostra ---")
    for f in fixtures[:3] + fixtures[len(fixtures) // 2: len(fixtures) // 2 + 2]:
        print(" ", f["section"], f["board"], f["hand"], "->", f["action"], f["size_pct"], "|", (f["hand_class"] or "")[:30])
    print("salvo:", OUT)


if __name__ == "__main__":
    main()
