"""Caça de BOUNTY (PKO) na Suprema. A percepção (suprema_state.to_table_state) já expõe, por
assento, o bounty CRU da cabeça (`bounty_raw`) + `ko`, e o `bb_chips` da mão. Este módulo CONVERTE
o bounty -> equivalente em FICHAS DE STACK -> BB e calcula, por VILÃO que o HERO COBRE, quanto de
equity A MENOS o call precisa (via icm_rp.bounty_power), destacando o cenário do Eduardo: vilão
CURTO + bounty GRANDE na cabeça + a gente COBRE => alargar open/call pra CAÇAR.

UNIDADE (corrigido 22/11): o bounty NÃO está em fichas de stack — está na MOEDA DE BUY-IN. Ex.: um
PKO que custa 100 de entrada manda 50 pra "cabeça" (bounty) e 50 pro prize pool. Pra usar numa
decisão de poker é preciso traduzir esse valor-prêmio para o EQUIVALENTE EM FICHAS DE STACK; o elo é
o STACK INICIAL: num PKO 50/50 a metade-prêmio do buy-in "compra" 1 stack inicial, logo uma cabeça
FRESCA (0 KO) ≈ 1 stack inicial em equivalente. Daí:
    bounty_bb = bounty_raw * BOUNTY_CHIP_SCALE / bb_chips
onde BOUNTY_CHIP_SCALE = FICHAS DE STACK EQUIVALENTES por 1 unidade crua de bounty do stream.

CALIBRAÇÃO: derive o scale de scale_from_structure(stack_inicial, bounty_cru_de_cabeça_fresca).
None = NÃO calibrado -> não estima bounty (note='SEM_CALIBRACAO'), nunca chuta.
"""
from __future__ import annotations

import icm_rp

# FICHAS DE STACK equivalentes por 1 unidade crua de bounty. Calibrar (scale_from_structure).
# None = não calibrado.
BOUNTY_CHIP_SCALE = None


def set_scale(chips_per_unit):
    """Calibra o fator bounty_cru -> fichas de stack equivalentes. Falsy/0 -> desliga."""
    global BOUNTY_CHIP_SCALE
    BOUNTY_CHIP_SCALE = float(chips_per_unit) if chips_per_unit else None
    return BOUNTY_CHIP_SCALE


def scale_from_structure(starting_stack, fresh_head_raw, *, head_fraction=0.5):
    """Deriva BOUNTY_CHIP_SCALE da estrutura do PKO. `starting_stack` = fichas de stack iniciais;
    `fresh_head_raw` = valor CRU (do stream) de uma cabeça FRESCA (0 KO); `head_fraction` = fração
    do buy-in que vai pra cabeça (0.5 no PKO padrão). A metade-prêmio ((1-hf)·buyin) compra 1 stack
    inicial, então uma cabeça fresca (hf·buyin) vale  starting_stack·hf/(1-hf)  fichas de stack;
    como ela lê `fresh_head_raw` unidades cruas:
        scale = starting_stack·hf/(1-hf) / fresh_head_raw  (fichas equivalentes por unidade crua).
    No 50/50 vira starting_stack/fresh_head_raw. Não altera o global; devolve o scale p/ set_scale."""
    ss, r0, hf = _f(starting_stack), _f(fresh_head_raw), _f(head_fraction)
    if not (ss and ss > 0) or not (r0 and r0 > 0) or not (hf and 0 < hf < 1):
        return None
    return round(ss * hf / (1.0 - hf) / r0, 6)


def _f(x):
    return x if isinstance(x, (int, float)) else None


def raw_to_bb(bounty_raw, bb_chips, scale=None):
    """bounty_raw (cru) -> bounty em BB, dado o BB em fichas e o scale cru->fichas. None se
    faltar dado ou scale (nunca estima)."""
    s = scale if scale is not None else BOUNTY_CHIP_SCALE
    br, bbc = _f(bounty_raw), _f(bb_chips)
    if not (br and br > 0) or not (bbc and bbc > 0) or not (isinstance(s, (int, float)) and s > 0):
        return None
    return round((br * s) / bbc, 4)


def head_raw(collected, base):
    """CABEÇA atual de um jogador (unidades cruas) = base da cabeça do torneio + bounty ACUMULADO
    (o campo seat.bounty = cash ganho, 0 p/ fresco). None se faltar a base."""
    b, c = _f(base), (_f(collected) or 0.0)
    if not (b and b > 0):
        return None
    return b + max(0.0, c)


