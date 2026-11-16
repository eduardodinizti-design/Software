"""Publish a reserved SB40 stage after seventeen actual full Windows transfers."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_archive import REPOSITORY
from strategy.batch_jobs import atomic_json
from strategy.sb40_series import family_tag,validate_series_plan
from strategy.campaign_download import load_family
from strategy.state_contract import StrategyError
from strategy.texassolver_backend import file_hash,SOURCE_COMMIT
from tools.collect_hu_campaign_evidence import release,receive,check_history
from tools.finalize_hu_campaign import checked_results
from tools.finalize_hu_sb40_complete51 import checked_root_review

DOC=Path('docs/software-hu-sb40-to102-20261116')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--target',required=True,type=int,choices=(68,85,102))
    p.add_argument('--catalog-asset',required=True)
    p.add_argument('--native-run',required=True);p.add_argument('--output',required=True);args=p.parse_args(argv)
    target=args.target;prior=target-17;tag=family_tag(target);family=f'sb40-{target}'
    if not re.fullmatch(r'batch-catalog-'+re.escape(args.native_run)+r'(?:-a[0-9]+)?\.json',args.catalog_asset):
        raise StrategyError('CATALOG_MUST_IDENTIFY_THE_ACTUAL_NATIVE_WORKFLOW')
    out=Path(args.output)
    if out.exists():raise StrategyError('FINAL_SB40_OUTPUT_MUST_BE_NEW')
    out.mkdir(parents=True);evidence=out/'evidence';evidence.mkdir()
    catalog,_=load_family(family,args.catalog_asset,new_only=True)
    full,_=load_family(family,args.catalog_asset)
    _,checkpoint=validate_series_plan(catalog['_original_plan'])
    atomic_json(evidence/f'checkpoint-primeiros{prior}.json',checkpoint)
    atomic_json(evidence/f'sb40-complete{target}-plan.json',catalog['_original_plan'])
    if len(catalog['cases'])!=17 or len(full['cases'])!=target:
        raise StrategyError('EXACT_RESERVED_TOTAL_MODELS_REQUIRED')
    remote=release(tag);assets={a['name']:a for a in remote['assets'] if a['state']=='uploaded'}
    rows=[];hashes=[];histories=[];origins={}
    for ordinal in range(1,18):
        pattern=rf'windows-sb40-{target}-case-{ordinal:02d}-([0-9]+)-a([0-9]+)\.json'
        options=[(a['id'],a,m[1]) for a in assets.values() if (m:=re.fullmatch(pattern,a['name']))]
        if not options:raise StrategyError('ACTUAL_WINDOWS_PROOF_MISSING:'+str(ordinal))
        _,asset,run=max(options,key=lambda item:item[0]);name=asset['name'];history=name[:-5]+'-json-history.zip'
        if history not in assets:raise StrategyError('ACTUAL_WINDOWS_JSON_HISTORY_MISSING:'+str(ordinal))
        hashes.append(receive(asset,tag,evidence/name))
        hashes.append(receive(assets[history],tag,evidence/history))
        row=json.loads((evidence/name).read_text());histories.append(check_history(evidence/history,row))
        checked_root_review(row)
        row.update(validation_workflow_run_id=run,validation_proof_asset_name=name,validation_history_asset_name=history)
        origins[str(ordinal)]=run;rows.append(row)
    rows=checked_results(catalog,rows)
    current_run=os.environ['GITHUB_RUN_ID']
    pattern=rf'windows-contracts-sb40-{target}-'+re.escape(current_run)+r'-a([0-9]+)\.txt'
    options=[(int(m[1]),a['name']) for a in assets.values() if (m:=re.fullmatch(pattern,a['name']))]
    if not options:raise StrategyError('THIS_WINDOWS_WORKFLOW_CONTRACT_RECEIPT_REQUIRED')
    contract=max(options)[1];hashes.append(receive(assets[contract],tag,evidence/contract))
    text=(evidence/contract).read_text(encoding='utf-8-sig');match=re.search(r'Ran (\d+) tests',text)
    if not match or not re.search(r'\nOK(?: |\r|\n|$)',text):raise StrategyError('WINDOWS_CONTRACTS_NOT_PASS')
    skipped=re.search(r'OK \(skipped=(\d+)\)',text);skipped=int(skipped[1]) if skipped else 0
    linux=json.loads((DOC/'regressao-linux.json').read_text())
    if (linux.get('status')!='PASS' or linux.get('errors') or linux.get('failures') or linux.get('skipped')
            or linux.get('native_stream_tests_enabled') is not True):raise StrategyError('NATIVE_ENABLED_LINUX_REGRESSION_REQUIRED')
    native=catalog['cases'];inventory=full['cases']
    summary=dict(schema='software.hu-sb40-series-delivery.v1',status='PASS',complete_distinct_flop_models=target,
        new_complete_flop_models=17,previous_saved_flop_models=prior,new_windows_policy_pass=17,
        previous_complete_windows_downloads_reused=prior,new_json_street_queries=51,new_exact_suit_street_queries=51,
        new_confirmed_synthetic_hands=17,windows_contract_tests=int(match[1]),windows_contract_skipped=skipped,
        windows_contract_asset_name=contract,linux_reference_regression=linux,prerequisite_checkpoint=checkpoint,
        total_public_nodes=sum(c['coverage']['public_nodes'] for c in inventory),
        total_policy_file_bytes=sum(c['policy_file_bytes'] for c in inventory),
        nodes_by_street={s:sum(c['coverage']['nodes_by_street'][s] for c in inventory) for s in ('FLOP','TURN','RIVER')},
        all_new_workers_exited=all(c['worker_exited'] for c in native),
        all_new_native_temporaries_removed=all(c['temporary_cleanup_verified'] for c in native),
        max_new_process_tree_rss_bytes=max(c['measurements']['peak_process_tree_rss_bytes'] for c in native),
        iterations=dict(min=min(c['iterations'] for c in native),max=max(c['iterations'] for c in native)),
        native_target_metric='EXPLOITABILITY_PERCENT_OF_ROOT_POT',native_target_pct=.5,
        global_gap_bb_definition='NASH_CONV_TWICE_EXPLOITABILITY',native_global_gap_independently_certified=False,
        context=catalog['context'],root_template=catalog['root_template'],profile_settings=catalog['profile_settings'],
        inventory=inventory,windows_cases=rows,windows_case_run_ids=origins,published_histories=histories,
        downloaded_evidence_hashes=hashes,catalog_asset=args.catalog_asset,plan_sha256=catalog['plan_sha256'],
        source_commit=os.environ['GITHUB_SHA'],native_workflow_run=args.native_run,windows_workflow_run=current_run,
        source_ranges='USER_APPROVED_NVT_REFERENCE_NOT_DIRECT_HRC_CERTIFICATION',postflop_backend='TexasSolver',
        native_upstream_source_commit=SOURCE_COMMIT,operational_hero_position='SB',
        opponent_policy_responses_saved='BB',bb_hero_operational_adapter_present=False,
        pppoker_windows_validated=False,user_notebook_validated=False,input_devices_used=False)
    if not summary['all_new_workers_exited'] or not summary['all_new_native_temporaries_removed']:
        raise StrategyError('NEW_NATIVE_WORKERS_AND_OWNED_TEMPORARIES_MUST_BE_CLOSED')
    stamp=current_run+'-a'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
    atomic_json(out/f'entrega-sb40-{target}-{stamp}.json',summary)
    atomic_json(out/f'inventario-sb40-{target}-{stamp}.json',dict(status='COMPLETE',models=inventory,
        context=summary['context'],profile_settings=summary['profile_settings']))
    lines=[f'SOFTWARE ORIGINAL — SB x BB 40 BB: {target} FLOPS COMPLETOS','',
        f'17 novos flops completos, {prior} anteriores preservados: total {target}.',
        'Politicas completas dentro do menu: acoes, frequencias privadas, sizes e respostas nas tres ruas.',
        f"Estados publicos: {summary['total_public_nodes']:,}; SQLite: {summary['total_policy_file_bytes']/1024**3:.2f} GiB.",
        f"Plano: {catalog['plan_sha256']}; checkpoint anterior: {checkpoint['checkpoint_sha256']}",'',
        'JOGO E ALCANCE',
        'Nove jogadores originalmente: sete folds, SB open 2 BB, BB call, BBA 1 BB.',
        'Stacks 40 BB antes dos posts; flop: pote 5 BB, SB 38 BB e BB 37 BB. Hero SB fora de posicao.',
        'Ranges NVT autorizados como referencia, sem certificacao direta HRC Pro.',
        'Menu preservado: bet 1/3, raise 100% do pote, all-in, duas agressoes por rua.',
        'Alvo nativo de exploitability <= 0,5% do pote; global_gap_bb e NashConv (o dobro).',
        'Um river condicional por modelo recebe enumeracao independente; nao certifica todos os nos.',
        'Logs de convergencia e politicas finais nao sao snapshots resumiveis dos regrets de cada iteracao.',
        'EV independente por acao pode ser null. Arvore completa significa o menu declarado.',
        'TexasSolver upstream '+SOURCE_COMMIT+'; patches/binario identificados nos reports.',
        '12 GiB por worker; oito hosts isolados no maximo; um solve por host.','',
        'VERIFICACOES',
        '17 bancos novos integralmente baixados e lidos no Windows do GitHub; 17 historicos sinteticos.',
        '51 consultas JSON das tres ruas e 51 consultas por bijecao exata de naipes.',
        'Frequencias e sizes conferidos com os bancos e ZIPs publicados de historicos.',
        f"Contratos Windows: {summary['windows_contract_tests']} testes, {skipped} pulados; motivos no log.",
        f"Linux com controles nativos: {linux['passed']}/{linux['tests_run']} PASS.",
        f'{prior} bancos anteriores mantem provas de leitura Windows e SHA-256 atuais.',
        'Workers encerrados; apenas temporarios proprios removidos depois de preservar as politicas.',
        'Nenhuma sessao PPPoker real e alegada. Nenhum mouse, teclado ou leitor OCR foi alterado.','',
        'NOVOS FLOPS | ITERACOES | NASHCONV GLOBAL BB | NASHCONV RIVER CONDICIONAL BB']
    for c in native:lines.append(f"{c['ordinal']:02d}. {' '.join(c['board'])} | {c['iterations']} | {c['global_gap_bb']:.9f} | {c['independent_river']['nash_conv_bb']:.9f}")
    lines.extend(['','FREQUENCIAS MEDIAS NO INICIO DO FLOP',
        'Ponderadas pelos dois ranges e blockers; cada mao consulta sua mistura. Amounts sao adicionais em BB.'])
    for row in rows:
        values='; '.join(a['action_id']+'='+format(100*a['frequency'],'.2f')+'%' for a in row['root_policy_review']['actions'])
        lines.append(' '.join(row['board'])+' | '+values)
    lines.extend(['','INSTALACAO',
        f'Extraia Software-SB40-{target} em pasta nova. Python 3.12 x64 e requirements.txt.',
        f'Execute BAIXAR_BLIND_WAR_40BB_{target}.bat; indice runtime/hu/{family}/bank/library.json.',
        'O BAT instala dados; nao inicia o bot. Os bancos anteriores e BTN25 permanecem separados.',
        'Use --postflop-library com esse indice no Software original e observe antes dos blinds.',
        'Prepare PolicyLibrary uma vez; SQLite usa disco e cache limitado. Confira espaco livre.',
        f'Para so os 17 novos, use --family {family} --new-only em pasta nova.',
        'JSONL opcional; consultas normais usam SQLite preservando frequencias e sizes.','',
        'PENDENCIAS',
        'Hero BB, limp/check, outros stacks/antes/sizes, 3-bet pots, multiway, ICM e PKO exigem estudos proprios.',
        'Nao ha roteamento automatico BTN25/SB40. Semelhanca visual nao substitui o board exato.',
        'Leitura, sincronizacao, historico, efeito dos cliques e latencia real no notebook PPPoker pendentes.',
        '8h -> 3h segue pendente no mesmo tema; nenhum limiar OCR foi reduzido.','',
        f'https://github.com/{REPOSITORY}/releases/tag/{tag}',
        f'https://github.com/{REPOSITORY}/actions/runs/{current_run}',f'Codigo: {os.environ["GITHUB_SHA"]}'])
    report=out/f'SB40_{target}_FLOPS_{stamp}.txt';report.write_text('\n'.join(lines)+'\n')
    source=out/f'Software-SB40-{target}-{os.environ["GITHUB_SHA"][:8]}-{stamp}.zip'
    subprocess.run(['git','archive','--format=zip','--prefix=Software/','HEAD','-o',str(source)],check=True)
    with zipfile.ZipFile(source,'a',compression=zipfile.ZIP_DEFLATED) as z:
        z.write(report,f'Software/RELATORIO_SB40_{target}_FLOPS.txt')
        for name in (f'checkpoint-primeiros{prior}.json',f'sb40-complete{target}-plan.json'):
            z.write(evidence/name,'Software/'+str(DOC/name))
    atomic_json(out/f'source-manifest-sb40-{target}-{stamp}.json',dict(asset=source.name,sha256=file_hash(source),
        bytes=source.stat().st_size,source_commit=os.environ['GITHUB_SHA'],contains_full_policy_data=False))
    with zipfile.ZipFile(out/f'evidencias-sb40-{target}-{stamp}.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(evidence.iterdir()):z.write(path,path.name)
    for path in sorted(out.iterdir()):
        if path.is_file():subprocess.run(['gh','release','upload',tag,'--repo',REPOSITORY,str(path)],check=True)
    notes=out/'release-notes.txt';notes.write_text('\n'.join(lines[:6])+f'\n\nRelatorio: {report.name}\nCodigo: {source.name}\n\n'
        'NVT de referencia; alvo nativo dentro do menu. Nao e validacao real PPPoker.\n')
    subprocess.run(['gh','release','edit',tag,'--repo',REPOSITORY,'--notes-file',str(notes)],check=True)
    print(json.dumps(dict(status='PASS',complete_sb40_models=target,new_windows_models=17,report=report.name)));return 0


if __name__=='__main__':raise SystemExit(main())
