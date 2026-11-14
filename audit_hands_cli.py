"""CLI do auditor NATIVO de leaks pós-flop (sem IA, offline, não vaza dados).

Uso:
    python audit_hands_cli.py <historico.txt> [--hero NICK] [--json saida.json]

Lê um export .txt de mãos do PPPoker, gradua as decisões pós-flop do hero contra o
cérebro (`postflop_advisor`) e imprime os leaks mais frequentes/custosos + perfil
recomendado. Com --json, grava o relatório estruturado completo.
"""
import argparse
import io
import json
import sys

from leak_audit import audit_file


def _fmt(report):
    L = []
    L.append('=' * 66)
    L.append(' AUDITORIA PÓS-FLOP (cérebro nativo, sem IA) — %s' % report['source'])
    L.append('=' * 66)
    L.append(' Mãos lidas .............. %d' % report['total_hands_detected'])
    L.append(' Pós-flop auditadas ...... %d' % report['postflop_hands_reviewed'])
    L.append(' Decisões graduadas ...... %d' % report['decisions_reviewed'])
    L.append(' Leaks encontrados ....... %d' % report['total_mistakes_found'])
    L.append(' Nota pós-flop ........... %s' % report['overall_grade'])
    L.append(' Perfil recomendado ...... %s' % report['recommended_profile'])
    L.append(' Motivo .................. %s' % report['profile_adjustment_reason'])
    L.append('-' * 66)
    if not report['top_mistakes']:
        L.append(' Nenhum leak pós-flop confiante encontrado. 👍')
    for i, t in enumerate(report['top_mistakes'], 1):
        L.append(' %d. [%s] %s  —  %dx (%.1f%%) · %s'
                 % (i, t['severity'].upper(), t['category'], t['occurrences'],
                    t['frequency_pct'], t['affected_street']))
        L.append('    ex.: %s' % t['example_spot'])
        L.append('    fix: %s' % t['recommended_fix'])
    L.append('=' * 66)
    return '\n'.join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Auditor nativo de leaks pós-flop (PPPoker .txt).')
    ap.add_argument('arquivo', help='histórico de mãos .txt exportado do PPPoker')
    ap.add_argument('--hero', default=None, help="nick do hero (senão detecta 'Dealt to'/'Hero')")
    ap.add_argument('--json', default=None, help='grava o relatório estruturado neste caminho')
    args = ap.parse_args(argv)

    report = audit_file(args.arquivo, args.hero)

    # Saída UTF-8 mesmo no console cp1252 do Windows.
    out = sys.stdout
    if hasattr(out, 'buffer'):
        out = io.TextIOWrapper(out.buffer, encoding='utf-8', errors='replace')
    out.write(_fmt(report) + '\n')
    out.flush()

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print('[json] relatório salvo em %s' % args.json)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
