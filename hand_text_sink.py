"""Sink de TEXTO (formato Hand2Note) no padrão pedido:

    <base>\\<ANO>\\<MÊS>\\<DIA>\\<torneio>.txt

Uma PASTA por dia, um ARQUIVO por torneio, append-only (cada mão fechada é gravada na
hora). É o texto que o Hand2Note importa — e que o nosso hand_history.py também parseia.
"""
import os
from datetime import datetime

from hand_sink import sanitize_name

# NOSSA base de texto (não mistura com a pasta do conversor externo). Aponte p/ a pasta do
# Hand2Note com --base se quiser que ele importe direto.
DEFAULT_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'maos_h2n')


def _day(ts=None):
    try:
        dt = datetime.fromisoformat(ts) if ts else datetime.now()
    except (TypeError, ValueError):
        dt = datetime.now()
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt


def text_path(base, tournament, ts=None):
    dt = _day(ts)
    day_dir = os.path.join(base, '%04d' % dt.year, '%02d' % dt.month, '%02d' % dt.day)
    return os.path.join(day_dir, sanitize_name(tournament) + '.txt')


class HandTextSink:
    """Grava cada mão (texto Hand2Note) em <base>\\ANO\\MÊS\\DIA\\<torneio>.txt."""

    def __init__(self, base=DEFAULT_BASE):
        self.base = base
        self.written = set()
        self.count = 0

    def write(self, text, tournament='sessao', ts=None):
        if not text:
            return None
        path = text_path(self.base, tournament, ts)
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(text.rstrip('\n') + '\n\n\n')
        self.written.add(path)
        self.count += 1
        return path
