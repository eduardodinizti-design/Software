"""Sombra de solver pós-flop — estudo SB x BB 40bb SINGLE-RAISED (SHADOW, NUNCA executa).

Contexto (do estudo do outro agente): HU, SB abre 2bb, BB paga, ~40bb efetivos,
pote single-raised, chip-EV, menu bet 1/3 + all-in, max 2 raises. gap native ~0,049bb.
O cérebro consulta como SOMBRA (grading por frequência, execution_allowed=False), igual
ao `solver_pr12_shadow`/`solver_cbet_shadow`. A própria fonte marca
`LAB_POLICY_REQUIRES_WINDOWS_EXECUTION_VALIDATION`.

AMOSTRAGEM INCREMENTAL: o pack (`sb40_srp_shadow.json.gz`) acumula leva a leva (17
mãos, depois +17...) até ser fidedigno (ver `ingest_sb40.py`). Hoje é PARCIAL (só
mãos-prova) — a cobertura cresce sem tocar neste módulo nem no cérebro.

Nós: FLOP com SB OOP agindo primeiro = história vazia (''). Turn/river exigem o
histórico de apostas pós-flop (como no pr12), então ao vivo só o FLOP (raiz) é
casável; turn/river ficam p/ estudo/auditoria.
"""
import gzip
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(_HERE, 'strategy_data', 'postflop_solver', 'sb40_srp_shadow.json.gz')

# Contexto exato em que esta sombra vale (casar ANTES de consultar).
CONTEXT = dict(positions=('SB', 'BB'), pot_type='single_raised', mode='chip_ev',
               stack_bb=40, stage='mid')
STACK_TOL_BB = 6          # 40bb ± tolerância p/ casar o efetivo ao vivo

_PACK = None


def load_pack(path=None):
    global _PACK
    if _PACK is None or path is not None:
        p = path or DATA
        if not os.path.exists(p):
            _PACK = dict(schema='nvt-sb40-srp-shadow.v1', flops={}, context=None, menu=None)
        else:
            with gzip.open(p, 'rt', encoding='utf-8') as fh:
                _PACK = json.load(fh)
    return _PACK


def _combo(hero_cards):
    """Duas cartas -> combo canônico (ordenado), ex.: ['Kc','2d'] -> '2dKc'."""
    cs = [c for c in (hero_cards or []) if isinstance(c, str) and len(c) == 2]
    if len(cs) != 2:
        return None
    return ''.join(sorted(cs))


def _flop_key(board_cards):
    """3 cartas do flop -> chave canônica (ordenada) p/ casar com o pack."""
    cs = [c for c in (board_cards or [])[:3] if isinstance(c, str) and len(c) == 2]
    if len(cs) != 3:
        return None
    return ''.join(sorted(cs))


def context_matches(positions, pot_type, mode, stack_bb):
    """True se o spot ao vivo é SB x BB 40bb single-raised chip-EV (onde a sombra vale)."""
    try:
        pos = tuple(positions or ())
        if set(pos) != set(CONTEXT['positions']):
            return False
        if pot_type is not None and pot_type != CONTEXT['pot_type']:
            return False
        if mode is not None and mode != CONTEXT['mode']:
            return False
        if isinstance(stack_bb, (int, float)) and abs(stack_bb - CONTEXT['stack_bb']) > STACK_TOL_BB:
            return False
        return True
    except Exception:
        return False


def _lookup(street, hero_cards, board_cards, history=''):
    pack = load_pack()
    fk = _flop_key(board_cards)
    combo = _combo(hero_cards)
    if not fk or not combo:
        return None
    # casa a chave de flop canônica contra os flops do pack (que guardam o board exato)
    for stored_fkey, fe in pack.get('flops', {}).items():
        if _flop_key(fe.get('board')) != fk:
            continue
        node = (fe.get('streets', {}).get(street, {}) or {}).get(history)
        if not node:
            return None
        hit = node.get(combo)
        if hit:
            return dict(street=street, combo=combo, board=fe.get('board'),
                        action_id=hit.get('action_id'), candidates=hit.get('candidates'),
                        execution_allowed=False, source='sb40_srp_shadow',
                        caveats=['HU_CHIP_EV_COMPILED_POLICY_SHADOW',
                                 'LAB_POLICY_REQUIRES_WINDOWS_EXECUTION_VALIDATION',
                                 'AMOSTRAGEM_PARCIAL'])
    return None


def flop_policy(hero_cards, board_cards):
    """Política de FLOP (SB OOP, raiz = 1º a agir) p/ o combo do hero, ou None se o
    flop/combo não estão na amostra atual. SHADOW: execution_allowed=False."""
    return _lookup('flop', hero_cards, board_cards, history='')


def coverage():
    pack = load_pack()
    flops = pack.get('flops', {})
    pts = sum(len(ne) for fe in flops.values()
              for se in fe.get('streets', {}).values() for ne in se.values())
    return dict(flops=len(flops), points=pts, batches=len(pack.get('batches') or []),
                context=pack.get('context'), menu=pack.get('menu'))
