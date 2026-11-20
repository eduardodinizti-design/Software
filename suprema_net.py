"""Ponte de REDE da SUPREMA: hook SSL_read (TLS, já descriptografado) -> reassembla o
stream -> extrai as mensagens JSON (gameinfo/moveturn/prompt) -> alimenta o SupremaTable
-> decide pelo cérebro. READ-ONLY (observa; não envia nada ao jogo).

A parte TESTÁVEL offline é o `JsonFrameExtractor` (balanceia chaves respeitando strings e
reconstrói mensagens que fragmentam entre reads). A fiação Frida (`run_live`) precisa do
cliente aberto p/ validar — ver research/suprema_cocos/SUPREMA_PROTOCOL.md.
"""
from __future__ import annotations

import json

_MAX_BUF = 1 << 20   # 1 MiB: teto do buffer de remontagem (evita runaway)


class JsonFrameExtractor:
    """Acumula texto (chunks de SSL_read decodificados latin-1) e devolve, a cada `feed`,
    a lista de objetos JSON COMPLETOS encontrados. Mensagens fragmentadas entre chunks
    ficam no buffer até fechar. Ignora o lixo binário do header WS/pomelo antes do '{'."""

    def __init__(self):
        self._buf = ''

    def feed(self, text):
        if not text:
            return []
        self._buf += text
        if len(self._buf) > _MAX_BUF:
            self._buf = self._buf[-_MAX_BUF:]     # descarta o começo velho (sanidade)
        out = []
        i = 0
        n = len(self._buf)
        consumed_to = 0
        while i < n:
            if self._buf[i] != '{':
                i += 1
                continue
            end = self._match_object(self._buf, i)
            if end is None:
                break                              # objeto incompleto -> espera mais bytes
            chunk = self._buf[i:end]
            try:
                obj = json.loads(chunk)
                if isinstance(obj, dict):
                    out.append(obj)
                consumed_to = end
                i = end
            except ValueError:
                i += 1                             # '{' falso (lixo binário) -> avança
        # mantém só o que ainda não fechou (a partir do último '{' não-consumido)
        tail_start = self._buf.find('{', consumed_to)
        self._buf = '' if tail_start < 0 else self._buf[tail_start:]
        return out

    @staticmethod
    def _match_object(s, start):
        """Índice APÓS o '}' que fecha o objeto que começa em `start`, ou None se incompleto.
        Respeita strings e escapes."""
        depth = 0
        in_str = False
        esc = False
        for j in range(start, len(s)):
            c = s[j]
            if in_str:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        return j + 1
        return None


def messages_from_stream(chunks):
    """Conveniência/teste: dada uma sequência de chunks de texto, devolve as mensagens JSON
    (dicts) na ordem. Usa um único extrator (estado entre chunks)."""
    ex = JsonFrameExtractor()
    out = []
    for ch in chunks:
        out.extend(ex.feed(ch))
    return out


def is_game_event(msg):
    """True se a mensagem é um evento de jogo que o SupremaTable consome."""
    return isinstance(msg, dict) and msg.get('event') in (
        'gameinfo', 'moveturn', 'prompt', 'handover', 'gameResult', 'settle')


# ---------------------------------------------------------------------------
# FIAÇÃO AO VIVO (Frida) — precisa do cliente aberto p/ validar. READ-ONLY.
# ---------------------------------------------------------------------------
_AGENT = r"""
'use strict';
const a = Process.getModuleByName('libssl-1_1.dll').findExportByName('SSL_read');
if (!a) { send({err: 'sem SSL_read' }); }
else Interceptor.attach(a, {
  onEnter(args) { this.buf = args[1]; },
  onLeave(ret) {
    try {
      const n = ret.toInt32(); if (n <= 0 || !this.buf) return;
      const take = Math.min(n, 65536);
      send({ssl: true}, this.buf.readByteArray(take));   // manda os bytes crus p/ o Python
    } catch (e) {}
  }
});
send({ready: true});
"""


def run_live(bb_chips, on_state=None, seconds=0, process='SupremaPoker.exe'):
    """Anexa no cliente, hooka SSL_read e mantém um SupremaTable vivo. A cada evento de jogo,
    chama `on_state(table)` (se dado) — ex.: rodar advise_from_suprema em DRY-RUN. READ-ONLY.
    Requer o cliente aberto; a extração de JSON é a mesma testada offline."""
    import time
    import frida
    from suprema_state import SupremaTable

    ex = JsonFrameExtractor()
    table = SupremaTable(bb_chips=bb_chips)
    dev = frida.get_local_device()
    procs = [p for p in dev.enumerate_processes() if p.name.lower() == process.lower()]
    if not procs:
        raise RuntimeError('%s não está aberto' % process)
    session = dev.attach(procs[0].pid)
    script = session.create_script(_AGENT)

    def _on(m, data):
        if m.get('type') != 'send':
            return
        p = m.get('payload') or {}
        if not p.get('ssl') or not data:
            return
        for msg in ex.feed(bytes(data).decode('latin-1', 'replace')):
            if is_game_event(msg):
                table.feed_json(msg)
                if on_state:
                    try:
                        on_state(table)
                    except Exception:
                        pass

    script.on('message', _on)
    script.load()
    t0 = time.time()
    try:
        while seconds == 0 or (time.time() - t0) < seconds:
            time.sleep(0.3)
    finally:
        try: script.unload()
        except Exception: pass
        try: session.detach()
        except Exception: pass
    return table
