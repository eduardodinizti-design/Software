"""Shadow Mode / Monitoring — compara, em tempo real, a DECISÃO do bot com o range
ideal do solver (GTO) e sinaliza quando o 'Cérebro' sai dos trilhos na sessão.

Para cada decisão na vez do hero, registra um DecisionRecord (spot, nó, sugestão
GTO = ação recomendada do nó validado, ação de fato tomada, autoridade do B04) e
classifica a disparidade. Acumula um sinal rolante de saúde da sessão. Append-only
em JSONL (`logs/shadow/decisoes.jsonl`) p/ o componente de Auditoria ler.

Veredito:
  segue_gto          nó validado + ação == recomendada (segue o solver).
  desvio_seguro      ação != recomendada, mas é piso de segurança (fold/check de
                     autoridade SAFETY_*/call-off) — desvio conhecido, sem risco.
  fora_dos_trilhos   COMPROMETEU ficha (call/raise/all_in) contra a recomendação
                     validada, OU sem nó validado -> o motor saiu dos trilhos.
  sem_no             abstenção / sem nó / sem ação.

PURO: não captura tela nem clica; só recebe o que o operador reporta e grava.
"""
import json
import os
import re
from collections import deque
from datetime import datetime, timezone

DEFAULT_LOG = os.path.join('logs', 'shadow', 'decisoes.jsonl')

_COMMIT = ('call', 'raise', 'bet', 'all_in')
_NONCOMMIT = ('fold', 'check')


def classify_decision(rec):
    """Veredito da disparidade bot×GTO (ver módulo). Usa gto_recommended (sugestão
    do nó), bot_action (executada), validated e authority."""
    gto = (rec.get('gto_recommended') or '').lower() or None
    act = (rec.get('bot_action') or '').lower() or None
    authority = (rec.get('authority') or '').upper()
    if act is None:
        return 'sem_no'
    if rec.get('validated') and gto is not None:
        if act == gto or (gto in ('raise', 'bet', 'all_in') and act in ('raise', 'all_in', 'bet')):
            return 'segue_gto'
        # Ação difere da recomendação validada.
        if act in _NONCOMMIT and authority.startswith('SAFETY'):
            return 'desvio_seguro'
        return 'fora_dos_trilhos'                       # desviou comprometendo/validado
    # Sem nó validado:
    if act in _COMMIT and authority not in ('VALIDATED', 'CALL_OFF'):
        return 'fora_dos_trilhos'                       # comprometeu ficha sem respaldo GTO
    if act in _NONCOMMIT:
        return 'desvio_seguro'                          # piso seguro sem nó
    return 'sem_no'


def make_record(*, frame=None, table=None, hero_cards=None, position=None,
                stack_bb=None, to_call_bb=None, spot=None, node_id=None,
                validated=None, gto_status=None, gto_recommended=None,
                bot_action=None, authority=None, result_state=None, ts=None):
    rec = dict(ts=ts or datetime.now(timezone.utc).isoformat(), frame=frame, table=table,
               hero_cards=hero_cards, position=position, stack_bb=stack_bb,
               to_call_bb=to_call_bb, spot=spot, node_id=node_id, validated=validated,
               gto_status=gto_status, gto_recommended=gto_recommended,
               bot_action=bot_action, authority=authority, result_state=result_state)
    rec['verdict'] = classify_decision(rec)
    return rec


