"""BASELINE do Henrique vs o guia — seções de LEAD (hero decide BET vs CHECK, to_call=0):
c-bet IP/OOP/vs SB, delayed c-bet, probe, bet-check-bet. Estado JUSTO por seção (posição/aggressor/
rua), sem olhar a resposta. Compara a ação IMEDIATA: guia bet/all_in/raise -> BET; resto -> CHECK."""
from __future__ import annotations
import collections
import json
import sys

REPO = r"C:\Meus Projetos\Aplicativos\_repo_software"
sys.path.insert(0, REPO)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from postflop_advisor import advise_postflop   # noqa: E402

FX = REPO + r"\fixtures\guia_posflop_fixtures.json"
LEAD = {
    "cbet_ip":       dict(hero="BTN", vill="BB", agg="hero"),
    "cbet_vs_sb":    dict(hero="BTN", vill="SB", agg="hero"),
    "cbet_oop":      dict(hero="CO",  vill="BTN", agg="hero"),
    "delayed_cbet":  dict(hero="BTN", vill="BB", agg="hero", vline="delayed"),
    "probe":         dict(hero="BB",  vill="BTN", agg=None, vline="checked_back"),
    "bet_check_bet": dict(hero="BTN", vill="BB", agg="hero", vline="checked_turn"),
}
POT = {"FLOP": 4.5, "TURN": 11.0, "RIVER": 22.0}


def stack_of(fx):
    s = fx.get("scenario") or ""
    return 25 if "25bb" in s else 40


def build_state(fx, cfg):
    stk = stack_of(fx)
    h, v = cfg["hero"], cfg["vill"]
    return dict(
        positions={"hero": h, "vill": v},
        seats={"hero": {"stack_bb": stk, "occupied": True},
               "vill": {"stack_bb": stk, "occupied": True}},
        bets=[{"seat": "hero", "bet_bb": 0.0}, {"seat": "vill", "bet_bb": 0.0}],
        board=fx["board"], street=fx["street"],
        to_call={"to_call_bb": 0.0}, pot={"pot_bb": POT.get(fx["street"], 6.0)},
        legal_actions=["check", "bet"],
    )


def guide_imm(a):
    return "BET" if a in ("bet", "raise", "all_in") else "CHECK"


def adv_imm(adv):
    if not isinstance(adv, dict) or adv.get("status") != "ADVICE":
        return "ABSTAIN"
    return "BET" if adv.get("recommended") in ("bet", "raise", "all_in") else "CHECK"


def main():
    F = json.load(open(FX, encoding="utf-8"))
    tot_match = tot = 0
    print("=== BASELINE — eixo de APOSTA (lead: bet vs check) ===")
    for sec, cfg in LEAD.items():
        fx = [x for x in F if x["section"] == sec]
        if not fx:
            continue
        m = ab = 0
        conf = collections.Counter()
        for x in fx:
            st = build_state(x, cfg)
            try:
                adv = advise_postflop(st, x["hand"], x["board"], street=x["street"],
                                      mode="chip_ev", stage="mid", aggressor=cfg["agg"],
                                      villain_line=cfg.get("vline"))
            except Exception:
                adv = {"status": "ERROR"}
            g, a = guide_imm(x["action"]), adv_imm(adv)
            conf[(g, a)] += 1
            if a == "ABSTAIN":
                ab += 1
            elif g == a:
                m += 1
        n = len(fx)
        tot_match += m
        tot += n
        extra = (" | abstém %d" % ab) if ab else ""
        print("  %-14s %3d/%3d = %5.1f%%%s   %s" % (
            sec, m, n, 100.0 * m / n, extra,
            {("%s->%s" % k): v for k, v in conf.most_common()}))
    print("  " + "-" * 60)
    print("  %-14s %3d/%3d = %5.1f%%  (eixo de aposta, %d exemplos)" % (
        "TOTAL", tot_match, tot, 100.0 * tot_match / tot, tot))


if __name__ == "__main__":
    main()
