"""Ingestor de ARVORE HoldemResources (export .zip: settings.json + nodes/*.json)
-> pack `nvt-range-export` v1 (ESTUDO/sombra). Complementa hrc_ingest.py, que lê
o JSON range-coach-pro (rfi/resp/opv3) e NAO emite os spots de SHOVE separados.

Estes exports de arvore sao solves de PUSH/FOLD (`Npf_*`) e RESTEAL (`Nresteal_*`):
cada nodes/N.json e um no da arvore de jogo com `player` (assento 0-8 = UTG..BB),
`street` (0=preflop), `sequence` (historico de acoes), `actions` ([{type,amount,
node}], index i <-> played[i]) e `hands` (169 classes -> {weight, played[], evs[]}).

Classificacao do SPOT pela `sequence` (so street preflop, sem limps/calls antes):
  - 0 raises antes, hero age first-in, acoes = {F, R=jam} -> OPEN_SHOVE   (vs=())
  - 1 raise antes e era JAM  -> hero da shove-or-fold por cima   -> VS_OPEN_SHOVE (vs=O)
  - 1 raise antes e era OPEN -> hero 3bet-JAM (resteal)          -> 3BET_SHOVE    (vs=O)
Um R e JAM se amount >= 0.9 * stack do raiser. Nos com >=2 raises (4bet+) ou com
open_raise nao-jam (F+minR+jam first-in) sao IGNORADOS (nao sao spot de shove;
o open_raise vem do rcp via hrc_ingest).

Contexto (mode/format/stage/spread) vem do NOME; o STACK bucket vem do stack do
HERO naquele assento (stacks[player]/bb), por isso UM arquivo curtos rende varios
buckets curtos. TODO no entra validated=False (estudo). Puro/offline, stdlib.
"""
import hashlib
import json
import re
import zipfile
from pathlib import Path

from hrc_ingest import HANDS, HAND_SET          # mesma ordem canonica de 169 classes

STACK_BUCKETS = (5, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 80, 100)
POSITIONS = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB')
JAM_FRAC = 0.9          # R >= 0.9*stack do raiser conta como all-in


class TreeIngestError(Exception):
    pass


def _snap_bucket(bb_stack):
    """Bucket solved mais proximo; empate -> o MENOR (jam levemente mais tight = seguro)."""
    return min(STACK_BUCKETS, key=lambda s: (abs(s - bb_stack), s))


# ------------------------------------------------------------------ contexto pelo nome
_NAME_RE = re.compile(
    r'^(?:hand\s*\d*)?'                                  # prefixo "Hand NN" opcional
    r'(npf|nresteal)_'                                   # familia (informativo)
    r'(chip|icm|pko)'                                    # modelo de EV
    r'(?:_(early|mid|preitm|bubble|ft))?'                # fase (ausente em chip<bb>)
    r'(?:_(curtosfim|curtosini))?'                       # spread curtos
    r'(?:_?(\d+))?'                                      # stack bucket numerico
    r'(?:[a-z]+)?$')                                     # sufixo variante (b/c/d/fp/...)

_STAGE = {'early': 'early', 'mid': 'mid', 'preitm': 'pre_itm', 'bubble': 'bubble', 'ft': 'ft'}


def context_from_name(name):
    """(mode, fmt, stage, spread) a partir do nome do arquivo. Levanta se fora do
    padrao (nunca adivinha). stage/ spread seguem a convencao do pack validado."""
    base = name.lower().strip()
    base = base[:-4] if base.endswith('.zip') else base
    m = _NAME_RE.match(base)
    if not m:
        raise TreeIngestError('NOME_ARVORE_FORA_DO_PADRAO:%s' % name)
    _fam, ev, phase, spread_raw, _stk = m.groups()
    if ev == 'chip':
        mode, fmt = 'chip_ev', 'regular'
        stage = _STAGE.get(phase or 'mid', 'mid')        # chip resteal = 'mid' (como o pack validado)
        spread = None
    elif ev == 'icm':
        mode, fmt = 'icm', 'regular'
        if phase is None:
            raise TreeIngestError('ICM_SEM_FASE:%s' % name)
        stage = _STAGE[phase]
        spread = ('curtos_fim' if spread_raw == 'curtosfim'
                  else 'curtos_ini' if spread_raw == 'curtosini' else 'iguais')
    elif ev == 'pko':
        if phase in ('early', 'mid', None):
            mode, fmt, stage = 'pko', 'pko', 'mid'
            spread = None
        else:                                            # bubble/ft -> pko_icm staged
            mode, fmt, stage = 'pko_icm', 'pko', _STAGE[phase]
            spread = ('curtos_fim' if spread_raw == 'curtosfim'
                      else 'curtos_ini' if spread_raw == 'curtosini' else 'iguais')
    else:
        raise TreeIngestError('MODELO_EV_DESCONHECIDO:%s' % name)
    return mode, fmt, stage, spread


