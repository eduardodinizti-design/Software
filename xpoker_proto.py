"""DECODER do protocolo do X-Poker (offline). Carrega os FileDescriptor(.pb) vendados em
`research/xpoker/pb/` num DescriptorPool e decodifica qualquer mensagem protobuf do wire do
X-Poker POR NOME. É o passo 1 do plano de captura (ver [[nvt-xpoker-recon]]): com isto pronto,
a captura ao vivo (hook SSL_read em libssl-1_1.dll, igual à Suprema) só precisa de-framar o
WebSocket e chamar `decode(tipo, payload)`.

GAP conhecido (não resolvível pelos .pb): o ENVELOPE cmd-id -> tipo de mensagem NÃO está nos
descriptors (sem service, sem enum de rota, sem campo cmd). Fica p/ a captura viva (ler o header
que precede o payload) ou o decompile do Lua cifrado. Enquanto isso, `try_decode()` identifica
o tipo tentando as mensagens de MESA candidatas e vendo qual parseia limpo.

READ-ONLY / puro: só lê os .pb do disco e parseia bytes. Não toca em processo nem rede.
"""
from __future__ import annotations

import os
import glob

from google.protobuf import descriptor_pb2 as _dpb
from google.protobuf import descriptor_pool as _pool
from google.protobuf import message_factory as _mf

PB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "research", "xpoker", "pb")

# Mensagens de PERCEPÇÃO do Texas (as que interessam p/ ler o estado da mesa). Ver nvt-xpoker-recon.
TABLE_MSGS = [
    "pk.TexasGameStartBRC",     # inicio: hand_id, dealer/sb/bb, seat_info[]
    "pk.TexasSelfHandBRC",      # cartas do HEROI (hands[])
    "pk.TexasRoundBeginBRC",    # board por rua (board_cards[])
    "pk.TexasGameActionBRC",    # cada acao (action, chips, seat)
    "pk.TexasRoundEndBRC",      # pot[]
    "pk.TexasGameEndBRC",       # fim
    "pk.TexasPlayerDetail",     # a VEZ: require_call_amount, min/max bet, hand_cards[]
    "pk.TexasGameDetail",       # snapshot completo (cold-attach)
    "pk.TexasSeatDetail",
    "pk.TexasPotWinningDetail",
]


def _iter_file_descriptors():
    """Todos os FileDescriptorProto únicos (por nome) dos .pb vendados."""
    seen = {}
    for path in sorted(glob.glob(os.path.join(PB_DIR, "*.pb"))):
        data = open(path, "rb").read()
        files = []
        try:
            fds = _dpb.FileDescriptorSet()
            fds.ParseFromString(data)
            files = list(fds.file)
        except Exception:
            files = []
        if not files:
            fdp = _dpb.FileDescriptorProto()
            fdp.ParseFromString(data)
            files = [fdp]
        for f in files:
            seen.setdefault(f.name, f)      # dedupe: um .pb pode trazer deps embutidas
    return seen


def _build_pool():
    """DescriptorPool com os arquivos adicionados em ORDEM de dependência (base.proto antes)."""
    files = _iter_file_descriptors()
    pool = _pool.DescriptorPool()
    added = set()

    def add(name, stack):
        if name in added or name not in files:
            return
        if name in stack:                    # ciclo (não esperado) -> para
            return
        stack.add(name)
        for dep in files[name].dependency:
            add(dep, stack)
        try:
            pool.Add(files[name])
            added.add(name)
        except Exception:
            # já presente / conflito benigno -> ignora
            added.add(name)
        stack.discard(name)

    for name in list(files):
        add(name, set())
    return pool


_POOL = None


def pool():
    global _POOL
    if _POOL is None:
        _POOL = _build_pool()
    return _POOL


def get_class(full_name):
    """Classe de mensagem protobuf pelo nome completo (ex. 'pk.TexasRoundBeginBRC')."""
    desc = pool().FindMessageTypeByName(full_name)
    return _mf.GetMessageClass(desc)


def decode(full_name, data):
    """Decodifica `data` (bytes do payload protobuf) como `full_name`. Lança se não casar."""
    msg = get_class(full_name)()
    msg.ParseFromString(data)
    return msg


def list_messages(prefix="pk."):
    """Nomes de todas as mensagens conhecidas (opcionalmente filtradas por prefixo)."""
    out = []
    for name in pool_message_names():
        if name.startswith(prefix):
            out.append(name)
    return sorted(out)


def pool_message_names():
    """Todos os full_names de mensagens no pool (varre os descriptors)."""
    names = []
    for f in _iter_file_descriptors().values():
        pkg = f.package
        def walk(msgs, pfx):
            for m in msgs:
                fn = "%s.%s" % (pfx, m.name) if pfx else m.name
                names.append(fn)
                walk(m.nested_type, fn)
        walk(f.message_type, pkg)
    return names


def try_decode(data, candidates=None, require_full=True):
    """Sem o cmd-id, identifica o tipo: tenta cada candidato e devolve [(nome, msg)] que
    parseiam. Com require_full, re-serializa e exige bytes idênticos (parse 'limpo', sem campos
    desconhecidos engolidos) — reduz falso-positivo. candidates default = TABLE_MSGS."""
    out = []
    for name in (candidates or TABLE_MSGS):
        try:
            msg = decode(name, data)
        except Exception:
            continue
        if require_full:
            try:
                if msg.SerializeToString() != data:
                    continue
            except Exception:
                continue
        out.append((name, msg))
    return out


if __name__ == "__main__":
    p = pool()
    names = list_messages()
    print("[xpoker_proto] pool OK: %d mensagens pk.*" % len(names))
    for n in TABLE_MSGS:
        try:
            c = get_class(n)
            fields = [f.name for f in c.DESCRIPTOR.fields]
            print("  %-26s campos: %s" % (n, fields))
        except Exception as e:
            print("  %-26s ERRO: %s" % (n, e))
