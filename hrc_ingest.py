"""Ingestor da biblioteca HRC -> pack `nvt-range-export` v1 (ESTUDO/sombra).

Converte os exports do HRC (range-coach-pro `public/solver/hrc/*.json`) para o
formato de nó que o `PreflopAdvisor` carrega (ver preflop_advisor._key_of /
preflop_equity.range_from_node). Cada arquivo HRC = UMA solve completa de um
contexto `(mode, format, stage, spread, stack, players)` e carrega:
  - `rfi[pos]`            -> spot 'open_raise' (raise + all_in + fold derivado)
  - `resp[opener>resp]`   -> spot 'vs_open'   (call + three_bet + all_in + fold)
  - `opv3[opener>3bet]`   -> spot 'vs_3bet'   (call + all_in + fold)
  - `limp`                -> spots 'sb_first_in' / 'vs_limp' / 'vs_iso' / 'vs_limp_jam'

POLÍTICA DE SEGURANÇA (inegociável): TODO nó entra `validated=False`
(estudo/sombra). A promoção a `validated=True` (o operador CLICA) só ocorre por
família numa sessão de HOMOLOGAÇÃO AO VIVO. Fazendo o merge DEPOIS do pack
validado (que é autoritário em colisões, ver PreflopAdvisor.__init__ B02), os
nós já homologados vencem e os novos apenas AMPLIAM a cobertura em sombra.

Puro/offline: não captura, não clica — só transforma JSON. stdlib apenas. As
169 classes são REINDEXADAS por STRING (o HRC usa outra ordem de mãos), então a
ordem interna do arquivo HRC é irrelevante.
"""
import hashlib
import json
import re
from pathlib import Path

RANKS = 'AKQJT98765432'
# Ordem canônica idêntica à do pack validado (preflop_study.RANKS + teste):
# pares AA..22, depois cada combo alto>baixo em suited e offsuit.
HANDS = ([r + r for r in RANKS] +
         [a + b + s for i, a in enumerate(RANKS) for b in RANKS[i + 1:] for s in ('s', 'o')])
HAND_SET = frozenset(HANDS)
assert len(HANDS) == 169 and len(HAND_SET) == 169

# HRC -> nosso vocabulário de ação (range_from_node seleciona o range por estes nomes).
ACTION_MAP = {'raise': 'raise', 'call': 'call', 'check': 'check', 'fold': 'fold',
              'shove': 'all_in', 'allin': 'all_in', 'three': 'three_bet', 'four': 'four_bet'}

# Posições: o HRC usa EXATAMENTE a mesma convenção do nosso strategy.scenarios.ORDER.
POSITIONS = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB')


class IngestError(Exception):
    pass


def _reindexer(hrc_hands):
    """Devolve uma função que reordena um array de 169 do HRC para a NOSSA ordem
    `HANDS`, casando por STRING. Falha se o arquivo não contém as 169 classes."""
    pos = {h: i for i, h in enumerate(hrc_hands)}
    missing = [h for h in HANDS if h not in pos]
    if missing:
        raise IngestError('HRC_HANDS_INCOMPLETAS:%s' % ','.join(missing[:6]))
    if len(hrc_hands) != 169:
        raise IngestError('HRC_HANDS_TAMANHO:%d' % len(hrc_hands))
    order = [pos[h] for h in HANDS]

    def reindex(arr):
        if arr is None:
            return None
        return [float(arr[j]) for j in order]

    return reindex


def _derive_fold(freqs):
    """freq['fold'][i] = max(0, 1 - soma das outras ações) por classe. HRC não
    exporta a frequência de fold do RFI/resposta explicitamente; deriva-se do
    complemento (as frequências de uma decisão somam 1)."""
    others = [a for a in freqs if a != 'fold']
    n = 169
    out = []
    for i in range(n):
        s = sum(freqs[a][i] for a in others)
        out.append(max(0.0, round(1.0 - s, 6)))
    return out


# ------------------------------------------------------------------ contexto

_FAMILY_RE = re.compile(
    r'^(?:hrc_)?'
    r'(chip|preitm|bubble|ft|pkoearly|pkomid)'          # fase
    r'(?:_(iguais|curtos))?'                             # spread
    r'(?:_(ini|fim))?'                                   # sub-fase (só curtos)
    r'(?:_(icm|pko))?'                                   # modelo de EV
    r'(?:_(\d+))?$')                                     # stack bucket

