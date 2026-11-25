"""Carrega e VALIDA a GRADE DO DIA (quais torneios jogar e quando) — a fonte de
verdade que alimenta o grind_planner. É a camada de I/O/validação que o grind_planner
(puro, sem I/O) de propósito não faz.

Fail-safe (metodologia do piloto): entrada inválida é REPORTADA em `errors`, nunca
corrigida nem inventada. Uma entrada ruim bloqueia a SI MESMA, não a grade inteira.

Esquema de cada torneio (grade_do_dia.json = LISTA destes):
  id         (obrigatório, str não-vazia)  nome EXATO como aparece no lobby
  start      (obrigatório, "HH:MM" 24h)    horário de início do torneio
  buyin_bb   (obrigatório, número >= 0)    custo da inscrição (fichas/BB)
  reg_opens  (opcional, "HH:MM")           quando a inscrição abre (vira reg_opens_min)
  club       (opcional, str)               RÓTULO do clube de onde registrar
                                           (ex.: "AK Ahakha club2"). NÃO restringe nada
                                           — todos os clubes estão liberados; serve p/ o
                                           runner saber em qual clube TROCAR O LOBBY antes
                                           de registrar, e p/ o histórico/ledger.

A grade normalizada sai pronta p/ o grind_planner.due_to_register: `start` (str) e
`reg_opens_min` (int) são os campos que ele consome.
"""
import json

from grind_planner import hhmm_to_min


def _finite_nonneg(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float('inf'), float('-inf')) or v < 0:   # NaN/inf/negativo
        return None
    return v


def normalize_entry(raw):
    """(entry_normalizada | None, [motivos de erro]). Não inventa valores: campo
    ausente/inválido vira erro, nunca um default silencioso."""
    if not isinstance(raw, dict):
        return None, ['entrada não é um objeto JSON (dict): %r' % (raw,)]
    errors = []
    e = {}

    rid = raw.get('id')
    if not isinstance(rid, str) or not rid.strip():
        errors.append('id ausente ou vazio')
    else:
        e['id'] = rid.strip()

    start = raw.get('start')
    if hhmm_to_min(start) is None:
        errors.append('start inválido (esperado "HH:MM" 24h): %r' % (start,))
    else:
        e['start'] = start

    buyin = _finite_nonneg(raw.get('buyin_bb'))
    if buyin is None:
        errors.append('buyin_bb inválido (esperado número >= 0): %r' % (raw.get('buyin_bb'),))
    else:
        e['buyin_bb'] = buyin

    ro = raw.get('reg_opens')
    if ro is not None:
        ro_min = hhmm_to_min(ro)
        if ro_min is None:
            errors.append('reg_opens inválido (esperado "HH:MM"): %r' % (ro,))
        else:
            e['reg_opens'] = ro                 # legível
            e['reg_opens_min'] = ro_min         # o que o grind_planner consome

    club = raw.get('club')
    if club is not None:
        if not isinstance(club, str) or not club.strip():
            errors.append('club deve ser string não-vazia (ou ausente): %r' % (club,))
        else:
            e['club'] = club.strip()            # RÓTULO; não restringe

    if errors:
        return None, errors
    return e, []


def normalize_grade(raw_list):
    """{'ok': bool, 'grade': [válidas], 'errors': [(índice|None, [motivos])]}.
    Entrada inválida é reportada, nunca descartada em silêncio nem corrigida. id
    duplicado é erro (dois cartões iguais confundiriam o registro)."""
    if not isinstance(raw_list, list):
        return dict(ok=False, grade=[],
                    errors=[(None, ['a grade deve ser uma LISTA de torneios'])])
    grade, errors, seen = [], [], {}
    for i, raw in enumerate(raw_list):
        e, errs = normalize_entry(raw)
        if errs:
            errors.append((i, errs))
            continue
        if e['id'] in seen:
            errors.append((i, ['id duplicado na grade: %r (já em #%d)' % (e['id'], seen[e['id']])]))
            continue
        seen[e['id']] = i
        grade.append(e)
    return dict(ok=not errors, grade=grade, errors=errors)


def load_grade(path):
    """Lê grade_do_dia.json e valida. Erro de arquivo/JSON vira `errors` (não explode)."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except FileNotFoundError:
        return dict(ok=False, grade=[], errors=[(None, ['arquivo não encontrado: %s' % path])])
    except (OSError, ValueError) as ex:
        return dict(ok=False, grade=[], errors=[(None, ['JSON inválido em %s: %s' % (path, ex)])])
    return normalize_grade(raw)