# ------------------------------------------------------------------ leitura da arvore
def _read_tree(zpath):
    """Devolve (nodes_by_index, stacks, bb). Le settings.json + nodes/*.json do zip."""
    z = zipfile.ZipFile(zpath)
    names = set(z.namelist())
    if 'settings.json' not in names:
        raise TreeIngestError('SEM_SETTINGS:%s' % zpath)
    s = json.loads(z.read('settings.json'))
    hd = s.get('handdata') or {}
    stacks = hd.get('stacks') or []
    blinds = hd.get('blinds') or []
    if not stacks or not blinds:
        raise TreeIngestError('SETTINGS_INCOMPLETO:%s' % zpath)
    bb = float(max(blinds))
    nodes = {}
    for n in names:
        m = re.match(r'nodes/(\d+)\.json$', n)
        if m:
            nodes[int(m.group(1))] = json.loads(z.read(n))
    return nodes, [float(x) for x in stacks], bb


def _hands_freq(node, actions_idx):
    """Para cada acao (por indice), devolve array de 169 com a freq daquela acao
    (played[i]) reindexado para a NOSSA ordem HANDS. Classes ausentes -> 0."""
    hands = node.get('hands') or {}
    freqs = {ai: [0.0] * 169 for ai in actions_idx}
    for pos, hkey in enumerate(HANDS):
        blk = hands.get(hkey)
        if not blk:
            continue
        played = blk.get('played') or []
        for ai in actions_idx:
            if ai < len(played):
                freqs[ai][pos] = float(played[ai])
    return freqs


def _classify(node, stacks, bb):
    """Devolve (spot, hero_pos, vs_tuple, jam_action_index, fold_action_index) ou None
    se o no nao e um spot de shove extraivel."""
    if node.get('street') != 0:
        return None
    seq = node.get('sequence') or []
    if any(a.get('type') == 'C' for a in seq):           # limp/flat antes -> fora de escopo
        return None
    raises = [a for a in seq if a.get('type') == 'R']
    if len(raises) >= 2:
        return None                                      # 4bet+ fora de escopo
    player = node.get('player')
    if not isinstance(player, int) or not (0 <= player < len(POSITIONS)):
        return None
    acts = node.get('actions') or []
    # SO spot de shove PURO = decisao BINARIA {fold, all-in}. Nos com 3 acoes
    # (F/C/R = call-off-ou-rejam, ou F/min-open/jam) NAO sao shove puro: a massa
    # da acao de CALL/open ficaria de fora e a freq nao somaria 1 (bug real que
    # colocou AA jam=0 no pack). Facing-all-in (F/C) e CALL-OFF, tratado por equity
    # ao vivo, nao range de jam. Exige exatamente 2 acoes.
    if len(acts) != 2:
        return None
    fold_i = next((i for i, a in enumerate(acts) if a.get('type') == 'F'), None)
    hero_stack = stacks[player] if player < len(stacks) else 0.0
    jam_i = next((i for i, a in enumerate(acts)
                  if a.get('type') == 'R' and a.get('amount', 0) >= JAM_FRAC * hero_stack), None)
    if fold_i is None or jam_i is None:
        return None
    hero = POSITIONS[player]
    if len(raises) == 0:
        return ('open_shove', hero, (), jam_i, fold_i)
    # 1 raise antes (opener)
    opener = raises[0].get('player')
    if not isinstance(opener, int) or not (0 <= opener < len(POSITIONS)):
        return None
    opener_stack = stacks[opener] if opener < len(stacks) else 0.0
    opener_jam = raises[0].get('amount', 0) >= JAM_FRAC * opener_stack
    spot = 'vs_open_shove' if opener_jam else '3bet_shove'
    return (spot, hero, (POSITIONS[opener],), jam_i, fold_i)


