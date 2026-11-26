"""Agregador de DESEMPENHO por sessão/dia do Henrique na Suprema (lógica pura, testável).

É a SUPERFÍCIE DE CONTRATO entre o pipeline de dados (grava o jsonl) e o PAINEL (lê e exibe):
o painel importa daqui e NUNCA faz parsing do jsonl na mão.

────────────────────────────────────────────────────────────────────────────────────────
SCHEMA (torneios_suprema.jsonl — append-only, 1 objeto JSON por linha)   schema=1
────────────────────────────────────────────────────────────────────────────────────────
  schema       int     versão do registro (1)
  ts           str     ISO-8601 UTC de quando foi gravado
  date         str     "YYYY-MM-DD" LOCAL da sessão (é o recorte "Hoje" do painel)
  session_id   str     agrupa torneios da MESMA sessão (ex.: "2026-11-25#1")
  room         str     "Suprema"
  event        str     "tournament_end"
  tournament_id str    id do torneio na Suprema (ex.: "20261125")
  name         str|None nome do torneio (se lido do lobby)
  mode         str|None "pko" | "regular" | None
  currency     str     unidade do dinheiro -> "R$" (Play money R$; é a MOEDA DE BUY-IN da Suprema,
                       NÃO as fichas de torneio — buy-in/prêmio/bounty vêm todos nessa moeda)
  buyin        num|None custo da inscrição, em R$ (play money)
  rebuys       int     nº de recompras      | rebuy_cost num|None custo unitário (R$)
  addons       int     nº de add-ons        | addon_cost num|None custo unitário (R$)
  invested     num|None buyin + rebuys*rebuy_cost + addons*addon_cost (em R$)
  prize        num|None prêmio recebido (R$ play money)
  bounty       num|None cash de bounty acumulado em PKO (R$ play money)
  kos          int|None cabeças/KOs
  profit       num|None (prize + bounty) - invested  (R$); None se faltar dado de $
  rank         int|None colocação final      | field int|None tamanho do campo
  itm          bool|None entrou no dinheiro
  reached_ft   bool|None chegou à mesa final
  result       str     "busted" | "itm" | "won" | ...
  closed       bool    a mesa foi de fato fechada (confirmado)

Campos ausentes/None são tolerados: o agregador só conta o que existe (nunca quebra).
O painel mostra tudo em R$ (Play money, currency="R$"); ROI = profit/invested.
"""
from __future__ import annotations

import json
import os
from collections import Counter, OrderedDict
from dataclasses import dataclass, field as _dc_field
from datetime import datetime, timezone

SCHEMA = 1
DEFAULT_LOG = os.path.join('logs', 'metrics', 'torneios_suprema.jsonl')


# ───────────────────────────── carga ─────────────────────────────
def load_rows(path=DEFAULT_LOG):
    """Lê o jsonl (tolerante a linha corrompida; nunca lança). Só eventos de fim de torneio."""
    rows = []
    if not path or not os.path.exists(path):
        return rows
    try:
        with open(path, encoding='utf-8') as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                if isinstance(r, dict) and r.get('event') == 'tournament_end':
                    rows.append(r)
    except Exception:
        return rows
    return rows


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def day_key(row):
    """Dia local do registro: usa `date` se gravado; senão deriva do `ts` (UTC->só a data)."""
    d = row.get('date')
    if isinstance(d, str) and len(d) >= 10:
        return d[:10]
    ts = row.get('ts')
    if isinstance(ts, str) and len(ts) >= 10:
        return ts[:10]
    return '?'


def invested_of(row):
    """Investido da mão: `invested` se gravado; senão reconstrói de buyin+rebuys+addons."""
    inv = _num(row.get('invested'))
    if inv is not None:
        return inv
    bi = _num(row.get('buyin'))
    if bi is None:
        return None
    total = bi
    rc = _num(row.get('rebuy_cost'))
    ac = _num(row.get('addon_cost'))
    if rc is not None:
        total += rc * (row.get('rebuys') or 0)
    if ac is not None:
        total += ac * (row.get('addons') or 0)
    return total


def profit_of(row):
    """Lucro da mão: `profit` se gravado; senão (prize+bounty)-invested quando houver dado."""
    pf = _num(row.get('profit'))
    if pf is not None:
        return pf
    inv = invested_of(row)
    prize = _num(row.get('prize'))
    bounty = _num(row.get('bounty'))
    if inv is None and prize is None and bounty is None:
        return None
    return (prize or 0) + (bounty or 0) - (inv or 0)


