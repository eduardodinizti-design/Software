"""Prontidão por telemetria REAL: lê os logs de estado das sessões (logs/estado/*.jsonl)
e mede o que o Henrique DE FATO faria numa mesa — quanto executaria, quanto só estudaria e
quanto absteria, e por quê. Offline, sem mesa, sem clique.

Responde com DADOS (não teoria) às perguntas de prontidão:
  - Em que fração das decisões reais o Henrique ARMARIA ficha (nó validado + commit)?
  - Quanto vira ESTUDO (approximation/referência não-validada -> não dispara)?
  - Quanto ABSTÉM, e por qual motivo (pós-flop não-coberto, sem nó, leitura falha)?
  - Em que ZONA (stack/mesa) as sessões caíram vs a zona executável (5-25bb, 9-max)?

Regra de execução (espelha operar_mesa): fold/check são PISO de segurança (executam
sempre, até sem nó). raise/call/all-in só ARMAM com validated=True (ou call-off). RAISE
de nó não-validado só estuda (operar_mesa.py).
"""
import glob
import json
import os
from collections import Counter

ESTADO_GLOB = os.path.join('logs', 'estado', '*', 'estado.jsonl')
_COMMIT = ('raise', 'call', 'all_in', 'bet')
_SAFETY = ('fold', 'check')


def _iter_advices(paths):
    for f in paths:
        with open(f, encoding='utf-8') as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    d = json.loads(ln)
                except ValueError:
                    continue
                adv = d.get('advice')
                if isinstance(adv, dict):
                    yield adv


def analyze(glob_pattern=ESTADO_GLOB):
    paths = sorted(glob.glob(glob_pattern))
    n = 0
    status = Counter()
    abstain_reason = Counter()
    advice_spot = Counter()
    validated = Counter()
    would_execute = 0          # commit armável (validated + ação de commit)
    study_only_commit = 0      # commit recomendado mas NÃO dispara (não-validado)
    safety_floor = 0           # fold/check (piso executa sempre)
    postflop_abstain = 0
    stack_caveats = Counter()
    table_size_caveats = Counter()
    for adv in _iter_advices(paths):
        n += 1
        st = adv.get('status')
        status[st] += 1
        if st == 'ABSTAIN':
            r = adv.get('reason')
            abstain_reason[r] += 1
            if r == 'POSTFLOP_NOT_COVERED':
                postflop_abstain += 1
            continue
        if st != 'ADVICE':
            continue
        advice_spot[adv.get('spot')] += 1
        v = bool(adv.get('validated'))
        validated[v] += 1
        rec = (adv.get('recommended') or '').lower()
        authority_ok = v or adv.get('authority') in ('CALL_OFF', 'VALIDATED')
        if rec in _SAFETY:
            safety_floor += 1
        elif rec in _COMMIT:
            if authority_ok:
                would_execute += 1
            else:
                study_only_commit += 1
        for c in (adv.get('caveats') or []):
            if c.startswith('STACK_BUCKETED'):
                stack_caveats[c] += 1
            elif c.startswith('TABLE_') and 'HANDED' in c:
                table_size_caveats[c] += 1
    advices = status.get('ADVICE', 0)
    return dict(
        sessions=len(paths), total_decisions=n, status=dict(status),
        abstain_reason=dict(abstain_reason.most_common()),
        postflop_abstain=postflop_abstain,
        advice_spots=dict(advice_spot.most_common()),
        validated=dict(validated),
        would_execute_commit=would_execute,
        study_only_commit=study_only_commit,
        safety_floor_exec=safety_floor,
        exec_rate_pct=round(100.0 * would_execute / n, 2) if n else None,
        abstain_rate_pct=round(100.0 * status.get('ABSTAIN', 0) / n, 2) if n else None,
        validated_rate_of_advice_pct=round(100.0 * validated.get(True, 0) / advices, 2) if advices else None,
        stack_zone=dict(stack_caveats.most_common()),
        table_size=dict(table_size_caveats.most_common()),
    )


def _fmt(r):
    L = ['=== PRONTIDÃO POR TELEMETRIA REAL (logs/estado) ===',
         'Sessões: %d | decisões: %d' % (r['sessions'], r['total_decisions']),
         'Status: %s' % r['status'],
         '',
         'O QUE O HENRIQUE FARIA de fato:',
         '  ARMARIA ficha (commit validado):   %d  (%s%% do total)' % (
             r['would_execute_commit'], r['exec_rate_pct']),
         '  ESTUDO só (commit não-validado):    %d  (recomenda mas NÃO dispara)' % r['study_only_commit'],
         '  PISO seguro (fold/check):           %d' % r['safety_floor_exec'],
         '  ABSTEU:                             %d  (%s%%)' % (
             r['status'].get('ABSTAIN', 0), r['abstain_rate_pct']),
         '',
         'Abstenções por motivo:']
    for k, v in r['abstain_reason'].items():
        L.append('  %4d  %s' % (v, k))
    L += ['', 'Spots com ADVICE: %s' % r['advice_spots'],
          'Validated nos ADVICE: %s  (validados = %s%%)' % (
              r['validated'], r['validated_rate_of_advice_pct']),
          'Zona de stack (bucket): %s' % r['stack_zone'],
          'Tamanho de mesa: %s' % r['table_size']]
    return '\n'.join(L)


if __name__ == '__main__':
    import sys
    rep = analyze()
    print(json.dumps(rep, ensure_ascii=False, indent=2) if '--json' in sys.argv else _fmt(rep))