def nodes_from_tree(zpath):
    """Extrai os nos de shove (open_shove/vs_open_shove/3bet_shove) de um export de
    arvore HRC. Devolve (lista_de_nos, source). Dedup por (spot,hero,vs,bucket):
    mantem o primeiro (caminho canonico). validated=False."""
    p = Path(zpath)
    raw = p.read_bytes()
    name = p.stem                                        # "Hand Npf_icm_bubble_curtosfim"
    mode, fmt, stage, spread = context_from_name(re.sub(r'^hand\s*\d*', '', name.lower()).lstrip(' _')
                                                 or name.lower())
    nodes_by_idx, stacks, bb = _read_tree(zpath)
    source = dict(name=name, path=str(p), sha256=hashlib.sha256(raw).hexdigest(),
                  tree_nodes=len(nodes_by_idx))
    out, seen = [], {}
    for idx in sorted(nodes_by_idx):
        node = nodes_by_idx[idx]
        cl = _classify(node, stacks, bb)
        if cl is None:
            continue
        spot, hero, vs, jam_i, fold_i = cl
        player = node['player']
        bucket = _snap_bucket(stacks[player] / bb)
        key = (spot, hero, vs, bucket)
        if key in seen:
            continue
        seen[key] = True
        acts = node['actions']
        freqs = _hands_freq(node, [jam_i, fold_i])
        freq = {'all_in': freqs[jam_i], 'fold': freqs[fold_i]}
        # GUARDA: jam+fold tem que capturar ~toda a massa por classe (senao havia
        # uma 3a acao e o no nao e shove puro -> descarta; nunca entra freq que
        # nao soma 1 no cerebro).
        if any(abs(freq['all_in'][i] + freq['fold'][i] - 1.0) > 0.02 for i in range(169)):
            continue
        # EV por acao (opcional) na nossa ordem
        ev = {}
        hands = node.get('hands') or {}
        for our_a, ai in (('all_in', jam_i), ('fold', fold_i)):
            col = [0.0] * 169
            got = False
            for pos, hkey in enumerate(HANDS):
                blk = hands.get(hkey)
                evs = (blk or {}).get('evs') or []
                if ai < len(evs):
                    col[pos] = float(evs[ai]); got = True
            if got:
                ev[our_a] = col
        nid = '%s:%s:%s:%s:%d' % (name, spot, hero, '-'.join(vs) or '_', bucket)
        out.append(dict(
            id=nid,
            context=dict(mode=mode, format=fmt, stage=stage, players=len(stacks), stack=bucket),
            spot=spot, hero=hero, vs=list(vs), spread=spread,
            validated=False, evUnit='bb', legalActions=['all_in', 'fold'],
            actions=['all_in', 'fold'], freq=freq, ev=ev,
            source=name, origin='HRC_tree', confidence='solved'))
    return out, source


def build_pack(paths, *, engine_commit='HRC-tree-ingest'):
    all_nodes, sources = [], []
    for path in paths:
        try:
            nodes, source = nodes_from_tree(path)
        except TreeIngestError as e:
            print('  PULADO %s: %s' % (Path(path).name, e))
            continue
        all_nodes.extend(nodes)
        sources.append(source)
    return dict(format='nvt-range-export', version=1, engineCommit=engine_commit,
                generatedAt=None, hands=list(HANDS), nodes=all_nodes, hrcTreeSources=sources)


def _cli(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='Ingestor de arvore HRC (push/fold + resteal) -> pack de estudo')
    ap.add_argument('--dir', required=True)
    ap.add_argument('--glob', default='*.zip')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    paths = sorted(Path(args.dir).glob(args.glob))
    pack = build_pack(paths)
    Path(args.out).write_text(json.dumps(pack, ensure_ascii=False), encoding='utf-8')
    print('nos=%d  fontes=%d  -> %s' % (len(pack['nodes']), len(pack['hrcTreeSources']), args.out))
    return 0


if __name__ == '__main__':
    raise SystemExit(_cli())
