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
    """True se a mensagem é um evento de jogo que o SupremaTable/HandBuilder consomem.
    (Nomes REAIS descobertos ao vivo 21/11: início=`gamestart`, fim/showdown=`gameover`,
    assentos=`updateseat`, bounty=`KOdata`.)"""
    return isinstance(msg, dict) and msg.get('event') in (
        'gameinfo', 'moveturn', 'prompt', 'gamestart', 'gameover', 'updateseat', 'KOdata')


# ---------------------------------------------------------------------------
# FIAÇÃO AO VIVO (Frida) — precisa do cliente aberto p/ validar. READ-ONLY.
# ---------------------------------------------------------------------------
_AGENT = r"""
'use strict';
const _ssl = Process.getModuleByName('libssl-1_1.dll');
// SSL_read: ret = nº de bytes lidos; buffer em args[1].
const a = _ssl.findExportByName('SSL_read');
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
// SSL_read_ex (OpenSSL 1.1.1): int SSL_read_ex(SSL*, void* buf, size_t num, size_t* readbytes).
// ret = 1 em sucesso; os bytes lidos vêm em *readbytes (args[3]), buffer em args[1]. MUITAS libs/WS
// usam ESTA em vez de SSL_read -> quando o cliente lê por aqui, o hook de SSL_read fica MUDO (medido:
// agente ocioso esperando o Frida durante os travamentos). Cliente 32-bit -> size_t = 32-bit (readUInt).
const b = _ssl.findExportByName('SSL_read_ex');
if (!b) { send({err: 'sem SSL_read_ex' }); }
else Interceptor.attach(b, {
  onEnter(args) { this.buf = args[1]; this.pn = args[3]; },
  onLeave(ret) {
    try {
      if (ret.toInt32() !== 1 || !this.buf || this.pn.isNull()) return;
      const n = this.pn.readUInt(); if (n <= 0) return;   // *readbytes (size_t, 32-bit)
      const take = Math.min(n, 65536);
      send({ssl: true}, this.buf.readByteArray(take));
    } catch (e) {}
  }
});
send({ready: true});
"""


def run_live(bb_chips, on_state=None, seconds=0, process='SupremaPoker.exe', on_message=None, lock=True):
    """Anexa no cliente, hooka SSL_read e mantém um SupremaTable vivo. A cada evento de jogo,
    chama `on_state(table)` (se dado) — ex.: rodar advise_from_suprema em DRY-RUN — e também
    `on_message(msg)` com a MENSAGEM CRUA (dict event/data) p/ quem reconstrói mão a mão
    (SupremaHandBuilder -> banco). READ-ONLY. Requer o cliente aberto; a extração de JSON é a
    mesma testada offline."""
    import time
    import frida
    from suprema_state import SupremaTable

    # BLINDAGEM (Eduardo 21/11): só UM hook Frida por cliente. Recusa o 2º attach pra
    # evitar injeção dupla (suspeito nº1 de crash em clientes 32-bit V8/Cocos frágeis).
    _lock = None
    if lock:
        from client_lock import ClientLock, ClientBusy
        _lock = ClientLock(process)
        try:
            _lock.acquire()
        except ClientBusy as e:
            raise RuntimeError(
                "RECUSADO: %s. Já existe um hook Frida ativo nesse cliente; um 2º attach "
                "injetaria por cima (injeção dupla = risco de crash). Feche o outro antes, "
                "ou passe lock=False se tiver CERTEZA do que faz." % e) from None

    ex = JsonFrameExtractor()
    table = SupremaTable(bb_chips=bb_chips)
    session = None
    script = None
    try:
        dev = frida.get_local_device()
        procs = [p for p in dev.enumerate_processes() if p.name.lower() == process.lower()]
        if not procs:
            raise RuntimeError('%s não está aberto' % process)
        # Escolhe o PROCESSO DO JOGO (maior RSS) — evita o helper/launcher (procs[0] podia
        # ser o processo de 18MB, cujo attach dava TransportError timeout). Tenta o próximo.
        try:
            import psutil
            procs.sort(key=lambda p: psutil.Process(p.pid).memory_info().rss, reverse=True)
        except Exception:
            pass
        last_err = None
        for p in procs:
            try:
                session = dev.attach(p.pid)
                break
            except Exception as e:
                last_err = e
        if session is None:
            raise RuntimeError('não consegui anexar em %s: %s' % (process, last_err))
        script = session.create_script(_AGENT)
        last_evt = [time.time()]      # carimba cada EVENTO DE JOGO -> detecta hook mudo p/ auto-re-attach

        def _on(m, data):
            if m.get('type') != 'send':
                return
            p = m.get('payload') or {}
            if not p.get('ssl') or not data:
                return
            for msg in ex.feed(bytes(data).decode('latin-1', 'replace')):
                if is_game_event(msg):
                    last_evt[0] = time.time()
                    table.feed_json(msg)
                    if on_message:
                        try:
                            on_message(msg)
                        except Exception:
                            pass
                    if on_state:
                        try:
                            on_state(table)
                        except Exception:
                            pass

        script.on('message', _on)
        script.load()
        t0 = time.time()
        # NOTA (Eduardo 23/11): havia aqui um AUTO-RE-ATTACH (re-injetar o script no silêncio). REVERTIDO:
        # medido ao vivo que re-injetar NÃO restaura os eventos (o mute NÃO é hook pendurado — re-hookar o
        # mesmo SSL_read não traz dados), e re-injetar a cada 30s no cliente 32-bit frágil é risco de crash
        # e atrapalha a recuperação natural (o hook voltava sozinho em ~3-4min). Causa real do mute EM
        # INVESTIGAÇÃO. Por ora: só mantém o hook; o _mute_watchdog do agente apenas AVISA (seguro).
        while seconds == 0 or (time.time() - t0) < seconds:
            time.sleep(0.3)
    finally:
        # unload ANTES do detach: reverte os hooks com a conexão viva -> sem crash.
        if script is not None:
            try: script.unload()
            except Exception: pass
        if session is not None:
            try: session.detach()
            except Exception: pass
        if _lock is not None:
            _lock.release()
    return table
