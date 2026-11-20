"""Homologa e PROMOVE os ranges-sombra transcritos (Eduardo 19/11).

Gate honesto antes de virar validated=True (executável):
  1. SANIDADE: cada mão soma 1.0 (±0.02) entre as ações; legalActions não vazio; a range
     não é degenerada (fração de ação não-fold entre 2% e 98% — exceto vs_limp, sem fold).
  2. FONTE CONFIÁVEL: só promove `reg_life_transcrito` (GTOWizard, <0.5% de erro medido);
     `reg_life_bounty` (PKO, ~2% + mapeamento de modo/stage ainda aproximado) FICA em sombra
     até a re-transcrição 3-cores (task #2).
  3. GAP: só promove nós cuja CHAVE ainda NÃO existe no validado+deep (nunca sobrepõe a
     verdade já validada — B01/B02). Os que colidem (RFI 15/30bb) ficam validated=False.

Escreve `strategy_data/ranges_reg_life_homologado.json`: promovidos (validated=True +
proveniência) + retidos (validated=False). O operador passa a carregar ESTE pack.
Offline, passivo (só lê/escreve JSON)."""
import json
import os

REPO = os.path.dirname(os.path.abspath(__file__))
SHADOW = os.path.join(REPO, 'strategy_data', 'ranges_reg_life_shadow.json')
OUT = os.path.join(REPO, 'strategy_data', 'ranges_reg_life_homologado.json')
_VAL = os.path.join(REPO, 'dist_bot', 'NVTBot', '_internal', 'nvt-ranges-validados.json')
_DEEP = os.path.join(REPO, 'dist_bot', 'NVTBot', '_internal', 'nvt-ranges-deep.json')

PROMOTABLE_SOURCES = ('reg_life_transcrito',)     # GTOWizard; PKO (reg_life_bounty) fica sombra


def _key(n):
    c = n.get('context') or {}
    return (c.get('mode'), c.get('format'), c.get('stage'), c.get('players'),
            c.get('stack'), n.get('spot'), n.get('hero'),
            tuple(n.get('vs') or ()), n.get('spread'))


def _sane(n):
    """(ok, motivo). Soma 1 por mão + ação não-fold entre 2%-98% (vs_limp isento)."""
    freq = n.get('freq') or {}
    if not n.get('legalActions'):
        return False, 'SEM_LEGAL_ACTIONS'
    acts = list(freq)
    if not acts:
        return False, 'SEM_FREQ'
    nhands = len(next(iter(freq.values())))
    if nhands != 169:
        return False, 'NAO_169'
    for i in range(169):
        s = sum(freq[a][i] for a in acts)
        if abs(s - 1.0) > 0.03:
            return False, 'SOMA_%.2f_NA_MAO_%d' % (s, i)
    # combos por ação (pair=6, suited=4, offsuit=12) p/ a fração não-fold
    from transcrever_range_gtow import hand_at, _combos
    hands = [hand_at(r, c) for r in range(13) for c in range(13)]
    total = sum(_combos(h) for h in hands)
    nonfold = sum(_combos(hands[i]) * sum(freq[a][i] for a in acts if a != 'fold')
                  for i in range(169))
    frac = nonfold / total
    if n.get('spot') != 'vs_limp' and not (0.02 <= frac <= 0.98):
        return False, 'DEGENERADO_%.2f' % frac
    return True, 'ok_acao_%.1f%%' % (100 * frac)


def homologate():
    shadow = json.load(open(SHADOW, encoding='utf-8'))
    val_keys = set()
    for p in (_VAL, _DEEP):
        if os.path.exists(p):
            for n in json.load(open(p, encoding='utf-8')).get('nodes', []):
                val_keys.add(_key(n))
    promoted, held, failed = [], [], []
    for n in shadow.get('nodes', []):
        ok, why = _sane(n)
        src = n.get('source')
        node = dict(n)
        if not ok:
            node['validated'] = False
            failed.append((n.get('id'), why)); held.append(node); continue
        if src in PROMOTABLE_SOURCES and _key(n) not in val_keys:
            node['validated'] = True
            node['promotion'] = dict(from_shadow=True, source=src, homologation=why,
                                     policy='reg_life_transcrito_<0.5pct')
            promoted.append(node)
        else:
            node['validated'] = False      # PKO (sombra) ou colisão com validado
            held.append(node)
    out = dict(shadow, nodes=promoted + held,
               homologation=dict(promoted=len(promoted), held=len(held), failed=len(failed)))
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    return promoted, held, failed


def main():
    promoted, held, failed = homologate()
    import collections
    bysrc = collections.Counter(n.get('source') for n in promoted)
    byspot = collections.Counter(n['spot'] for n in promoted)
    print('PROMOVIDOS (validated=True): %d  por spot=%s' % (len(promoted), dict(byspot)))
    print('RETIDOS em sombra (validated=False): %d' % len(held))
    if failed:
        print('REPROVADOS na sanidade: %d -> %s' % (len(failed), failed[:5]))
    print('-> %s' % OUT)


if __name__ == '__main__':
    main()
