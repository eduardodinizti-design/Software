"""Gravador de histórico das mãos que NÓS jogamos — banco de dados para estudo.

Grava, por mão: hand_id, mesa, contexto de torneio, hero (posição/cartas/stack), os
ADVERSÁRIOS por id (nick do nameplate) com stack/posição/HUD, a LINHA de cada rua
(ações de todos), o board, o RASTRO de conselhos do cérebro (recomendado/fonte/EV) e o
RESULTADO. Append-only em JSONL (`logs/maos/maos.jsonl`), análogo ao shadow_mode.

PURO: não captura tela nem clica. Recebe o que o observador/operador reporta e grava.
Objetivo: montar um banco para depois estudar linhas (menos-EV a corrigir, lucrativas a
explorar), adversários (id) e spots. A análise vive em `hand_db.py`.

Uso ao vivo (observação, nunca executa):
    rec = HandRecorder()
    h = rec.begin(hand_id=..., table_key=..., tournament=..., hero=..., opponents=[...])
    h.action(street='preflop', actor='BTN', action='raise', amount_bb=2.0, player_id='hero')
    h.board('flop', ['As','7d','2c'])
    h.advice(street='flop', recommended='bet', source='solver_shadow', ev_bb=None, ...)
    h.result(outcome='won', delta_bb=5.5, showdown={...})
    rec.commit(h)        # grava a mão fechada no JSONL
"""
import json
import os
from datetime import datetime, timezone

DEFAULT_LOG = os.path.join('logs', 'maos', 'maos.jsonl')

_STREETS = ('preflop', 'flop', 'turn', 'river')
_COMMIT_ACTIONS = ('bet', 'raise', 'call', 'all_in')
_OUTCOMES = ('won', 'lost', 'folded', 'chopped', 'unknown')


def _now():
    return datetime.now(timezone.utc).isoformat()


class HandInProgress:
    """Acumulador de UMA mão. Imutável por fora; preenchido pelos métodos do observador."""

    def __init__(self, *, hand_id, table_key=None, tournament=None, hero=None,
                 opponents=None, ts=None):
        self.rec = dict(
            hand_id=hand_id, ts=ts or _now(), table_key=table_key,
            tournament=dict(tournament or {}),
            hero=dict(hero or {}),
            opponents=[dict(o) for o in (opponents or [])],
            streets={s: dict(board=[], actions=[]) for s in _STREETS},
            advice_trail=[],
            result=dict(outcome='unknown', delta_bb=None, showdown=None),
        )

    # -- preenchimento incremental (tudo tolerante a campos ausentes) --
    def action(self, *, street, actor, action, amount_bb=None, player_id=None):
        if street in self.rec['streets']:
            self.rec['streets'][street]['actions'].append(
                dict(actor=actor, action=str(action).lower(), amount_bb=amount_bb,
                     player_id=player_id))
        return self

    def board(self, street, cards):
        if street in self.rec['streets'] and cards:
            self.rec['streets'][street]['board'] = list(cards)
        return self

    def advice(self, *, street, recommended=None, source=None, ev_bb=None,
               validated=None, mix=None, spot=None, execution_allowed=False, **extra):
        self.rec['advice_trail'].append(dict(
            street=street, recommended=recommended, source=source, ev_bb=ev_bb,
            validated=validated, mix=mix, spot=spot,
            execution_allowed=bool(execution_allowed), **extra))
        return self

    def opponent(self, **fields):
        self.rec['opponents'].append(dict(fields))
        return self

    def result(self, *, outcome='unknown', delta_bb=None, showdown=None):
        self.rec['result'] = dict(outcome=outcome if outcome in _OUTCOMES else 'unknown',
                                  delta_bb=delta_bb, showdown=showdown)
        return self

    # -- derivados úteis para estudo, calculados no fechamento --
    def _finalize(self):
        r = self.rec
        hero_seat = (r['hero'] or {}).get('seat')
        hero_pos = (r['hero'] or {}).get('position')
        # Linha do hero: sequência de ações do hero por rua (p/ agrupar linhas no estudo).
        line = []
        last_street = 'preflop'
        for s in _STREETS:
            for a in r['streets'][s]['actions']:
                if a.get('player_id') == 'hero' or a.get('actor') in (hero_seat, hero_pos, 'hero'):
                    line.append('%s:%s%s' % (s[:2], a['action'],
                                             ('' if a.get('amount_bb') is None else ':%g' % a['amount_bb'])))
                    last_street = s
        r['hero_line'] = line
        r['reached_street'] = last_street
        r['opponent_ids'] = [o.get('id') for o in r['opponents'] if o.get('id')]
        # Rótulo de linha canônico (p/ agregações): posição + ações do hero, sem valores.
        r['line_key'] = '%s|%s' % (hero_pos or '?',
                                   '>'.join(s.split(':', 1)[0] + ':' + s.split(':')[1]
                                            for s in (x.rsplit(':', 1)[0] if x.count(':') > 1 else x
                                                      for x in line))) if line else (hero_pos or '?')
        return r


class HandRecorder:
    """Grava mãos fechadas em JSONL (append-only, com rotação por tamanho)."""

    def __init__(self, path=DEFAULT_LOG, *, max_bytes=100_000_000, backups=3, sink=None):
        self.path = path
        self.max_bytes = int(max_bytes) if max_bytes else 0
        self.backups = max(1, int(backups))
        self._sink = sink

    def begin(self, **kw):
        return HandInProgress(**kw)

    def _rotate_if_needed(self):
        if not (self.max_bytes and self.path) or not os.path.exists(self.path):
            return
        try:
            if os.path.getsize(self.path) < self.max_bytes:
                return
        except OSError:
            return
        for i in range(self.backups, 0, -1):
            src = self.path if i == 1 else '%s.%d' % (self.path, i - 1)
            dst = '%s.%d' % (self.path, i)
            if os.path.exists(src):
                try:
                    os.replace(src, dst)
                except OSError:
                    pass

    def commit(self, hand):
        """Fecha e grava a mão. Devolve o registro final."""
        rec = hand._finalize() if isinstance(hand, HandInProgress) else dict(hand)
        if self.path:
            d = os.path.dirname(self.path)
            if d:
                os.makedirs(d, exist_ok=True)
            self._rotate_if_needed()
            with open(self.path, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
        if self._sink:
            try:
                self._sink(rec)
            except Exception:                            # noqa: BLE001
                pass
        return rec


def load_hands(path=DEFAULT_LOG):
    """Lê todas as mãos gravadas (lista de dicts). Tolerante a linhas corrompidas."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding='utf-8') as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    return out
