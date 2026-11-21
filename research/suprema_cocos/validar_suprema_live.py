"""VALIDACAO AO VIVO (dry-run, read-only) do pipeline de REDE da Suprema: roda o run_live
real (hook SSL_read -> JsonFrameExtractor -> SupremaTable) e DUMPA o estado cru lido, p/
confirmar que a percepcao bate com a mesa. NENHUM clique. Imprime quando ha novidade
(board muda, heroi conhecido, ou e a vez). Deriva bb dos blinds p/ mostrar bb tambem."""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    import suprema_net
    last = {"sig": None}

    def on_state(table):
        # assinatura p/ throttle: board + vez + cartas do heroi
        hero = table.hero_seat
        hcards = (table.players.get(hero) or {}).get('cards') if hero else None
        legal = sorted(table.legal_actions())
        sig = (tuple(table.board), tuple(sorted((s, p.get('coins'), p.get('chips'))
                                                for s, p in table.players.items())),
               hero, tuple(hcards or []), tuple(legal))
        if sig == last["sig"]:
            return
        last["sig"] = sig
        seats = []
        for s in sorted(table.players):
            p = table.players[s]
            tag = ' <HERO' + str(p.get('cards')) + '>' if s == hero else ''
            seats.append("s%s(coins=%s chips=%s)%s" % (s, p.get('coins'), p.get('chips'), tag))
        print("[LIVE] dealer=%s board=%s | %s | vez=%s" % (
            table.dealer_seat, table.board, ' '.join(seats), legal or '-'), flush=True)

    print("[validar] dry-run ao vivo; nenhum clique. Jogue; eu mostro o que estou LENDO.", flush=True)
    suprema_net.run_live(bb_chips=1, on_state=on_state, seconds=80)   # bb=1 -> mostra fichas cruas
    print("[validar] fim.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