_STAGE = {'chip': 'early', 'preitm': 'mid', 'bubble': 'bubble', 'ft': 'ft',
          'pkoearly': 'early', 'pkomid': 'mid'}


def family_context(name, *, stacks=None):
    """Deriva o contexto do nó a partir do NOME do arquivo HRC (e, para o stack,
    do array `stacks` quando não há sufixo numérico). Devolve dict com
    mode/format/stage/players/stack/spread + rótulos de proveniência. Levanta
    IngestError para nome fora do padrão (nunca adivinha)."""
    base = name[:-5] if name.endswith('.json') else name
    m = _FAMILY_RE.match(base)
    if not m:
        raise IngestError('NOME_HRC_FORA_DO_PADRAO:%s' % name)
    phase, spread_raw, sub, ev, stack_s = m.groups()

    if phase == 'chip':
        mode, fmt = 'chip_ev', 'regular'
    elif phase in ('pkoearly', 'pkomid'):
        mode, fmt = 'pko_icm', 'pko'
    elif ev == 'pko':
        mode, fmt = 'pko_icm', 'pko'
    elif ev == 'icm':
        mode, fmt = 'icm', 'regular'
    else:
        raise IngestError('MODELO_EV_AUSENTE:%s' % name)

    # spread carrega o REGIME de stack completo p/ a chave não colidir
    # (curtos_ini e curtos_fim são contextos distintos da mesma fase).
    if spread_raw == 'curtos':
        spread = 'curtos_%s' % (sub or 'na')
    elif spread_raw == 'iguais':
        spread = 'iguais'
    else:
        spread = None

    if stack_s is not None:
        stack = int(stack_s)
    elif stacks:
        stack = int(round(float(stacks[0])))
    else:
        raise IngestError('STACK_INDETERMINADO:%s' % name)

    players = len(stacks) if stacks else 9
    return dict(mode=mode, format=fmt, stage=_STAGE[phase], players=players,
                stack=stack, spread=spread, phase=phase)


# ------------------------------------------------------------------ nós

def _node(ctx, spot, hero, vs, freq, ev, source, evunit, *, confidence='solved',
          origin='HRC'):
    acts = [a for a in freq if a != 'fold' and any(v > 0 for v in freq[a])]
    acts.append('fold')
    legal = list(acts)
    nid = '%s:%s:%s:%s:%s' % (source['name'], spot, hero, '-'.join(vs) or '_',
                              ctx['spread'] or '_')
    return dict(
        id=nid,
        context=dict(mode=ctx['mode'], format=ctx['format'], stage=ctx['stage'],
                     players=ctx['players'], stack=ctx['stack']),
        spot=spot, hero=hero, vs=list(vs), spread=ctx['spread'],
        validated=False,                      # ESTUDO/sombra até homologação ao vivo
        evUnit=evunit, legalActions=legal, actions=list(acts),
        freq={a: freq[a] for a in acts}, ev={a: ev.get(a) for a in acts if a in ev},
        source=source['name'], origin=origin, confidence=confidence)


def _rfi_nodes(data, ctx, reindex, source, evunit):
    out = []
    for pos, blk in (data.get('rfi') or {}).items():
        if pos not in POSITIONS:
            continue
        freq = {}
        for hrc_a, arr in blk.items():
            if hrc_a == 'ev' or hrc_a not in ACTION_MAP:
                continue
            freq[ACTION_MAP[hrc_a]] = reindex(arr)
        if not freq:
            continue
        freq['fold'] = _derive_fold(freq)
        ev = {ACTION_MAP.get(a, a): reindex(v) for a, v in (blk.get('ev') or {}).items()}
        out.append(_node(ctx, 'open_raise', pos, (), freq, ev, source, evunit))
    return out


def _resp_nodes(data, ctx, reindex, source, evunit, section, spot):
    out = []
    for key, blk in (data.get(section) or {}).items():
        if '>' not in key:
            continue
        opener, hero = key.split('>', 1)
        if opener not in POSITIONS or hero not in POSITIONS:
            continue
        freq = {}
        for hrc_a, arr in blk.items():
            if hrc_a in ('ev', 'resumo') or hrc_a not in ACTION_MAP:
                continue
            freq[ACTION_MAP[hrc_a]] = reindex(arr)
        if not freq:
            continue
        freq['fold'] = _derive_fold(freq)
        ev = {ACTION_MAP.get(a, a): reindex(v) for a, v in (blk.get('ev') or {}).items()}
        out.append(_node(ctx, spot, hero, (opener,), freq, ev, source, evunit))
    return out


