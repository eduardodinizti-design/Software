"""Risk Premium (ICM) + Risk Advantage + Bounty Power — modelo de REFERÊNCIA calibrado.

Aproximação explícita (NÃO é um solver de ICM), calibrada pelos números de estudo da
skill poker-icm-mtt: RP por fração de field (stacks iguais) 75%→2,2%, 50%→3,5%,
25%→7,9%, bolha ITM→13,5%, mesa final/semi→~11–12%; e a assimetria de cobertura (RP
vem em PARES — quem COBRE tem RP menor, quem é COBERTO tem RP maior).

RP = equity extra (em frações, ex. 0.135 = +13,5 pontos) exigida ALÉM das pot odds para
PAGAR um all-in. Chip EV = 0. Bounty (PKO) vira DESCONTO (pode deixar o RP negativo).

Calibração da cobertura (exemplo da skill, bolha, BTN 39bb vs BB 16bb):
  - BTN cobre BB -> coverage_factor = 16/39 = 0,41 -> RP ≈ 13,5%×0,41 ≈ 5,5% (skill: 5,2%).
  - BB coberto pelo BTN -> factor = min(1, 39/16) = 1 -> RP ≈ 13,5% (skill: 12,6%).
Modelo: coverage_factor = min(1, villain_stack / hero_stack). Quem cobre arrisca só o
stack do vilão (sobrevive) -> RP reduzido; quem é coberto arrisca o próprio stack (busta)
-> RP cheio. Bate bem com a referência.
"""

# RP base (stacks iguais) por FRAÇÃO de field restante. Interpolado linearmente.
_FIELD_RP = [(1.00, 0.020), (0.75, 0.022), (0.50, 0.035), (0.25, 0.079), (0.0, 0.135)]
# RP base por ESTÁGIO nomeado (quando não há fração de field). Bolha ITM é o pico.
_STAGE_RP = {'pre_itm': 0.05, 'bubble': 0.135, 'ft': 0.115, 'mid': 0.035}
RP_CAP = 0.30                         # teto de segurança (20%+ já é extremo; 30% trava)
PKO_RP_SCALE = 0.6                    # bounty alivia a pressão ICM pura (antes do desconto)


def stage_base_rp(stage, field_fraction=None):
    """RP base (stacks iguais) da fase. `field_fraction` (0=bolha ITM .. 1=início) tem
    prioridade e é interpolado; senão usa o bucket do estágio."""
    if isinstance(field_fraction, (int, float)):
        x = max(0.0, min(1.0, field_fraction))
        pts = _FIELD_RP
        for (x1, y1), (x0, y0) in zip(pts, pts[1:]):   # pts desc em x
            if x0 <= x <= x1:
                t = 0.0 if x1 == x0 else (x - x0) / (x1 - x0)
                return round(y0 + t * (y1 - y0), 4)
        return _FIELD_RP[-1][1]
    return _STAGE_RP.get(stage, 0.05)


def coverage_factor(hero_stack, villain_stack):
    """min(1, villain/hero): <1 quando o HERO cobre (sobrevive ao perder), 1 quando é
    coberto/igual (busta). None de stack -> 1.0 (conservador: assume coberto)."""
    if not isinstance(hero_stack, (int, float)) or hero_stack <= 0:
        return 1.0
    if not isinstance(villain_stack, (int, float)) or villain_stack <= 0:
        return 1.0
    return round(min(1.0, villain_stack / hero_stack), 4)


def risk_premium(mode, stage, *, hero_stack=None, villain_stack=None, to_call_bb=None,
                 field_fraction=None):
    """RP efetivo (ICM) p/ o hero PAGAR, dado o par de stacks. 0 em chip EV. Escala a
    base da fase pela cobertura. PKO multiplica por PKO_RP_SCALE (bounty alivia; o
    desconto do bounty em si vem de `bounty_power`). Bounded em [0, RP_CAP]."""
    if mode not in ('icm', 'pko_icm'):
        return 0.0
    base = stage_base_rp(stage, field_fraction)
    if hero_stack is not None and villain_stack is not None:
        base *= coverage_factor(hero_stack, villain_stack)
    elif isinstance(to_call_bb, (int, float)) and isinstance(hero_stack, (int, float)) and hero_stack > 0:
        base *= max(0.0, min(1.0, to_call_bb / hero_stack))   # proxy antigo, sem stack do vilão
    if mode == 'pko_icm':
        base *= PKO_RP_SCALE
    return round(max(0.0, min(RP_CAP, base)), 4)


def risk_advantage(stage, hero_stack, villain_stack, *, field_fraction=None):
    """Par de RP entre hero e vilão + vantagem. `advantage` = RP do vilão contra o hero −
    RP do hero contra o vilão; POSITIVO = o HERO pode pressionar (o vilão sente mais)."""
    base = stage_base_rp(stage, field_fraction)
    rp_hero = round(min(RP_CAP, base * coverage_factor(hero_stack, villain_stack)), 4)
    rp_vill = round(min(RP_CAP, base * coverage_factor(villain_stack, hero_stack)), 4)
    return dict(rp_hero_vs_villain=rp_hero, rp_villain_vs_hero=rp_vill,
                advantage=round(rp_vill - rp_hero, 4),
                hero_covers=bool(isinstance(hero_stack, (int, float))
                                 and isinstance(villain_stack, (int, float))
                                 and hero_stack > villain_stack))


def bounty_power(bounty_bb, *, hero_stack, villain_stack, pot_bb, to_call_bb):
    """Poder do bounty: só se realiza quando o HERO COBRE o vilão (vencer ELIMINA e leva o
    bounty). Devolve a FRAÇÃO de pote extra que o bounty representa (a somar ao pote nas
    pot odds, não ao RP — evita dupla contagem), + `covers` e nota. Vilão cobre o hero ->
    0 (não elimina ninguém pagando). Modelo conservador."""
    out = dict(covers=False, pot_fraction=0.0, bounty_bb=bounty_bb, note=None)
    if not isinstance(bounty_bb, (int, float)) or bounty_bb <= 0:
        out['note'] = 'SEM_BOUNTY'
        return out
    covers = (isinstance(hero_stack, (int, float)) and isinstance(villain_stack, (int, float))
              and hero_stack >= villain_stack)
    if not covers:
        out['note'] = 'VILAO_COBRE_HERO_NAO_ELIMINA'
        return out
    base_pot = (pot_bb or 0) + (to_call_bb or 0)
    if base_pot <= 0:
        out['note'] = 'POTE_DESCONHECIDO'
        return out
    out.update(covers=True, pot_fraction=round(bounty_bb / base_pot, 4),
               note='BOUNTY_POT_FRACTION_%.2f' % (bounty_bb / base_pot))
    return out


def required_equity_icm(pot_odds, rp, *, bounty_pot_fraction=0.0):
    """Equity mínima p/ pagar, com ICM e bounty. pot_odds + rp, e o bounty DESCONTA (o
    pote efetivo cresce): aproxima (to_call)/(pote+to_call+bounty). Como atalho sobre a
    pot_odds já dada: req = max(0, pot_odds×(1 − bounty_pot_fraction) + rp), clamp [0,1]."""
    if pot_odds is None:
        return None
    req = pot_odds * (1.0 - max(0.0, min(1.0, bounty_pot_fraction))) + (rp or 0.0)
    return round(max(0.0, min(1.0, req)), 4)