def bounty_targets(state, *, scale=None, base=None, short_bb=20.0):
    """Analisa a CABEÇA de cada VILÃO (= base + acumulado). Devolve lista ORDENADA pelo maior
    pot_fraction (alvo mais lucrativo de caçar). Item: seat, stack_bb, head_bb (cabeça em BB-equiv),
    ko, covers (hero cobre o vilão), short, pot_fraction (desconto de equity — só realiza se cobre),
    juicy (coberto + curto + cabeça real), note. Sem scale/base -> head_bb=None."""
    seats = state.get('seats') or {}
    bb_chips = _f(state.get('bb_chips'))
    hero = seats.get('hero') or {}
    hero_stack = _f(hero.get('stack_bb'))
    pot_bb = _f((state.get('pot') or {}).get('pot_bb')) or 0.0
    to_call_bb = _f((state.get('to_call') or {}).get('to_call_bb')) or 0.0
    out = []
    for k, s in seats.items():
        if k == 'hero' or not isinstance(s, dict):
            continue
        vstack = _f(s.get('stack_bb'))
        hr = head_raw(s.get('bounty_raw'), base)
        vb = raw_to_bb(hr, bb_chips, scale) if hr else None
        covers = bool(hero_stack is not None and vstack is not None and hero_stack >= vstack)
        short = bool(vstack is not None and vstack <= short_bb)
        if vb:
            bp = icm_rp.bounty_power(vb, hero_stack=hero_stack, villain_stack=vstack,
                                     pot_bb=pot_bb, to_call_bb=to_call_bb)
            pot_fraction, note = bp['pot_fraction'], bp['note']
        else:
            pot_fraction = 0.0
            note = 'SEM_BASE' if base in (None, 0) else ('SEM_CALIBRACAO' if scale is None else 'OK')
        out.append(dict(seat=k, stack_bb=vstack, head_bb=vb, ko=s.get('ko'),
                        covers=covers, short=short, pot_fraction=pot_fraction,
                        juicy=bool(covers and short and vb and vb > 0), note=note))
    out.sort(key=lambda d: (d['pot_fraction'], d['head_bb'] or 0.0), reverse=True)
    return out


def hunt_summary(state, *, scale=None, base=None, short_bb=20.0):
    """Resumo p/ a decisão. `best_target` = vilão COBERTO com maior pot_fraction (melhor caça);
    `best_fraction` = desconto de equity a aplicar (required_equity_icm bounty_pot_fraction);
    `juicy_shorts` = vilões curtos cobertos com cabeça (alargar open/call pra caçar)."""
    s = scale if scale is not None else BOUNTY_CHIP_SCALE
    tg = bounty_targets(state, scale=scale, base=base, short_bb=short_bb)
    covered = [t for t in tg if t['covers'] and t['head_bb']]
    best = covered[0] if covered else None
    return dict(calibrated=bool(isinstance(s, (int, float)) and s > 0 and base),
                targets=tg, best_target=best,
                best_fraction=(best['pot_fraction'] if best else 0.0),
                juicy_shorts=[t for t in tg if t['juicy']])


# ---- AUTO-resolução a partir do estado vivo (sem input manual, quando possível) ----

def tournament_base(state):
    """Base da CABEÇA fresca do torneio (R0), em unidades cruas. Lida do kodata (2×min reward),
    exposta em state['mtt']['bounty_base']. É a cabeça de um jogador com 0 KOs (fresco)."""
    return _f((state.get('mtt') or {}).get('bounty_base'))


def est_starting_stack(mtt):
    """Estima o STACK INICIAL (fichas) do game_info: total de fichas (avg_stack × vivos) dividido
    pelos buy-ins que injetaram fichas (entradas + rebuys). ESTIMATIVA (flag ss_estimated), não
    precisa — o stream não manda o stack inicial. Use override manual p/ valor exato."""
    if not isinstance(mtt, dict):
        return None
    avg, left = _f(mtt.get('avg_stack')), _f(mtt.get('players_left'))
    total, reb = _f(mtt.get('players_total')), (_f(mtt.get('rebuys')) or 0)
    if not (avg and avg > 0 and left and left > 0 and total and total > 0):
        return None
    buyins = total + reb
    return round(avg * left / buyins) if buyins > 0 else None


def resolve_starting_stack(state, override=None):
    """Resolve o STACK INICIAL + a FONTE. Prioridade: override manual > DETECTADO no começo
    (suprema_state grava o menor avgStack visto em mtt['starting_stack'] + mtt['ss_level']; nível
    1 = exato) > estimativa do game_info (ruidosa). Devolve (ss, source)."""
    mtt = state.get('mtt') or {}
    if override:
        return float(override), 'manual'
    det = _f(mtt.get('starting_stack'))
    if det and det > 0:
        lvl = mtt.get('ss_level')
        return det, ('detectado_L%s' % lvl if lvl is not None else 'detectado')
    est = est_starting_stack(mtt)
    return (est, 'estimado') if est else (None, 'nenhum')


def scale_from_state(state, *, head_fraction=0.5, starting_stack=None):
    """Monta o scale (fichas-equivalentes por unidade crua de CABEÇA) a partir do estado vivo:
    base do kodata + stack inicial (override > detectado > estimado) + head_fraction (0.5 PKO,
    0.75 super-PKO). None se faltar dado."""
    base = tournament_base(state)
    ss, _src = resolve_starting_stack(state, starting_stack)
    hf = _f(head_fraction)
    if not (base and base > 0) or not (ss and ss > 0) or not (hf and 0 < hf < 1):
        return None
    return round(ss * hf / (1.0 - hf) / base, 6)


def hunt(state, *, head_fraction=0.5, starting_stack=None, short_bb=20.0):
    """Caça de bounty AUTO a partir do estado vivo. Resolve base (kodata) + stack inicial
    (detectado no começo) + scale sozinho e devolve hunt_summary enriquecido (scale, bounty_base,
    starting_stack, ss_source, ss_estimated). head_fraction: 0.5 PKO (default), 0.75 super-PKO."""
    base = tournament_base(state)
    ss, src = resolve_starting_stack(state, starting_stack)
    sc = scale_from_state(state, head_fraction=head_fraction, starting_stack=starting_stack)
    out = hunt_summary(state, scale=sc, base=base, short_bb=short_bb)
    out.update(scale=sc, bounty_base=base, starting_stack=ss, ss_source=src,
               ss_estimated=(src == 'estimado'), head_fraction=head_fraction)
    return out
