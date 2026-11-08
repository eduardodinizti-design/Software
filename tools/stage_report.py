"""Offline per-stage timing report for a passive session folder.

Reads a session's `leituras.jsonl` (written by coletar_sessao.py) and prints the
median/p95 of each pipeline stage (capture, detection, OCR setup, OCR wall,
hero, buttons, board, analyze total, cycle, CPU) plus the RSS memory budget.

This is analysis only: it never captures, clicks, or judges accuracy. Periodic
sampling can miss events between captures; these timings describe the measured
cycles, not isolated per-field truth.

Usage:
    python -m tools.stage_report --session logs/sessoes/sessao-...
    python -m tools.stage_report --jsonl path/to/leituras.jsonl --output stage-profile.json
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import stage_metrics


def _load_rows(jsonl_path):
    rows = []
    statuses = Counter()
    with Path(jsonl_path).open('r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                statuses['MALFORMED_LINE'] += 1
                continue
            statuses[str(record.get('status', 'UNKNOWN'))] += 1
            rows.append(stage_metrics.row_from_record(record))
    return rows, statuses


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--session', type=Path, help='Pasta sessao-... com leituras.jsonl')
    source.add_argument('--jsonl', type=Path, help='Caminho direto para um leituras.jsonl')
    parser.add_argument('--output', type=Path, help='Grava o perfil como JSON neste caminho')
    args = parser.parse_args(argv)

    jsonl = args.jsonl if args.jsonl else args.session / 'leituras.jsonl'
    if not jsonl.is_file():
        parser.error(f'Nao encontrei {jsonl}')

    rows, statuses = _load_rows(jsonl)
    if not rows:
        print('Nenhum registro em', jsonl)
        return 2
    profile = stage_metrics.summarize(rows)
    print('Fonte:', jsonl)
    print('Registros:', sum(statuses.values()), '| por status:', dict(statuses))
    print()
    print(stage_metrics.format_table(profile))
    if args.output:
        payload = dict(profile, source=str(jsonl), records=sum(statuses.values()), statuses=dict(statuses),
                       limitations=['Amostragem periodica: eventos entre capturas podem ser perdidos.',
                                    'Tempos descrevem os ciclos medidos, nao verdade por campo isolado.'])
        Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        print('\nPerfil salvo em:', args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