class ShadowMonitor:
    """Monitor em tempo real: grava cada decisão e mantém um sinal rolante de saúde
    (quantos 'fora_dos_trilhos' nas últimas `window` decisões)."""

    def __init__(self, path=DEFAULT_LOG, *, window=20, warn=2, off=4, sink=None,
                 max_bytes=50_000_000, backups=2):
        self.path = path
        self._recent = deque(maxlen=window)
        self.warn, self.off = warn, off
        self._sink = sink                              # callable(record) opcional (overlay/print)
        # D16: rotação por tamanho p/ o jsonl não crescer sem limite em sessões de horas.
        self.max_bytes = int(max_bytes) if max_bytes else 0
        self.backups = max(1, int(backups))

    def _rotate_if_needed(self):
        """Rotaciona o jsonl quando passa de max_bytes: path -> path.1 -> ... -> path.N
        (o mais antigo é descartado). Nunca levanta: rotação é best-effort."""
        if not (self.max_bytes and self.path) or not os.path.exists(self.path):
            return
        try:
            if os.path.getsize(self.path) < self.max_bytes:
                return
        except OSError:
            return
        for i in range(self.backups, 0, -1):          # do mais antigo p/ o mais novo
            src = self.path if i == 1 else '%s.%d' % (self.path, i - 1)
            dst = '%s.%d' % (self.path, i)
            if os.path.exists(src):
                try:
                    os.replace(src, dst)              # sobrescreve o backup mais antigo
                except OSError:
                    pass

    def observe(self, **fields):
        """Registra UMA decisão (campos de make_record). Grava no JSONL, atualiza o
        rolante e devolve (record, health)."""
        rec = make_record(**fields)
        if self.path:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            self._rotate_if_needed()
            with open(self.path, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
        self._recent.append(rec['verdict'])
        if self._sink:
            try:
                self._sink(rec)
            except Exception:                          # noqa: BLE001
                pass
        return rec, self.health()

    def health(self):
        """{status, off_rails, deviations, window, recent}. status: on_rails|warning|off_rails."""
        off = sum(v == 'fora_dos_trilhos' for v in self._recent)
        dev = sum(v in ('fora_dos_trilhos', 'desvio_seguro') for v in self._recent)
        status = 'off_rails' if off >= self.off else ('warning' if off >= self.warn else 'on_rails')
        return dict(status=status, off_rails=off, deviations=dev,
                    window=len(self._recent), recent=list(self._recent))


def load_recent(path=DEFAULT_LOG, n=10):
    """Últimas `n` decisões do JSONL (mais recente por último)."""
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    return rows[-n:]


# --------- backfill: extrai decisões do log de stdout do operador ---------
_CEREBRO = re.compile(
    r"\[(?P<frame>\d+)\] CEREBRO m(?P<table>\S+) hero=(?P<hero>\[[^\]]*\]|None) "
    r"pos=(?P<pos>\S+) to_call=(?P<tocall>\S+) bets=.*? \| spot=(?P<spot>\S+) "
    r"node=(?P<node>\S+) val=(?P<val>\S+) eq=\S+ req=\S+ -> (?P<status>\w+) (?P<tail>.*)")
_AGIU = re.compile(r"\[(?P<frame>\d+)\] >>> AGIU: (?P<action>\w+) .*?autoridade=(?P<auth>\w+) estado=(?P<state>\w+)")
_RAISE = re.compile(r"\[(?P<frame>\d+)\] >>> RAISE sequencia: preset (?P<preset>\S+) confirmado=(?P<ok>\w+)")
_FALL = re.compile(r"\[(?P<frame>\d+)\] >>> FALLBACK anti-freeze: (?P<action>\w+) \| autoridade=(?P<auth>\w+)")


def _bool(s):
    return {'true': True, 'false': False}.get(str(s).lower())


def parse_operator_log(text):
    """Extrai DecisionRecords das linhas CEREBRO + AGIU/RAISE/FALLBACK (mesma frame)
    do stdout do operador. Útil p/ popular o Shadow Mode com decisões REAIS de uma
    sessão. Ignora CEREBRO sem cartas (hero=None)."""
    by_frame = {}
    order = []
    for line in text.splitlines():
        m = _CEREBRO.search(line)
        if m and m.group('hero') != 'None':
            fr = m.group('frame')
            status = m.group('status')
            tail = m.group('tail').strip()
            try:
                cards = json.loads(m.group('hero').replace("'", '"'))
            except ValueError:
                cards = None
            node = m.group('node') if m.group('node') != 'None' else None
            stack = None
            if node:
                parts = node.split('|')
                if len(parts) > 2 and parts[2].isdigit():
                    stack = int(parts[2])
            rec = dict(frame=int(fr), table=m.group('table'), hero_cards=cards,
                       position=m.group('pos'),
                       to_call_bb=None if m.group('tocall') == 'None' else m.group('tocall'),
                       spot=m.group('spot') if m.group('spot') != 'None' else None,
                       node_id=node, stack_bb=stack, validated=_bool(m.group('val')),
                       gto_status=status,
                       gto_recommended=tail if status == 'ADVICE' else None,
                       bot_action=None, authority=None, result_state=None)
            by_frame[fr] = rec
            order.append(fr)
            continue
        for rx, kind in ((_AGIU, 'agiu'), (_RAISE, 'raise'), (_FALL, 'fall')):
            m = rx.search(line)
            if not m:
                continue
            fr = m.group('frame')
            rec = by_frame.get(fr)
            if rec is None:
                break
            if kind == 'agiu':
                rec['bot_action'] = m.group('action').lower()
                rec['authority'] = m.group('auth')
                rec['result_state'] = m.group('state')
            elif kind == 'raise':
                rec['bot_action'] = 'all_in' if m.group('preset').upper().startswith('ALL_IN') else 'raise'
                rec['authority'] = rec['authority'] or 'VALIDATED'
            elif kind == 'fall' and rec.get('bot_action') is None:
                rec['bot_action'] = m.group('action').lower()
                rec['authority'] = m.group('auth')
            break
    return [make_record(**by_frame[fr]) for fr in order if fr in by_frame]
