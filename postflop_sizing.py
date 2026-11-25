"""Sizing de APOSTA pós-flop no vocabulário do NOSSO slider (Eduardo 19/11).

O Henrique só clica 1/3, 1/2, 2/3 e all-in no pós-flop ([[nvt-posflop-sizes-nosso-slider]]).
Este módulo é o passo FINAL que, para toda recomendação de `bet` pós-flop (venha da
heurística ou dirigida pelo solver), encaixa o size num desses buckets — traduzindo a
fração do pote pelo valor real — e grava `bucket`/`size_bb`. Idempotente.

ÚNICA exceção à regra fixa = Plano Geométrico por street ([[nvt-plano-geometrico-street]]):
no TURN, com SPR alto, usa o size geométrico (postflop_adjustments.geometric_street_plan)
pra encaixar o shove no river — pode passar de 2/3, mas com lógica (limitado pelo SPR).

PURO: sem captura, sem clique. Só anota o alvo; quem executa é o operador/sequenciador.
Não mexe em `execution_allowed`. Só atua em `recommended=='bet'` (o raise pós-flop tem
base própria — raise-to — e não é fração de pote)."""
import postflop_adjustments as _pa

# NOSSO slider (fração do pote). All-in é tratado à parte.
BUCKETS = (('1/3', 1.0 / 3.0), ('1/2', 0.5), ('2/3', 2.0 / 3.0))
GEO_TURN_SPR_MIN = 1.5          # SPR a partir do qual o turn vira geométrico
ALLIN_COMMIT_FRAC = 0.9         # size >= 90% do stack -> vira all-in (sem stub ridículo)


def snap_fraction(frac):
    """Fração arbitrária -> (rótulo, fração) do bucket mais próximo do nosso slider."""
    return min(BUCKETS, key=lambda b: abs(b[1] - frac))


def enforce(advice, *, pot_bb=None, stack_bb=None, spr=None):
    """Encaixa o size de um `bet` pós-flop no nosso slider (ou geométrico no turn).
    Muta e devolve `advice`. No-op fora de bet pós-flop ADVICE, ou se já encaixado."""
    if not isinstance(advice, dict):
        return advice
    if advice.get('phase') != 'postflop' or advice.get('status') != 'ADVICE':
        return advice
    if (advice.get('recommended') or '').lower() != 'bet':
        return advice                                   # só aposta (raise tem base própria)
    sz = dict(advice.get('sizing') or {})
    if sz.get('bucket_enforced'):
        return advice                                   # idempotente
    pot = pot_bb if pot_bb is not None else advice.get('pot_bb')
    street = (advice.get('street') or '').upper()
    if spr is None:
        spr = advice.get('spr')
    cur = sz.get('size_bb')

    # Fração-base: do sizing (fraction) ou de size_bb/pote; default 1/2.
    frac = sz.get('fraction')
    if frac is None and isinstance(cur, (int, float)) and isinstance(pot, (int, float)) and pot > 0:
        frac = cur / pot
    if frac is None:
        frac = 0.5

    geo_plan = None
    size = cur
    bucket = None
    # --- EXCEÇÃO: Plano Geométrico no TURN (SPR alto) ---
    if (street == 'TURN' and isinstance(spr, (int, float)) and spr >= GEO_TURN_SPR_MIN
            and isinstance(pot, (int, float)) and pot > 0
            and isinstance(stack_bb, (int, float)) and stack_bb > 0):
        plan = _pa.geometric_street_plan(spr, 'TURN', pot, stack_bb)
        if plan:
            geo_plan = plan
            size = plan[0]['bet_bb']
            bucket = 'geo'
            frac = round(size / pot, 2) if pot else frac

    # --- Regra fixa: encaixa no bucket mais próximo ---
    if bucket is None:
        label, bfrac = snap_fraction(frac)
        frac = bfrac
        bucket = label
        if isinstance(pot, (int, float)):
            size = round(pot * frac, 1)

    # --- All-in commit: não deixa stub (ex.: betar 95% e sobrar 5%) ---
    if (isinstance(size, (int, float)) and isinstance(stack_bb, (int, float)) and stack_bb > 0
            and size >= ALLIN_COMMIT_FRAC * stack_bb):
        size = round(stack_bb, 1)
        bucket = 'allin'

    sz.update(size_bb=size, bucket=bucket,
              fraction=(round(frac, 2) if isinstance(frac, (int, float)) else frac),
              bucket_enforced=True)
    if geo_plan:
        sz['geometric_plan'] = geo_plan
    advice['sizing'] = sz
    advice.setdefault('caveats', [])
    tag = 'POSTFLOP_SIZE_%s' % str(bucket).upper().replace('/', '_')
    if tag not in advice['caveats']:
        advice['caveats'].append(tag)
    if bucket == 'geo' and 'POSTFLOP_SIZE_GEOMETRICO_TURN' not in advice['caveats']:
        advice['caveats'].append('POSTFLOP_SIZE_GEOMETRICO_TURN')
    return advice
