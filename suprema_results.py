"""Pipeline de RESULTADOS de torneio da Suprema -> jsonl que o PAINEL lê (session_summary).

Grava UMA linha por torneio (schema v1 de session_summary) no fim da mão/bust. Camadas:
  - PURAS/testáveis: new_session_id, buyin_from_grade, mtt_fields, build_row, record.
  - IO/wiring: on_bust_record (callback do vigia de bust) — monta a linha do estado vivo + grade
    e grava uma vez por (sessão, torneio). Best-effort: campo sem fonte confiável fica None (o
    agregador tolera; ITM sai do rank+places_paid, profit/ROI só quando houver prêmio).

UNIDADE: tudo em R$ (Play money) — a MOEDA DE BUY-IN da Suprema, NÃO as fichas de torneio
(buy-in/prêmio/bounty vêm todos nessa moeda). Ver schema em session_summary.py.

LIMITE CONHECIDO (precisa validação ao vivo): rank FINAL e PRÊMIO exatos vivem no pop-up de
CLASSIFICAÇÃO (suprema_bust). Sem um fixture real desse pop-up, aqui o rank é aproximado
(players_left no bust) e prize fica None. parse_classificacao() é o seam p/ ligar o OCR do prêmio
quando houver o print calibrado — aí profit/ROI acendem sozinhos.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import session_summary as S

DEFAULT_LOG = S.DEFAULT_LOG
_SESSION_STATE = os.path.join('logs', 'metrics', '.suprema_session.json')


# ───────────────────────── sessão ─────────────────────────
def new_session_id(now=None, state_path=_SESSION_STATE):
    """ID da sessão: "YYYY-MM-DD#n". Mesmo dia reaberto => n+1; dia novo => n=1. Persistido num
    state minúsculo (best-effort; se não der p/ gravar, devolve "#1" do dia). Chamar 1× na largada."""
    day = (now or datetime.now()).strftime('%Y-%m-%d')
    n = 1
    try:
        if os.path.exists(state_path):
            with open(state_path, encoding='utf-8') as fh:
                st = json.load(fh)
            if isinstance(st, dict) and st.get('date') == day:
                n = int(st.get('n', 0)) + 1
        os.makedirs(os.path.dirname(state_path) or '.', exist_ok=True)
        with open(state_path, 'w', encoding='utf-8') as fh:
            json.dump({'date': day, 'n': n}, fh)
    except Exception:
        pass
    return '%s#%d' % (day, n)


# ───────────────────────── buy-in da grade ─────────────────────────
def _norm(s):
    return ''.join(ch for ch in str(s or '').lower() if ch.isalnum())


def buyin_from_grade(name=None, tournament_id=None, grade=None, grade_path='grade_do_dia.json'):
    """Custo de inscrição (R$ play money) do torneio, cadastrado pelo Eduardo na aba Grade do Dia.
    Casa por nome (normalizado, substring) ou id. None se não achar. `grade` injetável p/ teste."""
    rows = grade
    if rows is None:
        try:
            with open(grade_path, encoding='utf-8') as fh:
                rows = json.load(fh)
        except Exception:
            rows = []
    if not isinstance(rows, list):
        return None
    nn = _norm(name)
    for r in rows:
        if not isinstance(r, dict):
            continue
        rn = _norm(r.get('name'))
        hit = (tournament_id is not None and str(r.get('id')) == str(tournament_id))
        if not hit and nn and rn:
            hit = nn in rn or rn in nn
        if hit:
            v = r.get('buyin_bb')
            if v is None:
                v = r.get('buyin')
            return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    return None


# ───────────────────────── estado MTT -> campos ─────────────────────────
def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def mtt_fields(state):
    """Extrai do estado vivo (SupremaTable.get_state()) os campos de torneio CONFIÁVEIS do stream:
    field (players_total), places_paid, players_left, rebuys/addons, mode (pko por 'type'/bounty_base).
    Tudo best-effort; chaves ausentes -> None. PURA."""
    mtt = (state or {}).get('mtt') or {}
    field = _num(mtt.get('players_total'))
    places = _num(mtt.get('places_paid'))
    left = _num(mtt.get('players_left'))
    mode = None
    t = str(mtt.get('type') or '').lower()
    if 'pko' in t or 'bounty' in t or mtt.get('bounty_base') is not None:
        mode = 'pko'
    elif t:
        mode = 'regular'
    return dict(field=int(field) if field else None,
                places_paid=int(places) if places else None,
                players_left=int(left) if left else None,
                rebuys=int(_num(mtt.get('rebuys')) or 0),
                addons=int(_num(mtt.get('addons')) or 0),
                mode=mode)


def hero_bounty(state):
    """Cash de bounty acumulado do hero (campo seat.bounty = cash ganho). None se não der."""
    try:
        seats = (state or {}).get('players') or (state or {}).get('seats') or {}
        hero_seat = (state or {}).get('hero_seat')
        if isinstance(seats, dict) and hero_seat in seats:
            return _num(seats[hero_seat].get('bounty'))
    except Exception:
        pass
    return None


# ───────────────────────── linha + gravação ─────────────────────────
def build_row(*, session_id, tournament_id, name=None, mode=None, buyin=None,
              rebuys=0, rebuy_cost=None, addons=0, addon_cost=None,
              prize=None, bounty=None, kos=None, rank=None, field=None, places_paid=None,
              reached_ft=None, result='busted', closed=True, now=None, currency='R$'):
    """Monta a linha schema-v1 (session_summary). Deriva invested/profit/itm quando há dado. PURA."""
    ts = (now or (lambda: datetime.now(timezone.utc).isoformat()))()
    # dia LOCAL (recorte "Hoje" do painel) a partir do session_id "YYYY-MM-DD#n"
    date = session_id.split('#')[0] if isinstance(session_id, str) and '#' in session_id \
        else datetime.now().strftime('%Y-%m-%d')
    bi = _num(buyin)
    invested = None
    if bi is not None:
        invested = bi + (_num(rebuy_cost) or 0) * (rebuys or 0) + (_num(addon_cost) or 0) * (addons or 0)
    prize_n, bounty_n = _num(prize), _num(bounty)
    profit = None
    if invested is not None or prize_n is not None or bounty_n is not None:
        profit = (prize_n or 0) + (bounty_n or 0) - (invested or 0)
    itm = None
    if isinstance(rank, int) and isinstance(places_paid, int) and places_paid > 0:
        itm = rank <= places_paid
    elif isinstance(rank, int) and isinstance(field, int) and field > 0:
        itm = rank <= max(1, field // 5)         # ~20% quando não há places_paid
    return dict(schema=S.SCHEMA, ts=ts, date=date, session_id=session_id, room='Suprema',
                event='tournament_end', tournament_id=str(tournament_id), name=name, mode=mode,
                currency=currency, buyin=bi, rebuys=int(rebuys or 0), rebuy_cost=_num(rebuy_cost),
                addons=int(addons or 0), addon_cost=_num(addon_cost), invested=invested,
                prize=prize_n, bounty=bounty_n, kos=(int(kos) if isinstance(kos, int) else None),
                profit=profit, rank=(rank if isinstance(rank, int) else None),
                field=(field if isinstance(field, int) else None), itm=itm,
                reached_ft=reached_ft, result=result, closed=bool(closed))


def record(path=DEFAULT_LOG, **row):
    """Acrescenta UMA linha ao jsonl de resultados (cria pasta). Devolve a linha gravada."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    return row