def _limp_nodes(data, ctx, reindex, source, evunit):
    """Família de limp (só SB/BB). Estrutura HRC: cada sub-nó é {ação:{freq,ev}}.
    bbVsLimp é o nó que o advisor já consome (vs_limp)."""
    limp = data.get('limp') or {}
    specs = [('sb', 'sb_first_in', 'SB', ()),
             ('bbVsLimp', 'vs_limp', 'BB', ('SB',)),
             ('sbVsIso', 'vs_iso', 'SB', ('BB',)),
             ('bbVsLimpJam', 'vs_limp_jam', 'BB', ('SB',))]
    out = []
    for hrc_key, spot, hero, vs in specs:
        blk = limp.get(hrc_key)
        if not isinstance(blk, dict):
            continue
        freq, ev = {}, {}
        for hrc_a, sub in blk.items():
            if hrc_a not in ACTION_MAP or not isinstance(sub, dict):
                continue
            our_a = ACTION_MAP[hrc_a]
            freq[our_a] = reindex(sub.get('freq'))
            if sub.get('ev') is not None:
                ev[our_a] = reindex(sub.get('ev'))
        if not freq:
            continue
        if 'fold' not in freq:
            freq['fold'] = _derive_fold(freq)
        out.append(_node(ctx, spot, hero, vs, freq, ev, source, evunit,
                         confidence='solved', origin='HRC_limp'))
    return out


def nodes_from_file(path):
    """Lê um arquivo HRC e devolve (lista_de_nós, source_entry). Todos os nós são
    validated=False. source_entry liga cada nó à fonte exata por sha256 (B01)."""
    p = Path(path)
    raw = p.read_bytes()
    data = json.loads(raw.decode('utf-8'))
    if data.get('format') != 1:
        raise IngestError('FORMATO_HRC_DESCONHECIDO:%r' % data.get('format'))
    name = data.get('name') or p.stem
    ctx = family_context(name, stacks=data.get('stacks'))
    reindex = _reindexer(data['hands'])
    evunit = data.get('unit') or 'bb'
    source = dict(name=name, path=str(p), sha256=hashlib.sha256(raw).hexdigest(),
                  hrc_version=data.get('version'), note=data.get('note'),
                  hrc_source=data.get('source'))
    nodes = []
    nodes += _rfi_nodes(data, ctx, reindex, source, evunit)
    nodes += _resp_nodes(data, ctx, reindex, source, evunit, 'resp', 'vs_open')
    nodes += _resp_nodes(data, ctx, reindex, source, evunit, 'opv3', 'vs_3bet')
    nodes += _limp_nodes(data, ctx, reindex, source, evunit)
    return nodes, source


def build_pack(paths, *, engine_commit='HRC-ingest'):
    """Monta o pack nvt-range-export v1 (ESTUDO) a partir de vários arquivos HRC.
    Nós de MESMA chave vindos de arquivos diferentes são uma colisão real: aqui
    não resolvemos (deixamos o PreflopAdvisor registrar/decidir no load, B02) —
    mas registramos a lista de fontes para auditoria."""
    all_nodes, sources = [], []
    for path in paths:
        nodes, source = nodes_from_file(path)
        all_nodes.extend(nodes)
        sources.append(source)
    return dict(format='nvt-range-export', version=1, engineCommit=engine_commit,
                generatedAt=None, hands=list(HANDS), nodes=all_nodes,
                hrcSources=sources)


def _cli(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='Ingestor HRC -> pack de estudo nvt-range-export')
    ap.add_argument('--dir', required=True, help='pasta com os *.json do HRC')
    ap.add_argument('--glob', default='*.json')
    ap.add_argument('--out', required=True, help='arquivo de pack de saída')
    args = ap.parse_args(argv)
    paths = sorted(p for p in Path(args.dir).glob(args.glob) if p.name != 'manifest.json')
    pack = build_pack(paths)
    Path(args.out).write_text(json.dumps(pack, ensure_ascii=False), encoding='utf-8')
    print('nós=%d  fontes=%d  -> %s' % (len(pack['nodes']), len(pack['hrcSources']), args.out))
    return 0


if __name__ == '__main__':
    raise SystemExit(_cli())
