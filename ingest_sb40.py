"""Ingestor do estudo SB x BB 40bb (single-raised) -> pack de SHADOW destilado.

Lê o bundle de evidências publicado (evidencias-sb40-next16-*.zip), que contém,
por flop (case), as consultas/respostas de política por rua (request/response
flop|turn|river) das mãos-prova. Destila para o formato de pack que o cérebro
consome (solver_sb40_shadow). O MESMO schema é o que o agente dono dos 59GB deve
exportar CHEIO (todos os combos por nó) — aqui preenchemos só as mãos-prova
(parcial, honesto), e o pack escala sem mudar o cérebro quando o destilado completo
chegar.

INCREMENTAL: cada leva traz +17 mãos (depois +17, +17...) até amostragem fidedigna.
O pack ACUMULA — rodar de novo apontando pro MESMO pack mergeia os novos pontos de
política (combo@nó) sem perder os antigos. Dedup por (flop, rua, nó, combo).

Uso: python -I ingest_sb40.py <evidencias.zip> <pack.json.gz>
     (se <pack.json.gz> já existe, MERGEIA a nova leva nele.)
Passivo: só lê o zip (dado não-confiável) e escreve o pack. Não executa nada dele.
"""
import gzip
import io
import json
import sys
import zipfile


SCHEMA = 'nvt-sb40-srp-shadow.v1'


def _hist_key(state):
    """Chave do nó = histórico de ações pós-flop, no formato '<actor>:<kind>:<amt>'
    (igual ao banco do solver). Vazio = raiz da rua (primeiro a agir)."""
    h = (state or {}).get('history') or []
    out = []
    for step in h:
        if isinstance(step, str):
            out.append(step)
        elif isinstance(step, dict):
            out.append('%s:%s:%s' % (step.get('actor'), step.get('kind') or step.get('action'),
                                     step.get('amount') or step.get('additional_bb') or 0))
    return '|'.join(out)


def _candidates(resp):
    """Extrai [[action, freq, size_bb], ...] da resposta de política."""
    dec = (resp or {}).get('decision') or {}
    out = []
    for c in dec.get('candidates') or []:
        freq = c.get('frequency')
        if freq is None:
            freq = c.get('selection_frequency')
        size = c.get('raise_to_bb')
        if size is None:
            size = c.get('additional_bb')
        out.append([c.get('action'), round(float(freq or 0.0), 6),
                    (round(float(size), 3) if size is not None else None)])
    return dict(action_id=dec.get('action_id'), combo=dec.get('combo'), candidates=out)


def _empty_pack():
    return dict(schema=SCHEMA, context=None, menu=None, source='evidencias-sb40-next16',
                note='AMOSTRAGEM INCREMENTAL: cada leva traz +17 maos. Acumula ate ser '
                     'fidedigno. Formato = o que o dono dos 59GB exporta cheio (todos os '
                     'combos por no). execution_allowed=False (shadow).',
                batches=[], flops={})


def ingest(evidencias_zip, base_pack=None):
    z = zipfile.ZipFile(evidencias_zip)
    pack = base_pack if isinstance(base_pack, dict) and base_pack.get('flops') is not None \
        else _empty_pack()
    added = 0
    hist_names = [n for n in z.namelist() if n.endswith('json-history.zip')
                  and 'next16' in n]
    for hn in sorted(hist_names):
        hz = zipfile.ZipFile(io.BytesIO(z.read(hn)))
        inner = set(hz.namelist())
        for street in ('flop', 'turn', 'river'):
            rq_n, rs_n = 'request-%s.json' % street, 'response-%s.json' % street
            if rq_n not in inner or rs_n not in inner:
                continue
            rq = json.loads(hz.read(rq_n))
            rs = json.loads(hz.read(rs_n))
            if pack['context'] is None:
                pack['context'] = rq.get('context')
            board = rq.get('state', {}).get('board') or rq.get('board') or []
            # chave do flop = os 3 primeiros (canônico por ordenação dentro do flop).
            flop3 = board[:3]
            fkey = ''.join(flop3)
            node = _candidates(rs)
            hk = _hist_key(rq.get('state'))
            fe = pack['flops'].setdefault(fkey, dict(board=board, streets={}))
            se = fe['streets'].setdefault(street, {})
            ne = se.setdefault(hk, {})
            if node['combo']:
                if node['combo'] not in ne:
                    added += 1
                ne[node['combo']] = dict(action_id=node['action_id'],
                                         candidates=node['candidates'],
                                         board=board)
    # menu (do param do modelo, se presente num case json completo)
    for n in z.namelist():
        if n.endswith('.json') and 'next16-case' in n and 'history' not in n:
            try:
                cj = json.loads(z.read(n))
                mp = cj.get('complete_model_parameters') or {}
                if mp.get('menu'):
                    pack['menu'] = mp['menu']
                    break
            except Exception:
                continue
    pack.setdefault('batches', []).append(dict(source=str(evidencias_zip), added=added))
    return pack, added


def _load_pack(path):
    import os
    if not os.path.exists(path):
        return None
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


def main(argv=None):
    a = argv or sys.argv[1:]
    if len(a) < 2:
        print(__doc__); return 2
    base = _load_pack(a[1])
    pack, added = ingest(a[0], base_pack=base)
    with gzip.open(a[1], 'wt', encoding='utf-8') as fh:
        json.dump(pack, fh, ensure_ascii=False)
    nflops = len(pack['flops'])
    ncombos = sum(len(ne) for fe in pack['flops'].values()
                  for se in fe['streets'].values() for ne in se.values())
    print('PACK %s: %s' % ('MERGEADO' if base else 'CRIADO', a[1]))
    print('  nesta leva: +%d pontos | TOTAL: flops=%d pontos(combo@nó)=%d levas=%d'
          % (added, nflops, ncombos, len(pack.get('batches') or [])))
    print('  context=%s' % json.dumps(pack['context'], ensure_ascii=False))
    print('  menu=%s' % json.dumps(pack['menu'], ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
