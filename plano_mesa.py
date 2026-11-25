"""PLANO DE MESA — consulta o DB de exploração (exploit_db.json) para os vilões presentes
na mesa e imprime, por jogador, como explorá-lo. Fecha o ciclo "ler o field na mesa".

Uso:
    python plano_mesa.py 8251882 1334308 "CapimVerde"        # IDs/nicks dos vilões sentados
    python plano_mesa.py --db logs/exploit_db.json 111 222   # outro DB
    python plano_mesa.py --file mesa.txt                     # 1 ID por linha

Vilão sem leitura (não está no DB / amostra pequena) -> "jogar base GTO" (honesto).
EXPLORATÓRIO: é consulta de estudo; não executa nada.
"""
import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

_DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'exploit_db.json')
# ordem de "quão explorável" (fish primeiro) p/ priorizar atenção
_PRIO = {'fish': 0, 'nit': 1, 'lag': 2, 'reg': 3, 'unknown': 4}


def load_db(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _stat(s, k):
    v = s.get(k) if s else None
    return '--' if v is None else f'{v:.0f}'


def format_villain(vid, rec):
    if not rec:
        return f"[{vid}]  SEM LEITURA (fora do DB / amostra pequena) → jogar base GTO"
    s = rec.get('stats', {})
    tags = ','.join(rec.get('tags', [])) or '-'
    head = (f"[{vid}]  {rec['category'].upper()} [{tags}]  "
            f"V{_stat(s,'vpip')}/P{_stat(s,'pfr')}/3b{_stat(s,'threebet')}/"
            f"STL{_stat(s,'steal')}/CB{_stat(s,'cbet')}/FCB{_stat(s,'foldcbet')}  "
            f"({rec.get('hands','?')} mãos)")
    adjs = (rec.get('preflop', []) + rec.get('postflop', []))
    lines = [head]
    if adjs:
        for a in adjs[:4]:
            lines.append(f"    • {a['situation']}: {a['direction']} ({a['strength']}) — {a['why']}")
    else:
        lines.append("    • reg sólido — sem exploit claro, jogar perto do GTO")
    return '\n'.join(lines)


def table_summary(ids, db):
    from collections import Counter
    cc = Counter()
    for vid in ids:
        rec = db.get(vid)
        cc[rec['category'] if rec else 'unknown'] += 1
    parts = [f"{k}:{cc[k]}" for k in ('fish', 'nit', 'lag', 'reg', 'unknown') if cc[k]]
    return 'Mesa: ' + '  '.join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ids', nargs='*', help='IDs/nicks dos vilões na mesa')
    ap.add_argument('--db', default=_DEFAULT_DB)
    ap.add_argument('--file', help='arquivo com 1 ID por linha')
    args = ap.parse_args()

    ids = list(args.ids)
    if args.file:
        with open(args.file, encoding='utf-8') as f:
            ids += [ln.strip() for ln in f if ln.strip()]
    if not ids:
        print('uso: python plano_mesa.py <id1> <id2> ...  (ou --file mesa.txt)')
        return
    if not os.path.exists(args.db):
        print(f'[plano] DB não encontrado: {args.db}\n  gere com: python field_exploit.py <pasta_HHs>')
        return
    db = load_db(args.db)

    # ordena: mais exploráveis primeiro (fish/nit), depois o resto
    def prio(vid):
        rec = db.get(vid)
        return _PRIO.get(rec['category'] if rec else 'unknown', 9)
    ordered = sorted(ids, key=prio)

    print(table_summary(ids, db))
    print('=' * 72)
    for vid in ordered:
        print(format_villain(vid, db.get(vid)))
        print()


if __name__ == '__main__':
    main()
