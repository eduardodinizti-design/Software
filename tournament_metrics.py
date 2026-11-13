"""Registro de DESEMPENHO em torneios (métricas futuras). Append-only JSONL.

Ao cair de um torneio, a rotina fecha a mesa (clica 'Sair') e registra aqui o
resultado para análise posterior (ITM%, posição média, campo, etc.). Não captura
nem clica; só grava. Puro/testável.
"""
import json
import os
import re
from datetime import datetime, timezone

DEFAULT_LOG = os.path.join('logs', 'metrics', 'torneios.jsonl')
_RANK = re.compile(r'(\d{1,6})\s*/\s*(\d{1,6})')


def parse_ranking(ranking):
    """'65/272' -> (65, 272); None/ilegível -> (None, None)."""
    if not ranking:
        return None, None
    m = _RANK.search(str(ranking))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def record_tournament_end(*, ranking=None, tournament=None, series=None, buyin=None,
                          mode=None, result='busted', action='closed_via_sair',
                          closed=None, table_key=None, extra=None,
                          path=DEFAULT_LOG, now=None):
    """Acrescenta uma linha JSON ao log de métricas e devolve o registro.

    `ranking` = 'posição/campo' (ex.: '65/272'). `closed` = a mesa foi de fato
    fechada (confirmado). `now` injetável p/ teste."""
    placed, field = parse_ranking(ranking)
    row = dict(ts=(now or (lambda: datetime.now(timezone.utc).isoformat()))(),
               event='tournament_end', tournament=tournament, series=series,
               buyin=buyin, mode=mode, result=result, ranking=ranking,
               placed=placed, field=field,
               itm=None if (placed is None or field is None) else placed <= max(1, field // 5),
               action=action, closed=closed, table_key=table_key)
    if extra:
        row.update(extra)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    return row
