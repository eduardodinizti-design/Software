"""Roteia cada mão gravada para o padrão solicitado (estilo Hand2Note):

    <base>\\<ANO>\\<MÊS>\\<DIA>\\<torneio>.jsonl

Uma PASTA por dia e um ARQUIVO por torneio. Usado como `sink` do HandRecorder.
O dia vem do timestamp da mão convertido p/ a hora LOCAL (o dia de jogo do operador).

Formato: JSONL (nosso registro rico). OBS: p/ o Hand2Note IMPORTAR de verdade seria
preciso o formato TEXTO de hand history dele (outra etapa, exige a mão completa com
toda a sequência de ações); aqui entregamos a ORGANIZAÇÃO por dia/torneio.
"""
import json
import os
import re
from datetime import datetime

# Base do NOSSO log de decisões do Henrique (JSONL). NÃO é a pasta do Hand2Note (aquela é
# alimentada pelo conversor externo em formato TEXTO; não misturar).
DEFAULT_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'maos_bot')


def sanitize_name(name):
    """Nome de arquivo seguro p/ o torneio (sem caracteres inválidos)."""
    s = re.sub(r'[^\w\- ]+', '', str(name or '').strip())
    s = re.sub(r'\s+', '_', s).strip('_')
    return (s or 'sem_torneio')[:60]


def _local_day(ts):
    try:
        dt = datetime.fromisoformat(ts) if ts else datetime.now()
    except (TypeError, ValueError):
        dt = datetime.now()
    if dt.tzinfo is not None:
        dt = dt.astimezone()          # UTC -> hora local (dia de jogo)
    return dt


def hand_path(base, rec):
    """Caminho destino da mão: <base>\\ANO\\MÊS\\DIA\\<torneio>.jsonl."""
    dt = _local_day(rec.get('ts'))
    day_dir = os.path.join(base, '%04d' % dt.year, '%02d' % dt.month, '%02d' % dt.day)
    tour = sanitize_name((rec.get('tournament') or {}).get('name'))
    return os.path.join(day_dir, tour + '.jsonl')


class DayTournamentSink:
    """`sink` do HandRecorder: grava cada mão em <base>\\ANO\\MÊS\\DIA\\<torneio>.jsonl
    (append-only, cria as pastas). Guarda os caminhos tocados em `written`."""

    def __init__(self, base=DEFAULT_BASE):
        self.base = base
        self.written = set()

    def __call__(self, rec):
        path = hand_path(self.base, rec)
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        self.written.add(path)
        return path