def parse_classificacao(tile_rgb):
    """SEAM (futuro, precisa fixture ao vivo): OCR do pop-up de CLASSIFICAÇÃO p/ rank FINAL e PRÊMIO
    exatos. Hoje devolve {} (sem chute). Quando houver o print calibrado, preencher rank/prize aqui
    e o profit/ROI acendem sozinhos no painel. Mantido separado p/ não gravar valor não-validado."""
    return {}


def make_bust_recorder(*, session_id, tournament_id, name, buyin=None, path=DEFAULT_LOG,
                       get_state=None, recorded=None):
    """Fábrica do callback de bust: grava UMA vez por torneio (dedup em `recorded`), montando a linha
    do estado vivo (mtt_fields + hero_bounty) + buy-in da grade. Best-effort: nunca lança no vigia.

    `get_state()` -> estado vivo (SupremaTable.get_state()) ou None. `recorded` = set compartilhado
    (sala/coluna já gravada). Devolve a função (column, tile) p/ passar ao bust_watch como on_bust."""
    recorded = recorded if recorded is not None else set()

    def on_bust(column=None, tile=None):
        key = (session_id, str(tournament_id), column)
        if key in recorded:
            return None
        state = None
        try:
            state = get_state() if get_state else None
        except Exception:
            state = None
        mf = mtt_fields(state) if state else dict(field=None, places_paid=None, players_left=None,
                                                  rebuys=0, addons=0, mode=None)
        extra = {}
        try:
            extra = parse_classificacao(tile) or {}      # rank/prize exatos quando o OCR estiver ligado
        except Exception:
            extra = {}
        rank = extra.get('rank')
        if rank is None and isinstance(mf.get('players_left'), int):
            rank = mf['players_left']                     # aproximação: vivos no bust ~ posição final
        row = build_row(
            session_id=session_id, tournament_id=tournament_id, name=name,
            mode=mf.get('mode'), buyin=buyin, rebuys=mf.get('rebuys') or 0,
            addons=mf.get('addons') or 0, prize=extra.get('prize'),
            bounty=hero_bounty(state), kos=extra.get('kos'), rank=rank,
            field=mf.get('field'), places_paid=mf.get('places_paid'), result='busted', closed=True)
        try:
            record(path, **row)
            recorded.add(key)
        except Exception:
            return None
        return row

    return on_bust
