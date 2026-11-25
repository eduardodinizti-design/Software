"""De-framer de WebSocket (RFC 6455) para o X-Poker. Entre o SSL_read (plaintext TLS = frames
WS) e o decoder protobuf (xpoker_proto). Reassembla frames fragmentados, desmascara, e devolve
os PAYLOADS completos (binários = protobuf). Espelha o papel do JsonFrameExtractor da Suprema,
mas pra frames WS binários em vez de JSON de texto.

Hook ao vivo (sessão dedicada): SSL_read em libssl-1_1.dll -> alimentar os bytes aqui -> cada
payload binário vai pro xpoker_proto.try_decode/decode. READ-ONLY / puro (só processa bytes).

Nota: no servidor->cliente (o que o SSL_read lê) os frames vêm DESMASCARADOS (RFC 6455 §5.1);
tratamos máscara mesmo assim por robustez. Opcodes: 0=cont,1=text,2=binary,8=close,9=ping,10=pong.
"""
from __future__ import annotations

_MAX_BUF = 8 << 20   # 8 MiB teto de remontagem (sanidade)


class WSDeframer:
    """Acumula bytes de um stream WS e devolve, a cada feed, os payloads de MENSAGEM completos
    (juntando frames de continuação). Guarda frame parcial entre feeds."""

    def __init__(self):
        self._buf = bytearray()
        self._frag_op = None            # opcode da mensagem em montagem (1=text/2=binary)
        self._frag = bytearray()        # payload acumulado da mensagem fragmentada

    def feed(self, data):
        """Adiciona bytes crus; devolve lista de (opcode, payload_bytes) de mensagens COMPLETAS."""
        if data:
            self._buf += data
            if len(self._buf) > _MAX_BUF:
                self._buf = self._buf[-_MAX_BUF:]
        out = []
        while True:
            frame = self._take_frame()
            if frame is None:
                break
            fin, opcode, payload = frame
            if opcode == 0x0:                      # continuação
                self._frag += payload
                if fin:
                    out.append((self._frag_op or 0x2, bytes(self._frag)))
                    self._frag, self._frag_op = bytearray(), None
            elif opcode in (0x1, 0x2):             # text / binary
                if fin:
                    out.append((opcode, bytes(payload)))
                else:
                    self._frag_op = opcode
                    self._frag = bytearray(payload)
            else:                                   # controle (close/ping/pong): entrega à parte
                out.append((opcode, bytes(payload)))
        return out

    def _take_frame(self):
        """Extrai UM frame do buffer, ou None se incompleto. Avança o buffer quando consome."""
        b = self._buf
        n = len(b)
        if n < 2:
            return None
        fin = (b[0] & 0x80) != 0
        opcode = b[0] & 0x0F
        masked = (b[1] & 0x80) != 0
        ln = b[1] & 0x7F
        i = 2
        if ln == 126:
            if n < i + 2:
                return None
            ln = int.from_bytes(b[i:i + 2], 'big'); i += 2
        elif ln == 127:
            if n < i + 8:
                return None
            ln = int.from_bytes(b[i:i + 8], 'big'); i += 8
        if masked:
            if n < i + 4:
                return None
            mask = b[i:i + 4]; i += 4
        if n < i + ln:
            return None                              # payload incompleto -> espera mais bytes
        payload = bytearray(b[i:i + ln])
        if masked:
            for j in range(ln):
                payload[j] ^= mask[j & 3]
        del self._buf[:i + ln]                        # consome o frame
        return fin, opcode, payload


def messages_from_stream(chunks, binary_only=True):
    """Conveniência/teste: dada uma sequência de chunks, devolve os payloads completos. Com
    binary_only, só os de opcode 2 (binary = protobuf)."""
    d = WSDeframer()
    out = []
    for ch in chunks:
        for op, pl in d.feed(ch):
            if (not binary_only) or op == 0x2:
                out.append(pl)
    return out


def build_frame(payload, opcode=0x2, fin=True, mask=None):
    """Monta UM frame WS (p/ TESTE). mask=bytes de 4 -> mascara (como cliente->servidor)."""
    b = bytearray()
    b.append((0x80 if fin else 0) | (opcode & 0x0F))
    ln = len(payload)
    mbit = 0x80 if mask else 0
    if ln < 126:
        b.append(mbit | ln)
    elif ln < (1 << 16):
        b.append(mbit | 126); b += ln.to_bytes(2, 'big')
    else:
        b.append(mbit | 127); b += ln.to_bytes(8, 'big')
    if mask:
        b += bytes(mask)
        b += bytes(payload[j] ^ mask[j & 3] for j in range(ln))
    else:
        b += bytes(payload)
    return bytes(b)
