"""Publish 34 SB40 models only after all 17 new full Windows transfers pass."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_archive import REPOSITORY
from strategy.batch_jobs import atomic_json
from strategy.blind_war import SB40_COMPLETE34_TAG
from strategy.campaign_download import load_family
from strategy.state_contract import StrategyError
from strategy.texassolver_backend import file_hash,SOURCE_COMMIT
from tools.check_hu_sb40_checkpoint import check_saved
from tools.collect_hu_campaign_evidence import release,receive,check_history
from tools.finalize_hu_campaign import checked_results

DOC=Path('docs/software-hu-sb40-complete34-20261116')


def checked_root_review(row):
    review=row.get('root_policy_review',{})
    probabilities=[a['frequency'] for a in review.get('actions',[])]
    if (review.get('source_policy_sha256')!=row['policy_sha256'] or review.get('board')!=row['board']
            or review.get('actor_position')!='SB' or review.get('policy_modified') is not False
            or review.get('method')!='BLOCKER_CONDITIONED_JOINT_RANGE_WEIGHTED_ROOT_POLICY'
            or not probabilities or any(not math.isfinite(v) or not 0<=v<=1 for v in probabilities)
            or abs(sum(probabilities)-1)>1e-6):
        raise StrategyError('EXACT_SB40_ROOT_REVIEW_REQUIRED')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--catalog-asset',required=True)
    p.add_argument('--native-run',required=True);p.add_argument('--output',required=True);args=p.parse_args(argv)
    if args.catalog_asset!='batch-catalog-'+args.native_run+'.json':
        raise StrategyError('CATALOG_MUST_IDENTIFY_THE_ACTUAL_NATIVE_WORKFLOW')
    out=Path(args.output)
    if out.exists():raise StrategyError('FINAL_SB40_OUTPUT_MUST_BE_NEW')
    out.mkdir(parents=True);evidence=out/'evidence';evidence.mkdir()
    checkpoint=check_saved()
    expected=json.loads((DOC/'checkpoint-primeiros17.json').read_text())
    if checkpoint!=expected:raise StrategyError('FIRST_SEVENTEEN_MUST_STILL_BE_SAVED_AT_DELIVERY')
    atomic_json(evidence/'checkpoint-primeiros17.json',checkpoint)
    catalog,_=load_family('sb40-34',args.catalog_asset,new_only=True)
    full,_=load_family('sb40-34',args.catalog_asset)
    if len(catalog['cases'])!=17 or len(full['cases'])!=34:
        raise StrategyError('EXACT_THIRTY_FOUR_MODELS_REQUIRED')
    remote=release(SB40_COMPLETE34_TAG);assets={a['name']:a for a in remote['assets'] if a['state']=='uploaded'}
    rows=[];hashes=[];histories=[];origins={}
    for ordinal in range(1,18):
        pattern=rf'windows-sb40-34-case-{ordinal:02d}-([0-9]+)-a([0-9]+)\.json'
        options=[(a['id'],a,m[1]) for a in assets.values() if (m:=re.fullmatch(pattern,a['name']))]
        if not options:raise StrategyError('ACTUAL_WINDOWS_PROOF_MISSING:'+str(ordinal))
        _,asset,run=max(options,key=lambda item:item[0]);name=asset['name'];history=name[:-5]+'-json-history.zip'
        if history not in assets:raise StrategyError('ACTUAL_WINDOWS_JSON_HISTORY_MISSING:'+str(ordinal))
        hashes.append(receive(asset,SB40_COMPLETE34_TAG,evidence/name))
        hashes.append(receive(assets[history],SB40_COMPLETE34_TAG,evidence/history))
        row=json.loads((evidence/name).read_text());histories.append(check_history(evidence/history,row))
        checked_root_review(row)
        row.update(validation_workflow_run_id=run,validation_proof_asset_name=name,validation_history_asset_name=history)
        origins[str(ordinal)]=run;rows.append(row)
    rows=checked_results(catalog,rows)
    current_run=os.environ['GITHUB_RUN_ID']
    pattern=r'windows-contracts-sb40-34-'+re.escape(current_run)+r'-a([0-9]+)\.txt'
    options=[(int(m[1]),a['name']) for a in assets.values() if (m:=re.fullmatch(pattern,a['name']))]
    if not options:raise StrategyError('THIS_WINDOWS_WORKFLOW_CONTRACT_RECEIPT_REQUIRED')
    contract=max(options)[1];hashes.append(receive(assets[contract],SB40_COMPLETE34_TAG,evidence/contract))
    text=(evidence/contract).read_text(encoding='utf-8-sig');match=re.search(r'Ran (\d+) tests',text)
    if not match or not re.search(r'\nOK(?: |\r|\n|$)',text):raise StrategyError('WINDOWS_CONTRACTS_NOT_PASS')
    skipped=re.search(r'OK \(skipped=(\d+)\)',text);skipped=int(skipped[1]) if skipped else 0
    linux=json.loads((DOC/'regressao-linux.json').read_text())
    if (linux.get('status')!='PASS' or linux.get('errors') or linux.get('failures') or linux.get('skipped')
            or linux.get('native_stream_tests_enabled') is not True):raise StrategyError('NATIVE_ENABLED_LINUX_REGRESSION_REQUIRED')
    native=catalog['cases'];inventory=full['cases']
    summary=dict(schema='software.hu-sb40-thirty-four-delivery.v1',status='PASS',complete_distinct_flop_models=34,
        new_complete_flop_models=17,previous_saved_flop_models=17,new_windows_policy_pass=17,
        previous_complete_windows_downloads_reused=17,new_json_street_queries=51,new_exact_suit_street_queries=51,
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
    atomic_json(out/f'entrega-sb40-34-{stamp}.json',summary)
    atomic_json(out/f'inventario-sb40-34-{stamp}.json',dict(status='COMPLETE',models=inventory,
        context=summary['context'],profile_settings=summary['profile_settings']))
    lines=['SOFTWARE ORIGINAL — SB x BB 40 BB: 34 FLOPS COMPLETOS','',
        'Concluidos 17 novos flops; os 17 anteriores permanecem salvos, totalizando 34 modelos distintos SB40.',
        'A condicao de preservacao dos primeiros 17 foi verificada antes de iniciar e novamente nesta entrega.',
        'Os 32 modelos BTN25, a main e as instalacoes anteriores permanecem separados e preservados.',
        f"Estados publicos: {summary['total_public_nodes']:,}; politicas SQLite: {summary['total_policy_file_bytes']/1024**3:.2f} GiB.",
        'Salvos: arvore completa dentro do menu, acoes, frequencias por combinacao privada, sizes e respostas nas tres ruas.',
        'Os ranges condicionais seguem o historico. Logs guardam parametros e checkpoints de convergencia.',
        'Nao sao snapshots de todos os regrets CFR para retomar cada iteracao.','',
        'CONFIGURACAO',
        'Nove jogadores originalmente: sete folds, SB open 2 BB, BB call, BBA de 1 BB.',
        'Stacks 40 BB antes dos posts; flop com pote 5 BB, SB 38 BB e BB 37 BB.',
        'SB fora de posicao e hero fixo. As respostas do BB estao salvas; operar como hero BB exige adaptacao propria.',
        'Ranges NVT de referencia autorizados pelo usuario, sem certificacao direta HRC Pro.',
        'TexasSolver upstream '+SOURCE_COMMIT+'; patches e binario identificados nos reports.',
        'Menu preservado: bet 1/3, raise de 100% do pote, all-in e duas agressoes por rua.',
        'Orcamento inicial deste lote: 12 GiB por worker, oito hosts isolados no maximo, um worker por host.',
        'Aumentar recursos nao alterou os priors, stacks, menu, iteracoes ou alvo de precisao.','',
        'VALIDACAO',
        '17 bancos novos integralmente baixados e conferidos em runners Windows do GitHub.',
        '17 maos sinteticas confirmadas ate showdown; 51 consultas JSON e 51 consultas por bijecao exata de naipes.',
        'As frequencias e sizes consultados correspondem aos bancos. Os ZIPs de historico foram baixados e conferidos.',
        'Um river condicional por novo modelo recebeu enumeracao independente e repeticao no Windows.',
        f"Contratos Windows: {summary['windows_contract_tests']} testes, {skipped} pulados; motivos no log.",
        f"Regressao Linux com controles nativos: {linux['passed']}/{linux['tests_run']} PASS, sem falhas ou pulados.",
        'Os 17 bancos anteriores preservam suas provas reais de download completo e leitura de arquivos no Windows.',
        'Alvo nativo de exploitability <= 0,5% do pote. global_gap_bb e NashConv, o dobro da exploitability.',
        'O criterio global nao garante a mesma precisao em cada no e nao certifica como otimos os ranges pre-flop.',
        'Nenhum teste desta entrega e uma sessao real no PPPoker; nenhum dispositivo de entrada foi acionado.','',
        'NOVOS FLOPS | ITERACOES | NASHCONV GLOBAL NATIVO BB | NASHCONV RIVER CONDICIONAL BB']
    for c in native:lines.append(f"{c['ordinal']:02d}. {' '.join(c['board'])} | {c['iterations']} | {c['global_gap_bb']:.9f} | {c['independent_river']['nash_conv_bb']:.9f}")
    lines.extend(['','FREQUENCIAS MEDIAS NO INICIO DO FLOP',
        'Ponderadas pelos DOIS ranges e blockers. Cada mao consulta sua propria mistura; isto nao e uma regra identica para todas.',
        'Amounts sao contribuicoes adicionais em BB, nao raise-to.'])
    for row in rows:
        values='; '.join(a['action_id']+'='+format(100*a['frequency'],'.2f')+'%' for a in row['root_policy_review']['actions'])
        lines.append(' '.join(row['board'])+' | '+values)
    lines.extend(['','INSTALACAO',
        'Extraia o ZIP Software-SB40-34 desta entrega em pasta nova. Python 3.12 x64 e requirements.txt.',
        'Execute BAIXAR_BLIND_WAR_40BB_34.bat; indice runtime/hu/sb40-34/bank/library.json.',
        'O BAT instala dados; nao ativa o bot nem movimenta o mouse. Os bancos sb40 e sb40-17 ficam preservados.',
        'Use --postflop-library com o indice novo no Software original; inicie a observacao antes dos blinds.',
        'Prepare PolicyLibrary uma vez por sessao. SQLite usa disco e cache limitado; nao carregue toda a arvore na RAM.',
        'O instalador confere disco livre; os 34 bancos completos exigem dezenas de GB mais um ZIP temporario.',
        'Para baixar so os 17 novos, use --family sb40-34 --new-only em pasta nova; veja o guia incluido.',
        'JSONL completo e opcional para interoperabilidade. O consumo normal consulta SQLite e preserva frequencias e sizes.',
        'Workers encerrados e temporarios proprios removidos apos verificacao; politicas finais e logs preservados.','',
        'PENDENCIAS',
        'Hero BB, SB limp x BB check, outros stacks/antes/sizes, 3-bet pots, multiway, ICM e PKO exigem trabalhos proprios.',
        'Nao ha roteamento automatico entre BTN25 e SB40. Outros flops nao sao resolvidos apenas por semelhanca visual.',
        'Equivalencia de naipes exige preservar ambos os ranges. EV independente por acao pode ser null.',
        'Leitura, sincronizacao, historico, efeito do clique e desempenho real no PPPoker do notebook seguem pendentes.',
        'O caso historico 8h -> 3h continua pendente no mesmo tema; nenhum limiar OCR foi reduzido.','',
        f'https://github.com/{REPOSITORY}/releases/tag/{SB40_COMPLETE34_TAG}',
        f'https://github.com/{REPOSITORY}/actions/runs/{args.native_run}',
        f'https://github.com/{REPOSITORY}/actions/runs/{current_run}',
        f'Codigo: {os.environ["GITHUB_SHA"]}',f'Plano: {catalog["plan_sha256"]}',
        f'Checkpoint anterior: {checkpoint["checkpoint_sha256"]}'])
    report=out/f'SB40_34_FLOPS_{stamp}.txt';report.write_text('\n'.join(lines)+'\n')
    source=out/f'Software-SB40-34-{os.environ["GITHUB_SHA"][:8]}-{stamp}.zip'
    subprocess.run(['git','archive','--format=zip','--prefix=Software/','HEAD','-o',str(source)],check=True)
    with zipfile.ZipFile(source,'a',compression=zipfile.ZIP_DEFLATED) as z:z.write(report,'Software/RELATORIO_SB40_34_FLOPS.txt')
    atomic_json(out/f'source-manifest-sb40-34-{stamp}.json',dict(asset=source.name,sha256=file_hash(source),
        bytes=source.stat().st_size,source_commit=os.environ['GITHUB_SHA'],contains_full_policy_data=False))
    with zipfile.ZipFile(out/f'evidencias-sb40-34-{stamp}.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(evidence.iterdir()):z.write(path,path.name)
    for path in sorted(out.iterdir()):
        if path.is_file():subprocess.run(['gh','release','upload',SB40_COMPLETE34_TAG,'--repo',REPOSITORY,str(path)],check=True)
    notes=out/'release-notes.txt';notes.write_text('\n'.join(lines[:6])+f'\n\nRelatorio: {report.name}\nCodigo: {source.name}\n\n'
        'NVT de referencia; alvo nativo dentro do menu. Nao e validacao real PPPoker.\n')
    subprocess.run(['gh','release','edit',SB40_COMPLETE34_TAG,'--repo',REPOSITORY,'--notes-file',str(notes)],check=True)
    print(json.dumps(dict(status='PASS',complete_sb40_models=34,new_windows_models=17,report=report.name)));return 0


if __name__=='__main__':raise SystemExit(main())
