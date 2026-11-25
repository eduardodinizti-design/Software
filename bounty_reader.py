"""Leitura AUTOMÁTICA do bounty (PKO/KO) — o Henrique coleta o dado sozinho, sem o Eduardo
informar na mão ([[nvt]] lei "os dado é o Henrique que tem que registrar").

Consome `logs/mtt_bounty.json` (escrito pelo emissor via protobuf: campos de bounty da
mensagem MTT, por nome) e devolve o bounty em BB p/ o call-off (`icm_rp.bounty_power`).
Puro e testável: não captura nem clica.

Contrato de `logs/mtt_bounty.json` (campos opcionais; o reader é tolerante):
  { "ts": <unix>,                    # frescor
    "bb_chips": 2000,                # big blind em fichas (p/ converter chips->BB)
    "bounty_bb": 5.0,                # se já veio calibrado (precedência máxima)
    "hero_bounty_chips": 10000,
    "players": {"<uid>": <bounty_chips>, ...},   # bounty por vilão (o que se ganha)
    "candidates": {"<campo>": <valor>, ...},     # cru, p/ calibrar ao vivo
    "calibrated": true|false }

Precedência: bounty_bb calibrado > bounty do VILÃO específico > hero/médio. Sem fonte
fresca -> None (o operador cai no pko_icm sem desconto, como antes). NUNCA inventa.
"""
import json
import os
import time

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'logs', 'mtt_bounty.json')
MAX_AGE_S = 30.0          # bounty mais velho que isto é considerado stale (torneio trocou)


def _load(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _fresh(data, max_age_s, now):
    ts = (data or {}).get('ts')
    if not isinstance(ts, (int, float)):
        return False
    return (now - ts) <= max_age_s


def read_bounty_bb(path=None, *, villain_uid=None, max_age_s=MAX_AGE_S, now=None,
                   starting_stack=None, head_fraction=0.5):
    """Bounty BASE em BB (cabeça fresca) p/ o call-off escalar pelo bounty do vilão, ou None.

    Precedência: `bounty_bb` calibrado > BRIDGE por estrutura (starting_stack + head_fraction:
    moeda-prêmio -> fichas-stack via o stack inicial, CORRETO p/ PKO) > ratio chips/bb (fallback
    legado, aproximado). O bridge resolve o bug de unidade (bounty é prêmio, não stack).
    """
    data = _load(path or DEFAULT_PATH)
    if not isinstance(data, dict):
        return None
    if not _fresh(data, max_age_s, time.time() if now is None else now):
        return None
    # 1) já calibrado em BB (o emissor/operador confirmou a conversão ao vivo)
    bb = data.get('bounty_bb')
    if isinstance(bb, (int, float)) and bb > 0:
        return round(float(bb), 3)
    bb_chips = data.get('bb_chips')
    # 1.5) BRIDGE por ESTRUTURA (preferido p/ PKO): cabeça fresca em BB via o stack inicial.
    if starting_stack:
        from bounty_model import base_bb_from_structure
        base = base_bb_from_structure(starting_stack, bb_chips, head_fraction)
        if base is not None:
            return base
    # 2/3) LEGADO: converter fichas -> BB precisa do big blind (ratio aproximado, unidade incerta)
    if not isinstance(bb_chips, (int, float)) or bb_chips <= 0:
        return None
    chips = None
    players = data.get('players') or {}
    if villain_uid is not None:
        v = players.get(str(villain_uid)) or players.get(villain_uid)
        if isinstance(v, (int, float)) and v > 0:
            chips = v
    if chips is None:
        hero = data.get('hero_bounty_chips')
        if isinstance(hero, (int, float)) and hero > 0:
            chips = hero
    if chips is None and players:
        vals = [v for v in players.values() if isinstance(v, (int, float)) and v > 0]
        if vals:
            chips = sum(vals) / len(vals)            # médio como último recurso
    if chips is None:
        return None
    return round(float(chips) / float(bb_chips), 3)


def status(path=None):
    """Resumo legível p/ log/painel: fonte, frescor, calibrado."""
    data = _load(path or DEFAULT_PATH)
    if not isinstance(data, dict):
        return dict(available=False, reason='SEM_ARQUIVO')
    fresh = _fresh(data, MAX_AGE_S, time.time())
    return dict(available=True, fresh=fresh, calibrated=bool(data.get('calibrated')),
                bb_chips=data.get('bb_chips'), n_players=len(data.get('players') or {}),
                candidates=list((data.get('candidates') or {}).keys()))
