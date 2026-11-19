"""Ingere os ranges TRANSCRITOS (GTOWizard, pasta strategy_data/ranges_gtow) no roteamento
como um pack de SOMBRA nvt-range-export (validated=False), reusando hrc_ingest._node.

Preenche GAPS de bucket (12/50/70bb) onde hoje o advisor EMPRESTA o stack vizinho. Onde já
há nó VALIDADO (15/20/25/30/40bb), a colisão é resolvida pelo RangeSet a favor do validado
(B02) — o sombra nunca sobrepõe validado. Spots cobertos aqui (mapeamento limpo):
  • rfi_<pos>  -> open_raise (raise = open-raise + open-shove combinados)
  • bb_vs_sb_rfi  -> vs_open (hero BB vs SB: call / three_bet=raise+allin / fold)
  • bb_vs_sb_limp -> vs_limp (hero BB vs SB: check=call / raise=raise+allin)
PENDENTE (mapeamento de ação exige cuidado, flagado): bb_vs_sb_shove (call-off) e os PKO
(precisam de posição/stack do contexto + modo pko). Pack: strategy_data/ranges_reg_life_shadow.json.
"""
import glob
import json
import os

import hrc_ingest
from transcrever_range_gtow import hand_at

REPO = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(REPO, 'strategy_data', 'ranges_gtow')
OUT = os.path.join(REPO, 'strategy_data', 'ranges_reg_life_shadow.json')
# ORDEM row-major (AA,AKs,...,A2s,AKo,KK,...) = a ordem do bundle validado (hrc_ingest.HANDS
# é pairs-first, DIFERENTE — não serve p/ o merge). _node só guarda os arrays nesta ordem.
HANDS = [hand_at(r, c) for r in range(13) for c in range(13)]

_POS = {'utg': 'UTG', 'utg1': 'UTG+1', 'lj': 'LJ', 'hj': 'HJ', 'co': 'CO', 'btn': 'BTN', 'sb': 'SB'}
_SOURCE = {'name': 'reg_life_transcrito'}


def _arr(hands, keys):
    """Array de 169 (ordem HANDS) somando as frações das ações `keys` de cada mão."""
    return [round(sum((hands.get(h) or {}).get(a, 0.0) for a in keys), 4) for h in HANDS]


def _ctx(stack):
    return dict(mode='chip_ev', format='regular', stage='mid', players=9, stack=stack, spread=None)


def _node_rfi(data):
    pos = _POS.get(data['spot'].replace('rfi_', ''))
    if not pos:
        return None
    freq = {'raise': _arr(data['hands'], ['raise', 'allin'])}
    freq['fold'] = hrc_ingest._derive_fold(freq)
    return hrc_ingest._node(_ctx(data['stack_bb']), 'open_raise', pos, (), freq, {}, _SOURCE, 'bb')


def _node_bb_vs_sb_rfi(data):
    freq = {'call': _arr(data['hands'], ['call']),
            'three_bet': _arr(data['hands'], ['raise', 'allin'])}
    freq['fold'] = hrc_ingest._derive_fold(freq)
    return hrc_ingest._node(_ctx(data['stack_bb']), 'vs_open', 'BB', ('SB',), freq, {}, _SOURCE, 'bb')


def _node_bb_vs_sb_limp(data):
    freq = {'check': _arr(data['hands'], ['call']),
            'raise': _arr(data['hands'], ['raise', 'allin'])}
    # vs_limp do BB: fold não existe (o BB já pagou); check fecha. Normaliza check p/ somar 1.
    tot = [c + r for c, r in zip(freq['check'], freq['raise'])]
    freq['check'] = [round(c + max(0.0, 1.0 - t), 4) for c, t in zip(freq['check'], tot)]
    freq['fold'] = [0.0] * len(HANDS)             # vs_limp do BB não folda (já pagou)
    return hrc_ingest._node(_ctx(data['stack_bb']), 'vs_limp', 'BB', ('SB',), freq, {}, _SOURCE, 'bb')


_BUILDERS = {'bb_vs_sb_rfi': _node_bb_vs_sb_rfi, 'bb_vs_sb_limp': _node_bb_vs_sb_limp}
_DEFER = ('bb_vs_sb_shove',)


def build_nodes():
    nodes, defer = [], []
    for path in sorted(glob.glob(os.path.join(SRC, '*.json'))):
        data = json.load(open(path, encoding='utf-8'))
        spot = data.get('spot', '')
        if spot in _DEFER:
            defer.append(os.path.basename(path)); continue
        try:
            if spot.startswith('rfi_'):
                node = _node_rfi(data)
            else:
                node = (_BUILDERS.get(spot) or (lambda d: None))(data)
        except Exception as e:                       # noqa: BLE001
            defer.append('%s (ERRO %s)' % (os.path.basename(path), e)); continue
        if node:
            nodes.append(node)
        else:
            defer.append(os.path.basename(path))
    return nodes, defer


def main():
    nodes, defer = build_nodes()
    pack = dict(format='nvt-range-export', version=1, engineCommit='reg-life-transcrito',
                generatedAt=None, hands=list(HANDS), nodes=nodes, source='reg_life_transcrito')
    json.dump(pack, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print('nós de sombra: %d  -> %s' % (len(nodes), OUT))
    import collections
    byspot = collections.Counter(n['spot'] for n in nodes)
    print('por spot:', dict(byspot))
    if defer:
        print('DEFERIDOS (%d, p/ depois):' % len(defer), defer)


if __name__ == '__main__':
    main()
