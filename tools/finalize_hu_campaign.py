"""Publish actual campaign results after every transferred Windows model passes."""
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
from strategy.batch_archive import REPOSITORY,PILOT_TAG
from strategy.batch_download import ASSET_BASE,read_json
from strategy.batch_jobs import atomic_json
from strategy.campaign_download import load_campaign,load_family
from strategy.state_contract import StrategyError
from strategy.texassolver_backend import file_hash


def prior_pilot_statistics(pilot, size_proof):
    """Fill the old pilot's omitted raw size from its independently hashed file."""
    size=pilot.get('policy_file_bytes')
    if size is None:
        if (size_proof.get('schema')!='software.hu-prior-pilot-size-proof.v1'
                or size_proof.get('source_release')!=PILOT_TAG
                or size_proof.get('method')!='STAT_OF_RETAINED_FULL_PILOT_SQLITE_AFTER_MATCHING_ITS_PUBLISHED_SHA256'
                or any(size_proof.get(k)!=pilot.get(k) or not pilot.get(k)
                    for k in ('file_sha256','policy_sha256'))
                or size_proof.get('source_iterations')!=pilot.get('iterations')):
            raise StrategyError('PRIOR_PILOT_RAW_SIZE_PROOF_DIFFERS_FROM_PUBLISHED_POLICY')
        size=size_proof.get('policy_file_bytes')
    if type(size) is not int or size<=0:
        raise StrategyError('PRIOR_PILOT_RAW_SIZE_MUST_BE_POSITIVE_BYTES')
    return dict({k:pilot[k] for k in ('coverage','iterations','global_gap_bb')},policy_file_bytes=size)


