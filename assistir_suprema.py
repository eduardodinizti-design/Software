"""OBSERVADOR (dry-run) da SUPREMA: amarra percepcao->cerebro->plano e MOSTRA o que o Henrique
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
# RANGES DO EDUARDO (AUTORIDADE, ordem direta 24/11): as ranges transcritas do Eduardo
# (GTOWizard) carregam PRIMEIRO -> na colisão de chave (B02, from_files strict=False) o 1º
# vence, então a range do Eduardo SOBREPÕE o solve GTO onde ela cobre (RFI por posição + blind
# war). O Henrique joga a ESTRATÉGIA DO EDUARDO, não o GTO que inventava flats.
EDUARDO = r'C:\Meus Projetos\Aplicativos\nvt-ranges-eduardo.json'


def load_advisor():
    from preflop_advisor import PreflopAdvisor
    packs = [p for p in (EDUARDO, PACK, DEEP) if os.path.exists(p)]
    return (PreflopAdvisor.from_files(*packs) if len(packs) > 1
            else PreflopAdvisor.from_file(packs[0]))


def decide_and_plan(table, advisor, *, mode='chip_ev', stage='mid', hunt_bounty=False,
                    head_fraction=0.5, starting_stack=None):
    """Núcleo testável: do SupremaTable vivo -> (state|None, advice, plano). NÃO clica.
    `hunt_bounty` liga a caça de bounty PKO AUTO (injeta a cabeça por vilão no call-off)."""
    from suprema_state import advise_from_suprema
    import suprema_act
    state, hero = table.to_table_state()
    if state is None:
        return None, dict(status='ABSTAIN', reason=hero), dict(action=suprema_act.ABSTAIN,
                                                               reason=hero)
    advice = advise_from_suprema(table, advisor, mode=mode, stage=stage, hunt_bounty=hunt_bounty,
                                 head_fraction=head_fraction, starting_stack=starting_stack)
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


class _SpotGate:
    """Trava ANTI-FLICKER da vez do herói. Só libera DECISÃO quando a MESMA leitura
    (board, posição, ações legais, to_call) aparece em STABLE_FRAMES eventos SEGUIDOS —
    assim um flicker de 1 frame (to_call 1.0->0.0, posição que desliza, board parcial)
    NUNCA dispara ação. Se a vez PERSISTE sem estabilizar (UNSTABLE_AT frames), devolve
    'unstable' UMA vez (nunca abstém calado). `reset()` quando não é a vez do herói."""
    STABLE_FRAMES = 1     # DECIDE na 1ª leitura válida (velocidade; anti-thrash evita re-clique)
    UNSTABLE_AT = 3

    def __init__(self):
        self._decided = None     # PERSISTE entre flickers/empties -> não re-clica o mesmo spot (bug AK 3x)
        self.reset()

    def reset(self):
        self._cand = None
        self._n = 0
        self._frames = 0
        self._warned = False
        # NÃO limpa self._decided: legal_actions pisca vazio entre eventos -> resetar o _decided
        # fazia re-decidir o MESMO spot -> re-clicar (AK tentou 3x o raise). Com hand_id na sig,
        # mão nova re-decide (sig != _decided) e o mesmo spot não re-dispara.

    def offer(self, sig):
        """Devolve 'decide' | 'wait' | 'unstable' para a leitura `sig` do evento atual."""
        self._frames += 1
        if sig == self._cand:
            self._n += 1
        else:
            self._cand, self._n = sig, 1
        if self._n >= self.STABLE_FRAMES and sig != self._decided:
            self._decided, self._warned = sig, False
            return 'decide'
        if self._decided is None and self._frames >= self.UNSTABLE_AT and not self._warned:
            self._warned = True
            return 'unstable'
        return 'wait'


def _spot_sig(state):
    """Assinatura do spot p/ a trava. Normaliza 'bet'<->'raise' (mesma ação agressiva: só
    muda o rótulo conforme haja ou não aposta a pagar) p/ não contar isso como instabilidade;
    o to_call ENTRA (mudar de call p/ check é instabilidade REAL que troca a jogada)."""
    legal = set(state.get('legal_actions', []))
    if 'bet' in legal:
        legal = (legal - {'bet'}) | {'raise'}
    return (state.get('hand_id'), tuple(state.get('board', [])),
            state.get('positions', {}).get('hero'),
            tuple(sorted(legal)), (state.get('to_call') or {}).get('to_call_bb'))


def make_on_state(advisor, *, mode='chip_ev', stage='mid', emit=None, stats=None,
                  hunt_bounty=False, head_fraction=0.5, starting_stack=None):
    """Fábrica do callback `on_state` de CONSELHO (dry-run), reutilizável por quem já tem um
    SupremaTable vivo (assistir OU o capturador unificado). Decide 1x por spot ESTÁVEL da vez
    do herói (trava anti-flicker _SpotGate), chamando `emit(state, advice, plan, hero)`.
    Default emit = imprime a linha _fmt. NÃO clica."""
    gate = _SpotGate()
    stats = stats if stats is not None else {"decisao": 0}

    def _emit(state, advice, plan, hero):
        if emit is not None:
            emit(state, advice, plan, hero)
        else:
            print(_fmt(state, advice, plan, hero), flush=True)

    def on_state(table):
        # FIX (21/11): as cartas do herói chegam DENTRO do prompt, às vezes depois do 1º push
        # da vez; decidir na transição crua abstinha. Agora espera RESOLVER e decide 1x por
        # spot. FIX (21/11 #2): a leitura ainda FLICKA na vez (to_call 1.0<->0.0, posição que
        # desliza, board parcial, raise<->bet) e isso chegou a TROCAR a jogada (call->check).
        # Trava: só decide quando a MESMA leitura se repete; se oscila, ABSTÉM e avisa.
        if not table.legal_actions():
            gate.reset()
            return
        state, reason = table.to_table_state()
        if state is None:
            return                       # ainda sem herói; espera o prompt trazer as cartas
        verdict = gate.offer(_spot_sig(state))
        if verdict == 'decide':
            _, advice, plan = decide_and_plan(table, advisor, mode=mode, stage=stage,
                                              hunt_bounty=hunt_bounty, head_fraction=head_fraction,
                                              starting_stack=starting_stack)
            stats["decisao"] = stats.get("decisao", 0) + 1
            # hero = o 2º retorno do to_table_state (consistente com `state`); a re-busca em
            # players[hero_seat] às vezes vinha None (hero=None nos logs pós-flop). `reason`
            # carrega as cartas do herói quando state != None.
            _emit(state, advice, plan, reason)
        elif verdict == 'unstable':
            stats["instavel"] = stats.get("instavel", 0) + 1
            print("[SUPREMA] SPOT INSTÁVEL na sua vez — leitura oscilando, ABSTENDO (nenhum "
                  "clique). board=%s pos=%s legal=%s to_call=%sbb"
                  % (state.get('board'), state.get('positions', {}).get('hero'),
                     sorted(state.get('legal_actions', [])),
                     (state.get('to_call') or {}).get('to_call_bb')), flush=True)

    return on_state


def run_live(bb, seconds, mode, stage):
    import suprema_net
    advisor = load_advisor()
    stats = {"decisao": 0}
    on_state = make_on_state(advisor, mode=mode, stage=stage, stats=stats)
    print("[assistir_suprema] dry-run; nenhum clique. Jogue; eu mostro o PLANO na sua vez.", flush=True)
    suprema_net.run_live(bb_chips=bb, on_state=on_state, seconds=seconds)
    print("[assistir_suprema] fim. decisões=%d" % stats["decisao"], flush=True)


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
