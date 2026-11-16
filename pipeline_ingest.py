"""PIPELINE de um comando: exports novos (HRC) -> cerebro validado, auditado.

Pega uma pasta de exports NOVOS do solver/HRC, auto-detecta o formato, INGERE,
VALIDA (rejeita lixo), PROMOVE so as chaves que ainda faltam (nunca sobrescreve a
verdade validada), faz BACKUP, re-AUDITA e mostra o DELTA de cobertura + as celulas
fechadas. Idempotente: rodar de novo nao duplica (dedup por chave).

Formatos aceitos (os mesmos do SavedHands):
  - *.json  -> JSON range-coach-pro (rfi/resp/opv3/limp)      via hrc_ingest
  - *.zip   -> arvore HoldemResources (settings+nodes/*.json) via hrc_tree_ingest
             (push/fold Npf_* e resteal Nresteal_* -> spots de shove)

Uso:
  python pipeline_ingest.py --dir <pasta_exports_novos> [--pack <validados.json>]
                            [--modes icm,pko_icm,chip_ev,pko] [--dry-run]

--dry-run: ingere, valida e MOSTRA o que entraria, SEM tocar no pack.
Sem --dry-run: faz backup <pack>.bak-pipeline-<data> e grava o pack promovido.
Passivo/offline: so le/escreve JSON; nao captura, nao clica.
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

import hrc_ingest
import hrc_tree_ingest
import promover_ranges
import auditar_cobertura_preflop as aud
from preflop_advisor import PreflopAdvisor

SHOVE_SPOTS = {'open_shove', 'vs_open_shove', '3bet_shove'}
STACK_BUCKETS = set(PreflopAdvisor.STACK_BUCKETS)
POSITIONS = set(hrc_ingest.POSITIONS)
SUM_TOL = 0.03            # soma das freqs por classe deve bater ~1
AA_JAM_MIN = 0.80         # num spot de shove, AA tem que jammar alto (sanidade)


def validate_node(n):
    """(ok, motivo). Rejeita no malformado/incoerente ANTES de entrar no cerebro."""
    c = n.get('context') or {}
    if c.get('stack') not in STACK_BUCKETS:
        return False, 'BUCKET_FORA_DA_GRADE:%s' % c.get('stack')
    if n.get('hero') not in POSITIONS:
        return False, 'HERO_INVALIDO:%s' % n.get('hero')
    freq = n.get('freq') or {}
    if not freq:
        return False, 'SEM_FREQ'
    for a, arr in freq.items():
        if not isinstance(arr, list) or len(arr) != 169:
            return False, 'FREQ_TAMANHO:%s' % a
        if any((v < -1e-6 or v > 1 + 1e-6) for v in arr):
            return False, 'FREQ_FORA_01:%s' % a
    # soma por classe ~1 (HRC deriva fold como complemento)
    for i in range(169):
        s = sum(freq[a][i] for a in freq)
        if abs(s - 1.0) > SUM_TOL:
            return False, 'SOMA_CLASSE_%d=%.3f' % (i, s)
    # sanidade de shove: AA tem que jammar
    if n.get('spot') in SHOVE_SPOTS and 'all_in' in freq:
        iaa = hrc_ingest.HANDS.index('AA')
        if freq['all_in'][iaa] < AA_JAM_MIN:
            return False, 'AA_NAO_JAMMA:%.2f' % freq['all_in'][iaa]
    return True, 'OK'


def collect(paths):
    """Ingere todos os arquivos; devolve (nos_validos, rejeitados[(id,motivo)], fontes)."""
    nodes, rejected, sources = [], [], []
    for p in paths:
        p = Path(p)
        try:
            if p.suffix.lower() == '.json':
                if p.name == 'manifest.json':
                    continue
                ns, src = hrc_ingest.nodes_from_file(str(p))
            elif p.suffix.lower() == '.zip':
                ns, src = hrc_tree_ingest.nodes_from_tree(str(p))
            else:
                continue
        except Exception as e:                            # noqa: BLE001
            rejected.append((p.name, 'INGEST_FALHOU:%s' % e))
            continue
        sources.append(src)
        for n in ns:
            ok, why = validate_node(n)
            (nodes if ok else rejected).append(n if ok else (n.get('id'), why))
    return nodes, rejected, sources


def _audit_pct(pack_path):
    adv = PreflopAdvisor.from_file(pack_path)
    cov, tot, _bcc, _bc, _g = aud.audit(adv)
    return cov, tot


def main(argv=None):
    ap = argparse.ArgumentParser(description='Pipeline de ingestao HRC -> cerebro validado')
    ap.add_argument('--dir', required=True, help='pasta com os exports NOVOS')
    ap.add_argument('--glob', default='*', help='filtro (default: *.json e *.zip)')
    ap.add_argument('--pack', default=r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json')
    ap.add_argument('--modes', default='icm,pko_icm,chip_ev,pko')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args(argv)

    d = Path(args.dir)
    paths = sorted([p for p in d.glob(args.glob) if p.suffix.lower() in ('.json', '.zip')])
    if not paths:
        print('Nenhum export (.json/.zip) em %s' % d); return 2
    print('Arquivos a ingerir: %d' % len(paths))

    nodes, rejected, sources = collect(paths)
    print('Nos validos: %d | rejeitados: %d | fontes: %d' % (len(nodes), len(rejected), len(sources)))
    if rejected:
        print('--- REJEITADOS (amostra) ---')
        for item in rejected[:15]:
            print('   ', item)

    # estudo pack em memoria -> promover so chaves novas
    study = dict(format='nvt-range-export', version=1, engineCommit='pipeline-ingest',
                 generatedAt=None, hands=list(hrc_ingest.HANDS), nodes=nodes)
    with open(args.pack, encoding='utf-8') as fh:
        val = json.load(fh)
    modes = set(args.modes.split(','))
    out, added, by_mode = promover_ranges.promote(val, study, modes)
    print('\nPromoveria %d nos novos (chaves ausentes). Por modo: %s' % (len(added), dict(by_mode)))
    # quais celulas (mode,stage,spot,spread,bucket) fecham
    cells = sorted({(n['context']['mode'], n['context']['stage'], n['spot'],
                     n.get('spread'), n['context']['stack']) for n in added}, key=str)
    for cell in cells[:40]:
        print('   fecha', cell)
    if len(cells) > 40:
        print('   ... +%d celulas' % (len(cells) - 40))

    if args.dry_run or not added:
        print('\n[dry-run ou nada novo] pack NAO alterado.')
        return 0

    # auditoria antes/depois
    cov0, tot = _audit_pct(args.pack)
    bak = '%s.bak-pipeline-%s' % (args.pack, datetime.date.today().strftime('%Y%m%d'))
    if not os.path.exists(bak):
        with open(bak, 'w', encoding='utf-8') as fh:
            json.dump(val, fh, ensure_ascii=False)
    with open(args.pack, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False)
    cov1, _ = _audit_pct(args.pack)
    print('\nPACK ATUALIZADO: %s (backup: %s)' % (args.pack, os.path.basename(bak)))
    print('  nos: %d -> %d' % (len(val['nodes']), len(out['nodes'])))
    print('  COBERTURA AO VIVO: %.1f%% -> %.1f%% (%+d situacoes)'
          % (100.0 * cov0 / tot, 100.0 * cov1 / tot, cov1 - cov0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