# ───────────────────────────── resumo ─────────────────────────────
@dataclass
class Summary:
    n: int = 0                       # torneios registrados
    currency: str = 'R$'             # Play money R$ (moeda de buy-in da Suprema)
    invested: float = 0.0            # total investido (R$)
    prize: float = 0.0               # total de prêmios (R$)
    bounty: float = 0.0              # total de bounty/KO cash (R$)
    profit: float = 0.0              # lucro líquido (R$)
    roi: float | None = None         # profit / invested (fração; *100 = %)
    itm_pct: float | None = None     # % no dinheiro
    ft_pct: float | None = None      # % mesa final
    avg_pos_pct: float | None = None # posição média (% do campo; MENOR = melhor)
    kos: int = 0                     # total de cabeças/KOs
    best_prize: float | None = None  # maior prêmio isolado
    rebuys: int = 0
    addons: int = 0
    by_result: dict = _dc_field(default_factory=dict)
    n_with_money: int = 0            # quantos torneios tinham dado de $ (p/ honestidade do ROI)

    def as_dict(self):
        return self.__dict__.copy()


def summarize(rows):
    """Resumo de um conjunto de linhas (já filtrado por dia/sessão pelo chamador)."""
    s = Summary(n=len(rows))
    invs, profs, prizes, itms, fts, poss = [], [], [], [], [], []
    res = Counter()
    for r in rows:
        if r.get('currency'):
            s.currency = r['currency']
        inv = invested_of(r)
        pf = profit_of(r)
        prize = _num(r.get('prize'))
        bounty = _num(r.get('bounty'))
        if inv is not None:
            invs.append(inv)
        if prize is not None:
            prizes.append(prize)
        if bounty is not None:
            s.bounty += bounty
        if pf is not None:
            profs.append(pf)
        if inv is not None or prize is not None or bounty is not None:
            s.n_with_money += 1
        ko = r.get('kos')
        if isinstance(ko, int):
            s.kos += ko
        s.rebuys += int(r.get('rebuys') or 0)
        s.addons += int(r.get('addons') or 0)
        if r.get('itm') is not None:
            itms.append(bool(r['itm']))
        if r.get('reached_ft') is not None:
            fts.append(bool(r['reached_ft']))
        rank, fld = r.get('rank'), r.get('field')
        if isinstance(rank, int) and isinstance(fld, int) and fld > 0:
            poss.append(100.0 * rank / fld)
        res[r.get('result') or '?'] += 1
    s.invested = round(sum(invs), 2)
    s.prize = round(sum(prizes), 2)
    s.bounty = round(s.bounty, 2)
    s.profit = round(sum(profs), 2)
    s.roi = (s.profit / s.invested) if s.invested else None
    s.itm_pct = (100.0 * sum(1 for x in itms if x) / len(itms)) if itms else None
    s.ft_pct = (100.0 * sum(1 for x in fts if x) / len(fts)) if fts else None
    s.avg_pos_pct = (sum(poss) / len(poss)) if poss else None
    s.best_prize = max(prizes) if prizes else None
    s.by_result = dict(res)
    return s


def _today_str(today=None):
    if today:
        return today
    return datetime.now().strftime('%Y-%m-%d')


def summarize_today(rows, today=None):
    """Resumo SÓ do dia atual (recorte "Hoje" do painel)."""
    day = _today_str(today)
    return summarize([r for r in rows if day_key(r) == day])


def summarize_session(rows, session_id):
    return summarize([r for r in rows if r.get('session_id') == session_id])


def group_by_day(rows):
    """OrderedDict dia -> Summary, em ordem cronológica (p/ tendência no histórico)."""
    buckets = OrderedDict()
    for r in sorted(rows, key=day_key):
        buckets.setdefault(day_key(r), []).append(r)
    return OrderedDict((d, summarize(rs)) for d, rs in buckets.items())


def sessions(rows):
    """Lista de session_ids conhecidos, do mais recente ao mais antigo."""
    seen = OrderedDict()
    for r in sorted(rows, key=lambda x: x.get('ts') or '', reverse=True):
        sid = r.get('session_id')
        if sid and sid not in seen:
            seen[sid] = True
    return list(seen.keys())


def cumulative_profit(rows):
    """Série (ts, lucro_acumulado) em ordem cronológica, p/ o gráfico de lucro/ROI."""
    out, cum = [], 0.0
    for r in sorted(rows, key=lambda x: x.get('ts') or ''):
        pf = profit_of(r)
        if pf is None:
            continue
        cum += pf
        out.append((r.get('ts'), round(cum, 2)))
    return out
