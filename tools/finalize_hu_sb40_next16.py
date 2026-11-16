"""Publish seventeen SB40 models only after the sixteen actual Windows proofs."""
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
from strategy.blind_war import SB40_TAG,SB40_NEXT16_TAG
from strategy.campaign_download import load_family,load_campaign
from strategy.state_contract import StrategyError
from strategy.texassolver_backend import file_hash
from tools.collect_hu_campaign_evidence import release,receive,check_history
from tools.finalize_hu_campaign import checked_results


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--catalog-asset',required=True)
    p.add_argument('--native-run',required=True);p.add_argument('--output',required=True);args=p.parse_args(argv)
    if args.catalog_asset!='batch-catalog-'+args.native_run+'.json':
        raise StrategyError('CATALOG_MUST_IDENTIFY_THE_ACTUAL_NATIVE_WORKFLOW')
    out=Path(args.output)
    if out.exists():raise StrategyError('FINAL_SB40_OUTPUT_MUST_BE_NEW')
    out.mkdir(parents=True);evidence=out/'evidence';evidence.mkdir()
    catalog,_=load_family('sb40-next16',args.catalog_asset,new_only=True)
    full,_=load_family('sb40-next16',args.catalog_asset)
    pilot,_=load_campaign(SB40_TAG,'batch-catalog-43777381626.json')
    if len(full['cases'])!=17 or len(catalog['cases'])!=16:
        raise StrategyError('EXACT_SEVENTEEN_SB40_MODELS_REQUIRED')
    remote=release(SB40_NEXT16_TAG);assets={a['name']:a for a in remote['assets'] if a['state']=='uploaded'}
    rows=[];hashes=[];histories=[];origins={}
    for ordinal in range(1,17):
        pattern=rf'windows-sb40-next16-case-{ordinal:02d}-([0-9]+)-a([0-9]+)\.json'
        options=[(a['id'],a,m[1]) for a in assets.values() if (m:=re.fullmatch(pattern,a['name']))]
        if not options:raise StrategyError('ACTUAL_WINDOWS_PROOF_MISSING:'+str(ordinal))
        _,asset,run=max(options,key=lambda item:item[0]);name=asset['name'];history=name[:-5]+'-json-history.zip'
        if history not in assets:raise StrategyError('ACTUAL_WINDOWS_JSON_HISTORY_MISSING:'+str(ordinal))
        hashes.append(receive(asset,SB40_NEXT16_TAG,evidence/name))
        hashes.append(receive(assets[history],SB40_NEXT16_TAG,evidence/history))
        row=json.loads((evidence/name).read_text());histories.append(check_history(evidence/history,row))
        row.update(validation_workflow_run_id=run,validation_proof_asset_name=name,validation_history_asset_name=history)
        origins[str(ordinal)]=run;rows.append(row)
    rows=checked_results(catalog,rows)
    previous=release(SB40_TAG);previous={a['name']:a for a in previous['assets']}
    name='windows-sb40-case-01-43779044783-a1.json';history=name[:-5]+'-json-history.zip'
    for key in (name,history):hashes.append(receive(previous[key],SB40_TAG,evidence/key))
    pilot_proof=json.loads((evidence/name).read_text());checked_results(pilot,[pilot_proof])
    pilot_history=check_history(evidence/history,pilot_proof)
    pattern=r'windows-contracts-sb40-next16-'+re.escape(os.environ['GITHUB_RUN_ID'])+r'-a([0-9]+)\.txt'
    options=[(int(m[1]),a['name']) for a in assets.values() if (m:=re.fullmatch(pattern,a['name']))]
    if not options:raise StrategyError('THIS_WINDOWS_WORKFLOWS_CONTRACT_RECEIPT_REQUIRED')
    contract=max(options)[1]
    hashes.append(receive(assets[contract],SB40_NEXT16_TAG,evidence/contract))
    text=(evidence/contract).read_text(encoding='utf-8-sig');match=re.search(r'Ran (\d+) tests',text)
    if not match or not re.search(r'\nOK(?: |\r|\n|$)',text):raise StrategyError('FINAL_WINDOWS_CONTRACTS_NOT_PASS')
    skipped=re.search(r'OK \(skipped=(\d+)\)',text);skipped=int(skipped[1]) if skipped else 0
    native=catalog['cases'];inventory=full['cases'];stamp=os.environ['GITHUB_RUN_ID']+'-a'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
    summary=dict(schema='software.hu-sb40-seventeen-delivery.v1',status='PASS',complete_distinct_flop_models=17,
        new_complete_flop_models=16,new_windows_policy_pass=16,new_json_street_queries=48,
        new_exact_suit_street_queries=48,new_confirmed_synthetic_hands=16,previous_confirmed_synthetic_hands_reused=1,
        windows_contract_tests=int(match[1]),windows_contract_skipped=skipped,windows_contract_asset_name=contract,
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
        inventory=inventory,windows_cases=rows,windows_case_run_ids=origins,
        pilot_windows_proof=pilot_proof,published_histories=histories,pilot_published_history=pilot_history,
        downloaded_evidence_hashes=hashes,catalog_asset=args.catalog_asset,plan_sha256=catalog['plan_sha256'],
        source_commit=os.environ['GITHUB_SHA'],native_workflow_run=args.native_run,windows_workflow_run=os.environ['GITHUB_RUN_ID'],
        source_ranges='USER_APPROVED_NVT_REFERENCE_NOT_DIRECT_HRC_CERTIFICATION',
        pppoker_windows_validated=False,user_notebook_validated=False,input_devices_used=False)
    if not summary['all_new_workers_exited'] or not summary['all_new_native_temporaries_removed']:
        raise StrategyError('NATIVE_WORKERS_AND_OWNED_TEMPORARIES_MUST_BE_CLOSED')
    atomic_json(out/f'entrega-sb40-next16-{stamp}.json',summary)
    atomic_json(out/f'inventario-sb40-17-{stamp}.json',dict(status='COMPLETE',models=inventory,
        context=summary['context'],profile_settings=summary['profile_settings']))
    lines=['SOFTWARE ORIGINAL — BLIND WAR SB x BB 40 BB: 17 FLOPS COMPLETOS','',
        'Concluidos 16 flops novos; com o piloto As 7d 2c, sao 17 modelos distintos nesta familia.',
        'Os 32 modelos BTN x BB de 25 BB e a instalacao antiga foram preservados.',
        f"Estados publicos: {summary['total_public_nodes']:,}; politicas SQLite: {summary['total_policy_file_bytes']/1024**3:.2f} GiB.",
        'Salvos: arvore completa dentro do menu, acoes, frequencias por combinacao, sizes e respostas flop/turn/river.',
        'Os ranges condicionais seguem o historico observado; o range inicial nao e reiniciado a cada street.',
        'Parametros e checkpoints de convergencia estao nos reports dos bancos. Nao sao snapshots CFR de cada iteracao.','',
        'CONFIGURACAO EXATA',
        'Torneio chip-EV regular com nove jogadores originalmente; sete folds, SB open 2 BB, BB call.',
        'Ambos com 40 BB antes das postagens; big-blind ante de 1 BB. Flop: pote 5 BB, SB 38 BB e BB 37 BB.',
        'SB e o jogador fora de posicao. Dois jogadores ativos nao transforma a mesa em um torneio originalmente HU.',
        'Ranges NVT autorizados como referencia; sem certificacao independente de export direto HRC Pro.',
        'Menu: bet 1/3, raise de 100% do pote e all-in; limite de duas agressoes por rua.',
        'Convergencia nesse menu nao prova que os ranges pre-flop de entrada sejam otimos.','',
        'VALIDACAO',
        '16 bancos novos integralmente baixados e verificados em runners Windows do GitHub.',
        '16 maos sinteticas novas confirmadas ate showdown; 48 consultas JSON e 48 consultas por bijecao exata de naipes.',
        f"Contratos Windows: {summary['windows_contract_tests']} testes; {skipped} pulados. Consulte o log para os motivos.",
        'Historico anterior do piloto conferido novamente, preservando seu workflow de origem.',
        'Os ZIPs de historico publicados foram baixados e comparados com os receipts e as respostas JSON.',
        'Um river condicional por modelo foi enumerado independentemente e repetido no Windows.',
        'O alvo nativo e exploitability <= 0,5% do pote. global_gap_bb e NashConv, o dobro da exploitability.',
        'O criterio global nao garante igual precisao em cada no; a revisao condicional tem outro escopo.',
        'Nenhuma validacao desta entrega e uma sessao real no PPPoker. Nenhum dispositivo de entrada foi acionado.','',
        'NOVOS FLOPS | ITERACOES | NASHCONV GLOBAL NATIVO (BB) | NASHCONV RIVER CONDICIONAL (BB)']
    for c in native:lines.append(f"{c['ordinal']:02d}. {' '.join(c['board'])} | {c['iterations']} | {c['global_gap_bb']:.9f} | {c['independent_river']['nash_conv_bb']:.9f}")
    lines.extend(['','INSTALACAO E CONSUMO',
        'Extraia o ZIP de codigo desta entrega em pasta nova; Python 3.12 x64 e requirements.txt.',
        'Execute BAIXAR_BLIND_WAR_40BB_17.bat. Banco: runtime/hu/sb40-17/bank/library.json.',
        'Esse BAT instala dados; nao inicia o bot nem movimenta o mouse. O banco antigo runtime/hu/sb40 fica preservado.',
        'O bot le library.json e consulta as politicas completas SQLite no disco com cache limitado.',
        'Use --postflop-library com o caminho desse indice no Software original, iniciando a observacao antes dos blinds.',
        'Nao recrie PolicyLibrary a cada frame: prepare uma vez e mantenha uma instancia por sessao.',
        'JSONL completo e opcional para interoperabilidade; nao carregue a arvore inteira na RAM do notebook.',
        'O instalador confere disco livre. E possivel baixar modelos individuais; veja docs/GUIA_SB40_17_FLOPS_20261116.txt.',
        'Os workers terminaram; seus temporarios foram removidos apos verificacao. Bancos finais e logs foram preservados.','',
        'PENDENCIAS',
        'SB limp x BB check ainda precisa de priors proprios e perfil de chegada limpado; nao e o complemento do raise.',
        '3-bet pots, outros stacks/antes/sizes, multiway, ICM e PKO precisam de modelos separados.',
        'Outros flops nao sao resolvidos por semelhanca visual. Equivalencia de naipes exige preservar ambos os ranges.',
        'As familias BTN25 e SB40 permanecem separadas, sem roteamento automatico entre elas.',
        'EV independente de cada acao nao esta salvo em todos os nos; ev_bb pode ser null.',
        'Leitura, historico, sincronizacao, clique e desempenho real no PPPoker Windows do notebook seguem pendentes.',
        'O caso historico 8h -> 3h continua pendente no mesmo tema; nenhum limiar OCR foi reduzido.','',
        f'https://github.com/{REPOSITORY}/releases/tag/{SB40_NEXT16_TAG}',
        f'https://github.com/{REPOSITORY}/actions/runs/{args.native_run}',
        f'https://github.com/{REPOSITORY}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
        f'Codigo: {os.environ["GITHUB_SHA"]}',f'Plano: {catalog["plan_sha256"]}'])
    report=out/f'SB40_17_FLOPS_{stamp}.txt';report.write_text('\n'.join(lines)+'\n')
    source=out/f'Software-SB40-17-{os.environ["GITHUB_SHA"][:8]}-{stamp}.zip'
    subprocess.run(['git','archive','--format=zip','--prefix=Software/','HEAD','-o',str(source)],check=True)
    with zipfile.ZipFile(source,'a',compression=zipfile.ZIP_DEFLATED) as z:z.write(report,'Software/RELATORIO_SB40_17_FLOPS.txt')
    atomic_json(out/f'source-manifest-sb40-next16-{stamp}.json',dict(asset=source.name,sha256=file_hash(source),
        bytes=source.stat().st_size,source_commit=os.environ['GITHUB_SHA'],contains_full_policy_data=False))
    with zipfile.ZipFile(out/f'evidencias-sb40-next16-{stamp}.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(evidence.iterdir()):z.write(path,path.name)
    for path in sorted(out.iterdir()):
        if path.is_file():subprocess.run(['gh','release','upload',SB40_NEXT16_TAG,'--repo',REPOSITORY,str(path)],check=True)
    notes=out/'release-notes.txt';notes.write_text('\n'.join(lines[:6])+f'\n\nRelatorio: {report.name}\nCodigo: {source.name}\n\n'
        'NVT de referencia. Alvo nativo de exploitability; nao e certificacao global independente ou validacao real PPPoker.\n')
    subprocess.run(['gh','release','edit',SB40_NEXT16_TAG,'--repo',REPOSITORY,'--notes-file',str(notes)],check=True)
    print(json.dumps(dict(status='PASS',complete_sb40_models=17,new_windows_models=16,report=report.name)));return 0


if __name__=='__main__':raise SystemExit(main())
