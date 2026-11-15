"""Publish a checked 16-model Windows transfer report and a source-code ZIP."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_archive import BATCH_TAG,PILOT_TAG,REPOSITORY
from strategy.batch_download import ASSET_BASE,load_catalog,read_json
from strategy.batch_jobs import atomic_json
from strategy.state_contract import StrategyError
from strategy.texassolver_backend import file_hash


def checked_windows_results(catalog,rows):
    if len(rows)!=16 or {r['ordinal'] for r in rows}!=set(range(1,17)):
        raise StrategyError('WINDOWS_REQUIRES_SIXTEEN_DISTINCT_COMPLETED_TRANSFERS')
    expected={c['ordinal']:c for c in catalog['cases']}
    for r in rows:
        c=expected[r['ordinal']]
        if (r.get('status')!='PASS' or not r.get('platform','').startswith('Windows')
                or r['board']!=c['board'] or r['policy_sha256']!=c['policy_sha256']
                or r['file_sha256']!=c['file_sha256'] or r['archive_sha256']!=c['archive_sha256']
                or r.get('native_target_met') is not True or not r.get('coverage',{}).get('structurally_complete')
                or abs(r['global_native_gap_bb']-c['global_gap_bb'])>1e-12
                or set(r.get('source_lookup',{}).get('probes',{}))!={'flop','turn','river'}
                or set(r.get('exact_suit_alias',{}).get('probes',{}))!={'flop','turn','river'}
                or r.get('pppoker_windows_validated') is not False or r.get('input_devices_used') is not False):
            raise StrategyError('WINDOWS_TRANSFER_OR_QUERY_PROOF_DOES_NOT_MATCH_PUBLISHED_CASE:'+str(r['ordinal']))
        a,b=r['independent_river'],c['independent_river']
        if (not a.get('exact_enumeration') or a['runout']!=b['runout']
                or a['joint_private_deals']!=b['joint_private_deals']
                or abs(a['nash_conv_bb']-b['nash_conv_bb'])>1e-8):
            raise StrategyError('WINDOWS_CONDITIONAL_RIVER_DIFFERS_FROM_LINUX:'+str(r['ordinal']))
    return sorted(rows,key=lambda r:r['ordinal'])


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--run-id',required=True);p.add_argument('--run-url',required=True)
    args=p.parse_args(argv);out=Path(args.output)
    if out.exists():raise StrategyError('FINAL_DELIVERY_OUTPUT_MUST_BE_NEW')
    out.mkdir(parents=True);catalog,asset=load_catalog();rows=[]
    for n in range(1,17):rows.append(read_json(ASSET_BASE+BATCH_TAG+f'/windows-case-{n:02d}-{args.run_id}.json'))
    rows=checked_windows_results(catalog,rows)
    native=catalog['cases'];total_bytes=sum(c['policy_file_bytes'] for c in native)
    summary=dict(schema='software.hu-next16-delivery.v1',status='PASS',new_flops=16,
        previous_full_pilot_flops=1,total_reference_models_with_pilot=17,
        native_target_met_flops=16,windows_download_and_query_pass=16,
        original_street_queries=48,exact_suit_alias_street_queries=48,
        total_public_nodes=sum(c['coverage']['public_nodes'] for c in native),
        nodes_by_street={street:sum(c['coverage']['nodes_by_street'].get(street,0) for c in native)
                        for street in ('FLOP','TURN','RIVER')},
        native_gap_bb=dict(min=min(c['global_gap_bb'] for c in native),max=max(c['global_gap_bb'] for c in native)),
        native_iterations=dict(min=min(c['iterations'] for c in native),max=max(c['iterations'] for c in native)),
        new_policy_file_bytes=total_bytes,new_archive_bytes=sum(c['archive_bytes'] for c in native),
        max_measured_process_tree_rss_bytes=max(c['measurements']['peak_process_tree_rss_bytes'] for c in native),
        all_workers_exited=all(c['worker_exited'] for c in native),
        all_native_temporaries_cleaned_after_validation=all(c['temporary_cleanup_verified'] for c in native),
        source_commit=os.environ['GITHUB_SHA'],plan_sha256=catalog['plan_sha256'],catalog_asset=asset,
        windows_run_url=args.run_url,pilot_release=PILOT_TAG,release=BATCH_TAG,
        source_ranges=catalog['source_ranges'],context=catalog['context'],root_template=catalog['root_template'],
        scope='NVT_REFERENCE_COMPLETE_POLICIES_NATIVE_PRECISION_AND_WINDOWS_DATA_QUERY_VALIDATION',
        native_global_gap_independently_certified=False,pppoker_windows_validated=False,user_notebook_validated=False,
        windows_cases=rows)
    atomic_json(out/f'entrega-lote-16-{args.run_id}.json',summary)
    lines=['SOFTWARE ORIGINAL — 16 NOVOS FLOPS BTN x BB','',
        'CONCLUIDO: 16/16 politicas completas, 16/16 no alvo nativo e 16/16 transferidas e consultadas no Windows.',
        'Incluindo o piloto A72 anterior, sao 17 modelos completos de referencia. Variantes de naipe nao contam como novos estudos.',
        '',f"Nos publicos novos: {summary['total_public_nodes']:,}",
        f"Flop/turn/river: {summary['nodes_by_street']}",
        f"Dados SQLite novos: {total_bytes/1024**3:.2f} GiB; ZIPs de transferencia: {summary['new_archive_bytes']/1024**3:.2f} GiB.",
        'A consulta usa cache limitado; as arvores completas permanecem no disco.',
        '', 'FLOP | ITERACOES REAIS | GAP GLOBAL NATIVO (BB) | WINDOWS']
    for c in sorted(native,key=lambda c:c['ordinal']):
        lines.append(f"{c['ordinal']:02d}. {' '.join(c['board'])} | {c['iterations']} | {c['global_gap_bb']:.9f} | PASS")
    lines.extend(['','O que foi salvo: acoes, frequencias por combinacao privada, sizes efetivos e respostas em todas as ruas.',
        'A arvore foi conferida em todas as acoes e continuacoes publicas fisicamente possiveis do modelo.',
        'O decisor do bot consultou os arquivos publicados em flop/turn/river: 48 consultas originais e 48 por bijecao exata de naipes.',
        'Os hashes das partes, dos ZIPs, dos bancos e das politicas foram conferidos. Os processos nativos foram encerrados.',
        'Os temporarios nativos foram removidos apos validacao; os bancos e o piloto anterior foram preservados.',
        '', 'Modelo: BTN open 2,5 BB x BB call; stack inicial 25 BB, pote 5,5 BB, 22,5 BB restantes, sem ante.',
        'Priors NVT autorizados como referencia. Menu: bet 1/3, raise 100% do pote e all-in.',
        'Alvo nativo: exploitability <= 0,5% do pote. O gap global aqui e o do solver, sem certificacao independente completa.',
        'Um river condicional por flop foi enumerado de forma independente e repetido no Windows; os 16 resultados coincidiram.',
        'Isso nao estende a estrategia a outros ranks, stacks, sizes, multiway, ICM ou recompensas PKO.',
        '', 'PARA INSTALAR',
        'Use o ZIP Software-HU-next16 disponibilizado nesta Release, extraia em pasta nova e execute BAIXAR_LOTE_NVT_16.bat.',
        'O instalador monta library.json com os 16 flops e o piloto anterior, em runtime/hu/nvt-next16-.../bank/.',
        'Informe ao Software: --postflop-library "CAMINHO/bank/library.json".',
        'O download nao liga o bot, nao inicia solver e nao aciona o mouse. Veja docs/GUIA_LOTE_NVT_16_20261115.txt.',
        '', 'LIMITES E PENDENCIAS',
        'Windows significa transferencia e consulta de dados em executor Windows do GitHub; nao e uma sessao real no PPPoker do usuario.',
        'A leitura, o historico e a confirmacao dos cliques no notebook ainda exigem o teste real no cliente.',
        'O caso historico 8h -> 3h continua pendente de reproducao no mesmo tema. Nenhum threshold de leitura foi alterado neste lote.',
        '', 'EVIDENCIAS',args.run_url,
        f'https://github.com/{REPOSITORY}/releases/tag/{BATCH_TAG}',
        f'https://github.com/{REPOSITORY}/tree/feat/hu-next16-20261115',
        f'Plano SHA-256: {catalog["plan_sha256"]}',f'Catalogo: {asset}',f'Codigo verificado: {os.environ["GITHUB_SHA"]}'])
    report=out/f'RELATORIO_LOTE_16_WINDOWS-{args.run_id}.txt';report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    source=out/f'Software-HU-next16-{os.environ["GITHUB_SHA"][:8]}-{args.run_id}.zip'
    subprocess.run(['git','archive','--format=zip','--prefix=Software-HU-next16/','HEAD','-o',str(source)],check=True)
    with zipfile.ZipFile(source,'a',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(report,'Software-HU-next16/RELATORIO_ENTREGA_LOTE_16.txt')
    atomic_json(out/f'source-download-manifest-{args.run_id}.json',dict(asset=source.name,
        bytes=source.stat().st_size,sha256=file_hash(source),source_commit=os.environ['GITHUB_SHA'],contains_full_policy_data=False))
    for path in sorted(out.iterdir()):
        subprocess.run(['gh','release','upload',BATCH_TAG,'--repo',REPOSITORY,str(path)],check=True)
    notes=out/'notes.txt';notes.write_text('\n'.join(lines[:9])+'\n\nNVT de referencia; alvo nativo, sem certificacao GTO global independente ou teste real no PPPoker.\n\nDownload code: '+source.name+'\nReport: '+report.name+'\n\nWindows validation: '+args.run_url+'\n')
    subprocess.run(['gh','release','edit',BATCH_TAG,'--repo',REPOSITORY,'--notes-file',str(notes)],check=True)
    print(json.dumps({k:summary[k] for k in ('status','new_flops','windows_download_and_query_pass','new_policy_file_bytes')}));return 0


if __name__=='__main__':raise SystemExit(main())