def checked_results(catalog,rows):
    count=len(catalog['cases']);expected={c['ordinal']:c for c in catalog['cases']}
    if len(rows)!=count or {r['ordinal'] for r in rows}!=set(expected):raise StrategyError('EVERY_CAMPAIGN_WINDOWS_MODEL_REQUIRED')
    for row in rows:
        case=expected[row['ordinal']];hand=row.get('confirmed_hand',{})
        if (row.get('status')!='PASS' or not row.get('platform','').startswith('Windows')
                or any(row.get(k)!=case[k] for k in ('board','policy_sha256','file_sha256','archive_sha256'))
                or row.get('native_target_met') is not True or not row.get('coverage',{}).get('structurally_complete')
                or row.get('pppoker_windows_validated') is not False or row.get('input_devices_used') is not False
                or row.get('all_json_responses_exactly_match_stored_policy') is not True
                or set(row.get('json_roundtrip_streets',()))!={'flop','turn','river'}
                or set(row.get('source_lookup',{}).get('probes',{}))!={'flop','turn','river'}
                or set(row.get('exact_suit_alias',{}).get('probes',{}))!={'flop','turn','river'}
                or not math.isfinite(row['global_native_gap_bb']) or abs(row['global_native_gap_bb']-case['global_gap_bb'])>1e-12):
            raise StrategyError('CAMPAIGN_WINDOWS_PROOF_DIFFERS_FROM_NATIVE_MODEL:'+str(row['ordinal']))
        a,b=row['independent_river'],case['independent_river']
        if (not a.get('exact_enumeration') or a['runout']!=b['runout'] or a['joint_private_deals']!=b['joint_private_deals']
                or not math.isfinite(a['nash_conv_bb']) or abs(a['nash_conv_bb']-b['nash_conv_bb'])>1e-8):
            raise StrategyError('CAMPAIGN_WINDOWS_RIVER_DIFFERS_FROM_NATIVE:'+str(row['ordinal']))
        declared=hand.get('declared_hero_actions_by_street',[])
        if (len(declared)!=3 or {a['street'] for a in declared}!={'FLOP','TURN','RIVER'}
                or any(a['action_id'].split(':')[0] not in ('bet','check') for a in declared)):
            raise StrategyError('CAMPAIGN_WINDOWS_HISTORY_INCOMPLETE:DECLARED_LINE_MISSING_OR_INVALID')
        actions=sum(2+(1 if catalog['context']['positions'][0]!='SB' and a['action_id'].startswith('bet:') else 0) for a in declared)
        if (hand.get('status')!='PASS' or hand.get('event_counts')!=dict(action=actions,board=2)
                or not hand.get('journal_chain_valid') or not hand.get('complete_to_showdown')
                or hand.get('policy_sha256')!=case['policy_sha256']
                or hand.get('frequencies_and_sizes_exactly_match_stored_policy') is not True
                or hand.get('hero_selected_actions_match_lab_actions') is not True
                or hand.get('operational_profile_settings')!=catalog.get('profile_settings',{})):
            raise StrategyError('CAMPAIGN_WINDOWS_CONFIRMED_HISTORY_INCOMPLETE:'+str(row['ordinal']))
    return sorted(rows,key=lambda r:r['ordinal'])


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--family',required=True,choices=('btn32','sb40'))
    p.add_argument('--catalog-asset',required=True);p.add_argument('--windows-run-id',required=True)
    p.add_argument('--verified-receipts-from-all-runs',action='store_true',help='Retain each actual source workflow ID; reuse immutable validated proofs')
    p.add_argument('--output',required=True);args=p.parse_args(argv)
    out=Path(args.output)
    if out.exists():raise StrategyError('FINAL_CAMPAIGN_OUTPUT_MUST_BE_NEW')
    out.mkdir(parents=True);full,asset=load_family(args.family,args.catalog_asset)
    catalog,_=load_family(args.family,args.catalog_asset,new_only=True);tag=catalog['tag']
    release=read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}');rows=[];origins={}
    for ordinal in range(1,len(catalog['cases'])+1):
        run_pattern=r'([0-9]+)' if args.verified_receipts_from_all_runs else '('+re.escape(args.windows_run_id)+')'
        pattern=rf'windows-{args.family}-case-{ordinal:02d}-{run_pattern}-a([0-9]+)\.json'
        matches=[(a['id'],a['name'],m[1]) for a in release['assets'] if a['state']=='uploaded' and (m:=re.fullmatch(pattern,a['name']))]
        if not matches:raise StrategyError('CAMPAIGN_WINDOWS_RECEIPT_NOT_PUBLISHED:'+str(ordinal))
        _,name,actual_run=max(matches)
        row=read_json(ASSET_BASE+tag+'/'+name)
        row.update(validation_workflow_run_id=actual_run,validation_proof_asset_name=name,
            validation_history_asset_name=name[:-5]+'-json-history.zip')
        origins[str(ordinal)]=actual_run;rows.append(row)
    rows=checked_results(catalog,rows);native=catalog['cases'];inventory=[dict(c) for c in full['cases']]
    if args.family=='btn32':
        pilot=read_json(ASSET_BASE+PILOT_TAG+'/result.json')
        size_proof=json.loads(Path('docs/software-hu-close32-sb40-20261115/pilot-size-proof.json').read_text())
        for row in inventory:
            if row['tag']==PILOT_TAG:row.update(prior_pilot_statistics(pilot,size_proof))
        prior=json.loads(Path('docs/software-hu-next16-20261115/published/entrega-lote-16-43765023157-a1.json').read_text())
        pilot_windows=json.loads(Path('docs/software-hu-convergence-20261115/published/integracao-windows-referencia-43752745519.json').read_text(encoding='utf-8-sig'))
        if (prior.get('status')!='PASS' or prior.get('windows_download_and_query_pass')!=16
                or pilot_windows.get('status')!='PASS' or pilot_windows.get('policy_sha256')!=pilot['policy_sha256']):
            raise StrategyError('PREVIOUS_SEVENTEEN_WINDOWS_EVIDENCE_REQUIRED')
    stamp=os.environ['GITHUB_RUN_ID']+'-a'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
    summary=dict(schema='software.hu-campaign-delivery.v1',status='PASS',family=args.family,
        complete_distinct_flop_models=len(inventory),new_complete_flop_models=len(native),
        windows_new_policy_pass=len(rows),json_original_street_queries=3*len(rows),exact_suit_street_queries=3*len(rows),
        confirmed_hands_to_showdown=len(rows),native_target_met_models=len(inventory),
        total_public_nodes=sum(c['coverage']['public_nodes'] for c in inventory),
        nodes_by_street={street:sum(c['coverage']['nodes_by_street'].get(street,0) for c in inventory) for street in ('FLOP','TURN','RIVER')},
        total_policy_file_bytes=sum(c['policy_file_bytes'] for c in inventory),
        new_archive_bytes=sum(c['archive_bytes'] for c in native),
        iterations=dict(min=min(c['iterations'] for c in native),max=max(c['iterations'] for c in native)),
        native_gap_bb=dict(min=min(c['global_gap_bb'] for c in native),max=max(c['global_gap_bb'] for c in native)),
        max_process_tree_rss_bytes=max(c['measurements']['peak_process_tree_rss_bytes'] for c in native),
        all_new_workers_exited=all(c['worker_exited'] for c in native),
        all_new_native_temporaries_removed=all(c['temporary_cleanup_verified'] for c in native),
        plan_sha256=catalog['plan_sha256'],catalog_asset=asset,context=catalog['context'],root_template=catalog['root_template'],
        profile_settings=catalog.get('profile_settings',{}),inventory=inventory,windows_cases=rows,
        source_commit=os.environ['GITHUB_SHA'],release=tag,windows_run_id=args.windows_run_id,
        windows_case_run_ids=origins,
        native_global_gap_independently_certified=False,source_ranges='USER_APPROVED_NVT_REFERENCE',
        pppoker_windows_validated=False,user_notebook_validated=False,input_devices_used=False)
    atomic_json(out/f'entrega-{args.family}-{stamp}.json',summary)
    atomic_json(out/f'inventario-{args.family}-{stamp}.json',dict(schema='software.hu-complete-model-inventory.v1',
        status='COMPLETE',models=inventory,context=catalog['context'],profile_settings=summary['profile_settings']))
    lines=['SOFTWARE ORIGINAL — '+('32 FLOPS BTN x BB CONCLUIDOS' if args.family=='btn32' else 'PILOTO BLIND WAR SB x BB 40 BB CONCLUIDO'),'',
        f"Modelos completos distintos nesta familia: {len(inventory)}.",
        f"Novos modelos calculados e transferidos no Windows: {len(rows)}/{len(native)} PASS.",
        f"Historicos confirmados ate showdown neste lote: {len(rows)}; consultas JSON: {3*len(rows)}.",
        f"Nos publicos: {summary['total_public_nodes']:,}; flop/turn/river: {summary['nodes_by_street']}.",
        f"Politicas finais no disco: {summary['total_policy_file_bytes']/1024**3:.2f} GiB.",'',
        'Salvos: acoes, frequencias de cada combinacao privada, sizes efetivos e respostas nas tres ruas.',
        'Arvore completa dentro do menu declarado: bet 1/3, raise de 100% do pote e all-in; duas agressoes por rua.',
        'Logs de parametros e checkpoints de convergencia estao dentro dos ZIPs de cada politica.',
        'Processos nativos encerrados e temporarios removidos apos verificacao. Bancos finais preservados.','',
        'MODELOS NOVOS | ITERACOES REAIS | GAP GLOBAL NATIVO (BB) | WINDOWS/JSON/HISTORICO']
    for c in native:lines.append(f"{c['ordinal']:02d}. {' '.join(c['board'])} | {c['iterations']} | {c['global_gap_bb']:.9f} | PASS")
    lines.extend(['','INSTALAR',
        'Extraia o ZIP de codigo em pasta nova. Preserve a instalacao antiga.',
        'Execute '+('BAIXAR_BANCO_BTN_BB_32.bat' if args.family=='btn32' else 'BAIXAR_BLIND_WAR_40BB.bat')+'.',
        'O indice library.json e lido com --postflop-library. Veja docs/GUIA_32_FLOPS_E_BLIND_WAR_40BB_20261115.txt.',
        'Os bancos ficam no disco, com cache limitado. Nao e preciso manter todas as arvores na RAM.','',
        'LIMITACOES',
        'BTN 25 BB e SB40 sao familias distintas. Esta entrega nao faz troca automatica entre bibliotecas.',
        'Ranges NVT autorizados como referencia; nao sao um export HRC Pro certificado independentemente.',
        'SB40 usa SB open 2 BB, BB call, BBA de 1 BB e 40 BB antes das postagens.',
        'Nao foram encontrados ranges proprios SB limp x BB check no upload. Esse ramo continua pendente.',
        'Alvo nativo <= 0,5% do pote; precisao nativa nao certifica o gap global por metodo independente.',
        'Um river condicional por modelo foi enumerado independentemente e conferido no Windows.',
        'Os testes usam leituras sinteticas no Windows do GitHub, sem PPPoker nem acionamento de dispositivos.',
        'O notebook do usuario ainda precisa validar leitura, historico e clique real; 8h -> 3h segue pendente.',
        'Outros stacks, ranks, sizes, multiway, ICM e PKO nao foram resolvidos por este lote.','',
        f'https://github.com/{REPOSITORY}/releases/tag/{tag}',
        f'https://github.com/{REPOSITORY}/actions/runs/{args.windows_run_id}',
        f'https://github.com/{REPOSITORY}/pull/14',f'Codigo: {os.environ["GITHUB_SHA"]}',f'Plano: {catalog["plan_sha256"]}'])
    report=out/f'RELATORIO_{args.family.upper()}_{stamp}.txt';report.write_text('\n'.join(lines)+'\n')
    source=out/f'Software-{args.family}-{os.environ["GITHUB_SHA"][:8]}-{stamp}.zip'
    subprocess.run(['git','archive','--format=zip','--prefix=Software/','HEAD','-o',str(source)],check=True)
    with zipfile.ZipFile(source,'a',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(report,'Software/RELATORIO_ENTREGA.txt')
    atomic_json(out/f'source-manifest-{args.family}-{stamp}.json',dict(asset=source.name,sha256=file_hash(source),
        bytes=source.stat().st_size,source_commit=os.environ['GITHUB_SHA'],contains_full_policy_data=False))
    for path in sorted(out.iterdir()):subprocess.run(['gh','release','upload',tag,'--repo',REPOSITORY,str(path)],check=True)
    notes=out/'release-notes.txt';notes.write_text('\n'.join(lines[:8])+f'\n\nRelatorio: {report.name}\nCodigo: {source.name}\n\nNVT de referencia; nao e validacao real no PPPoker.\n')
    subprocess.run(['gh','release','edit',tag,'--repo',REPOSITORY,'--notes-file',str(notes)],check=True)
    print(json.dumps({k:summary[k] for k in ('status','family','complete_distinct_flop_models','windows_new_policy_pass')}));return 0


if __name__=='__main__':raise SystemExit(main())
