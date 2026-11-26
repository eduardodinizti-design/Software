"""Replay OFFLINE da percepção por DADOS (protobuf) do PPPoker — READ-ONLY, sem cliente, sem clique.

Roda capturas reais do estado (estado_mesa*.json, emitidas por research/ppp_il2cpp/emitir_seats.*
a partir da memória do PPPoker via Frida/IL2CPP) pelo MESMO cérebro compartilhado
(protobuf_state.advise_from_protobuf -> preflop/postflop_advisor + ranges), e imprime a decisão
por mesa. É a PROVA OFFLINE da cadeia dados->cérebro->decisão do PPPoker: cartas/apostas/posições
vêm EXATAS da memória (não OCR), então acaba a classe de erro "leu a ação/carta errada".

Fundação do agente de produção (pppoker_agente, nos moldes do suprema_agente): o laço vivo e a
execução entram depois; aqui validamos a DECISÃO contra capturas reais, offline.

Uso:
  python pppoker_replay.py [captura.json ...]     # sem args: usa a captura de exemplo do repo
"""
from __future__ import annotations

import argparse
import json
import os

import protobuf_state as PB
from ppp_cards import decode_cards

DEFAULT_CAPTURE = os.path.join('research', 'ppp_il2cpp', 'estado_mesa_multitable_20261120.json')


def load_capture(path):
    """Lê uma captura estado_mesa*.json -> lista de (table_key, entry). Tolerante: aceita o dict
    multitable {table_key: entry}, uma única entry {players:...}, ou uma lista de entries."""
    with open(path, encoding='utf-8') as fh:
        d = json.load(fh)
    if isinstance(d, dict) and 'players' in d:
        return [(str(d.get('room') or 'mesa'), d)]
    if isinstance(d, dict):
        return [(str(k), v) for k, v in d.items() if isinstance(v, dict) and 'players' in v]
    if isinstance(d, list):
        return [(str(i), v) for i, v in enumerate(d) if isinstance(v, dict) and 'players' in v]
    return []


def _bb(x, bb):
    return round(x / bb, 2) if isinstance(x, (int, float)) and bb else None


def _hero_str(hero):
    """hero pode vir como ['Ah','Kd'] (já decodificado) ou [ints]. Normaliza p/ strings."""
    if not hero:
        return None
    if all(isinstance(c, int) for c in hero):
        return decode_cards(hero)
    return list(hero)


def decide_entry(table_key, entry, advisor, **kwargs):
    """Roda UMA mesa pelo cérebro via protobuf e devolve o dict de decisão (p/ exibir/testar).
    Campos: table, bb_chips, pos, hero, board, pot_bb, to_call_bb, status, recommended, size, reason.
    Nunca lança: erro de leitura/decisão vira status=ABSTAIN com o motivo."""
    table = (entry or {}).get('table') or {}
    bb = PB.bb_chips(table)
    out = dict(table=table_key, bb_chips=bb, board=decode_cards(table.get('board') or []),
               pot_bb=_bb(table.get('pot'), bb), to_call_bb=_bb(table.get('tocall'), bb),
               pos=None, hero=None, status=None, recommended=None, size=None, reason=None)
    try:
        state, hero_or_reason = PB.build_table_state(entry)
    except Exception as e:  # leitura nunca derruba o replay
        return dict(out, status='ABSTAIN', reason='BUILD_ERRO:%s' % e)
    if state is None:
        return dict(out, status='ABSTAIN', reason=hero_or_reason)
    out['hero'] = _hero_str(hero_or_reason)
    out['pos'] = (state.get('positions') or {}).get('hero')
    try:
        adv = PB.advise_from_protobuf(entry, advisor, **kwargs) or {}
    except Exception as e:
        return dict(out, status='ABSTAIN', reason='ADVISE_ERRO:%s' % e)
    sz = adv.get('sizing') or {}
    return dict(out, status=adv.get('status'), recommended=adv.get('recommended'),
                size=sz.get('size_bb') or sz.get('multiplier'), bucket=sz.get('bucket'),
                reason=adv.get('reason') or adv.get('note'))


def format_line(d):
    sz = ('' if d.get('size') is None else ' %s' % d['size'])
    extra = ('' if not d.get('reason') else '  (%s)' % d['reason'])
    return ("[PPP %s] pos=%s hero=%s board=%s pot=%sbb to_call=%sbb -> %s%s%s"
            % (d.get('table'), d.get('pos'), d.get('hero'), d.get('board'),
               d.get('pot_bb'), d.get('to_call_bb'),
               d.get('recommended') or d.get('status'), sz, extra))


def replay(entries, advisor, **kwargs):
    return [decide_entry(k, e, advisor, **kwargs) for k, e in entries]


def _load_advisor():
    """Cérebro compartilhado (mesmos packs da Suprema/PPPoker). Mantém a fonte da verdade única."""
    from assistir_suprema import load_advisor
    return load_advisor()


def main(argv=None):
    ap = argparse.ArgumentParser(description='Replay offline da percepção protobuf do PPPoker (read-only).')
    ap.add_argument('captures', nargs='*', default=[DEFAULT_CAPTURE],
                    help='arquivos estado_mesa*.json (default: captura de exemplo do repo)')
    ap.add_argument('--mode', default='chip_ev')
    ap.add_argument('--stage', default='mid')
    args = ap.parse_args(argv)
    advisor = _load_advisor()
    total = 0
    for path in args.captures:
        if not os.path.exists(path):
            print('(captura ausente: %s)' % path)
            continue
        entries = load_capture(path)
        print('== %s: %d mesa(s) ==' % (path, len(entries)))
        for d in replay(entries, advisor, mode=args.mode, stage=args.stage):
            print('  ' + format_line(d))
            total += 1
    print('total de mesas decididas: %d' % total)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
