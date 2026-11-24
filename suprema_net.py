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
_MAX_MSG = 1 << 17   # 128 KiB: maior mensagem de jogo plausível. Um '{' que não fecha em 128KB (e sem
                     # byte de controle que já o marque como lixo) é tratado como LIXO e PULADO — senão o
                     # parser TRAVA nele até encher _MAX_BUF (~3-4min = os "mutes" medidos 24/11). Ver
                     # _match_object: o gatilho PRINCIPAL é o byte de controle do framing WS (pula na hora).


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
            if end == -1:                          # '{' é LIXO binário (byte de controle no framing WS)
                i += 1                             # -> PULA na hora (senão trava o parser = o "mute")
                continue
            if end is None:
                # objeto ainda INCOMPLETO (msg real chegando aos pedaços) -> espera mais bytes. MAS se já
                # acumulou MUITO após o '{' sem fechar, trata como lixo e pula (teto de segurança, raro).
                if n - i > _MAX_MSG:
                    i += 1
                    continue
                break
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
        """Índice APÓS o '}' que fecha o objeto que começa em `start`; None se INCOMPLETO (ainda pode
        chegar mais bytes); -1 se o '{' é LIXO — contém um BYTE DE CONTROLE cru (framing binário WS/pomelo),
        que nunca vai fechar como JSON. O JSON de jogo é bem-formado (sem byte de controle cru fora de
        \\t\\n\\r), então controle cru = não é JSON -> o chamador PULA esse '{' em vez de travar o parser
        nele até encher _MAX_BUF (~3-4min = os 'mutes' medidos 24/11). Respeita strings e escapes."""
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
                elif c < ' ' and c not in '\t\n\r':
                    return -1                          # byte de controle cru dentro de string -> lixo
            else:
                if c == '"':
                    in_str = True
                elif c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        return j + 1
                elif c < ' ' and c not in '\t\n\r':
                    return -1                          # byte de controle cru fora de string -> não é JSON
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
      send({ssl: true, via: 'read'}, this.buf.readByteArray(take));   // manda os bytes crus p/ o Python
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
      send({ssl: true, via: 'read_ex'}, this.buf.readByteArray(take));
    } catch (e) {}
  }
});
send({ready: true});
"""


def run_live(bb_chips, on_state=None, seconds=0, process='SupremaPoker.exe', on_message=None, lock=True, pid=None):
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
        # MULTI-INSTANCIA (Eduardo 24/11): lock por PID quando `pid` é dado (duas instâncias da Suprema =
        # dois agentes, um por cliente/PID; não recusa o 2º cliente). Sem pid = lock por nome (1 instância).
        _lock = ClientLock('%s_%s' % (process, pid) if pid is not None else process)
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
        if pid is not None:
            session = dev.attach(int(pid))     # MULTI-INSTANCIA: anexa no cliente ESPECÍFICO (por PID)
        else:
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
        last_evt = [time.time()]      # carimba cada EVENTO DE JOGO -> detecta hook mudo
        # DIAGNÓSTICO do mute (Eduardo 24/11): conta leituras por função (read/read_ex), bytes e eventos
        # de jogo. O loop abaixo imprime um resumo a cada 5s — INCLUSIVE durante o mute -> mostra se o
        # hook está disparando (dado não-jogo) ou se NÃO chega nada (dados em outro caminho/conexão parada).
        _diag = {'read': 0, 'read_ex': 0, 'rb': 0, 'xb': 0, 'game': 0}

        def _on(m, data):
            if m.get('type') != 'send':
                return
            p = m.get('payload') or {}
            if not p.get('ssl') or not data:
                return
            if p.get('via') == 'read_ex':
                _diag['read_ex'] += 1
                _diag['xb'] += len(data)
            else:
                _diag['read'] += 1
                _diag['rb'] += len(data)
            for msg in ex.feed(bytes(data).decode('latin-1', 'replace')):
                if is_game_event(msg):
                    _diag['game'] += 1
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
        _last_diag = time.time()
        while seconds == 0 or (time.time() - t0) < seconds:
            time.sleep(0.3)
            _dt_s = time.time() - _last_diag
            if _dt_s >= 5.0:
                # resumo do que o HOOK recebeu nos últimos ~5s (imprime mesmo no mute: aí mostra 0/0/0)
                print('[NET-DIAG] %.0fs  read=%d/%.0fkb  read_ex=%d/%.0fkb  game_events=%d'
                      % (_dt_s, _diag['read'], _diag['rb'] / 1024,
                         _diag['read_ex'], _diag['xb'] / 1024, _diag['game']), flush=True)
                for _k in _diag:
                    _diag[_k] = 0
                _last_diag = time.time()
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
