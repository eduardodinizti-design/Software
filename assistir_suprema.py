"""OBSERVADOR (dry-run) da SUPREMA: amarra percepcao->cerebro->plano e MOSTRA o que o bot
FARIA, sem clicar nada. Pronto p/ a micro-sessao de validacao ao vivo (so rodar com o
cliente aberto). READ-ONLY.

Uso:
    python -I assistir_suprema.py --bb 500                 # dry-run ao vivo (90s default)
    python -I assistir_suprema.py --bb 500 --seconds 120
    python -I assistir_suprema.py --selftest               # valida a logica OFFLINE (sem Frida)

O --bb e a stake da mesa em FICHAS (o BB). A camada de CLIQUE (overlay/botoes) NAO esta aqui:
isto so DECIDE e imprime (dry-run). Ver SUPREMA_PROTOCOL.md / nvt-multisite-expansion.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # robusto sob `python -I`

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PACK = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'


def load_advisor():
    from preflop_advisor import PreflopAdvisor
    return (PreflopAdvisor.from_files(PACK, DEEP) if os.path.exists(DEEP)
            else PreflopAdvisor.from_file(PACK))


def decide_and_plan(table, advisor, *, mode='chip_ev', stage='mid'):
    """Núcleo testável: do SupremaTable vivo -> (state|None, advice, plano). NÃO clica."""
    from suprema_state import advise_from_suprema
    import suprema_act
    state, hero = table.to_table_state()
    if state is None:
        return None, dict(status='ABSTAIN', reason=hero), dict(action=suprema_act.ABSTAIN,
                                                               reason=hero)
    advice = advise_from_suprema(table, advisor, mode=mode, stage=stage)
    plan = suprema_act.plan_action(advice, table)
    return state, advice, plan


def _fmt(state, advice, plan, hero):
    pos = (state or {}).get('positions', {}).get('hero', '?')
    board = (state or {}).get('board', [])
    tocall = (state or {}).get('to_call', {}).get('to_call_bb')
    legal = (state or {}).get('legal_actions', [])
    return ("[SUPREMA] pos=%s hero=%s board=%s to_call=%sbb | CEREBRO=%s(%s) -> PLANO=%s %s%s | legal=%s"
            % (pos, hero, board, tocall, advice.get('recommended'), advice.get('status'),
               plan.get('action'),
               (('%s' % plan['chips']) if plan.get('chips') is not None else ''),
               ((' [%s]' % plan['preset']) if plan.get('preset') else ''), legal))


def run_live(bb, seconds, mode, stage):
    import suprema_net
    advisor = load_advisor()
    last = {"turn": False}

    def on_state(table):
        legal = table.legal_actions()
        is_turn = bool(legal)
        # so imprime quando MUDA p/ "minha vez" (evita flood dos pushes de estado)
        if is_turn and not last["turn"]:
            state, advice, plan = decide_and_plan(table, advisor, mode=mode, stage=stage)
            hero = (table.players.get(table.hero_seat) or {}).get('cards') if table.hero_seat else None
            print(_fmt(state, advice, plan, hero), flush=True)
        last["turn"] = is_turn

    print("[assistir_suprema] dry-run; nenhum clique. Jogue; eu mostro o PLANO na sua vez.", flush=True)
    suprema_net.run_live(bb_chips=bb, on_state=on_state, seconds=seconds)
    print("[assistir_suprema] fim.", flush=True)


def selftest():
    """Valida a logica OFFLINE (sem Frida): injeta eventos de uma mao e checa o plano."""
    from suprema_state import SupremaTable
    import suprema_act
    advisor = load_advisor()
    t = SupremaTable(bb_chips=500)
    t.feed_json({"event": "gameinfo", "data": {"game_info": {
        "dealer_seat": 2, "shared_cards": [], "pot": 750, "state": 3}}})
    t.feed_json({"event": "moveturn", "data": {"game_seat": {
        "1": {"seat": 2, "coins": 10000, "cards": [59, 56], "chips": 0, "sitout": False},
        "2": {"seat": 3, "coins": 9000, "cards": None, "chips": 250, "sitout": False},
        "3": {"seat": 6, "coins": 12000, "cards": [0, 0], "chips": 500, "sitout": False}}}})
    t.feed_json({"event": "prompt", "data": {"gamer_prompt": {
        "fold": True, "check": None, "call": 500,
        "raise": "range,1000,10000,2X,1000,3X,1500", "all_in": True}}})
    state, advice, plan = decide_and_plan(t, advisor)
    hero = t.players[t.hero_seat]['cards']
    print(_fmt(state, advice, plan, hero), flush=True)
    assert state is not None, "deveria ter estado"
    assert advice.get('status') == 'ADVICE', advice
    assert plan['action'] in (suprema_act.RAISE, suprema_act.ALL_IN, suprema_act.CALL), plan
    print("[selftest] OK — AA no BTN com prompt ativo gerou plano:", plan['action'])
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bb", type=float, default=None, help="BB em fichas (stake da mesa)")
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--mode", default="chip_ev")
    ap.add_argument("--stage", default="mid")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.bb:
        print("Informe --bb (BB em fichas da mesa) p/ o dry-run ao vivo, ou --selftest.")
        return 2
    run_live(args.bb, args.seconds, args.mode, args.stage)
    return 0


if __name__ == "__main__":
    sys.exit(main())
