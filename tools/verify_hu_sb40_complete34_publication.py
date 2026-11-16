"""Download and check the published source, complete inventory and all hand ZIPs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy.batch_download import ASSET_BASE,fetch,safe_name
from strategy.batch_jobs import atomic_json,canonical_flop
from strategy.blind_war import SB40_COMPLETE34_TAG
from strategy.campaign_download import load_family
from strategy.state_contract import StrategyError
from strategy.texassolver_backend import file_hash
from tools.collect_hu_campaign_evidence import release,receive,check_history
from tools.finalize_hu_campaign import checked_results
from tools.finalize_hu_sb40_complete34 import checked_root_review
from tools.check_hu_sb40_checkpoint import check_saved


def require(value,reason):
    if not value:raise StrategyError(reason)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True)
    p.add_argument('--catalog-asset',required=True);p.add_argument('--output',required=True);args=p.parse_args(argv)
    out=Path(args.output)
    require(not out.exists(),'PUBLICATION_CHECK_OUTPUT_MUST_BE_NEW');out.mkdir(parents=True)
    assets={a['name']:a for a in release(SB40_COMPLETE34_TAG)['assets'] if a['state']=='uploaded'}
    options=[a for a in assets.values() if a['name'].startswith('entrega-sb40-34-'+args.run+'-a') and a['name'].endswith('.json')]
    require(bool(options),'FINAL_DELIVERY_MUST_EXIST_BEFORE_ROUNDTRIP_CHECK')
    asset=max(options,key=lambda a:a['id']);stamp=asset['name'][len('entrega-sb40-34-'):-5]
    names=[asset['name'],'inventario-sb40-34-'+stamp+'.json','SB40_34_FLOPS_'+stamp+'.txt',
        'source-manifest-sb40-34-'+stamp+'.json','evidencias-sb40-34-'+stamp+'.zip']
    hashes=[receive(assets[name],SB40_COMPLETE34_TAG,out/name) for name in names]
    summary=json.loads((out/names[0]).read_text());inventory=summary['inventory']
    require(summary.get('status')=='PASS' and summary.get('complete_distinct_flop_models')==34
        and summary.get('new_windows_policy_pass')==17 and summary.get('new_json_street_queries')==51
        and summary.get('new_exact_suit_street_queries')==51 and summary.get('new_confirmed_synthetic_hands')==17
        and summary.get('all_new_workers_exited') is True and summary.get('all_new_native_temporaries_removed') is True
        and summary.get('pppoker_windows_validated') is False and summary.get('bb_hero_operational_adapter_present') is False,
        'PUBLISHED_DELIVERY_IS_NOT_COMPLETE_WITH_EXPLICIT_SCOPE')
    require(len(inventory)==34 and len({canonical_flop(c['board']) for c in inventory})==34,'ALL_THIRTY_FOUR_MODELS_MUST_BE_DISTINCT')
    require(summary['total_public_nodes']==sum(c['coverage']['public_nodes'] for c in inventory)
        and summary['total_policy_file_bytes']==sum(c['policy_file_bytes'] for c in inventory),'PUBLISHED_INVENTORY_TOTALS_CHANGED')
    catalog,_=load_family('sb40-34',args.catalog_asset,new_only=True)
    full,_=load_family('sb40-34',args.catalog_asset)
    require(full['cases']==inventory,'PUBLISHED_INVENTORY_DIFFERS_FROM_THE_CHECKED_FULL_LIBRARY')
    checked_results(catalog,summary['windows_cases'])
    for row in summary['windows_cases']:checked_root_review(row)
    require(summary['prerequisite_checkpoint']==check_saved(),'THE_FIRST_SEVENTEEN_NO_LONGER_MATCH_THE_SAVED_CHECKPOINT')
    histories=[]
    with zipfile.ZipFile(out/names[-1]) as bundle,tempfile.TemporaryDirectory(prefix='sb40-published-history-',dir=out) as temp:
        require(bundle.testzip() is None,'PUBLISHED_EVIDENCE_CRC_FAILED')
        for row in summary['windows_cases']:
            name=row['validation_history_asset_name'];require(safe_name(name),'UNSAFE_HISTORY_NAME')
            path=Path(temp)/name;path.write_bytes(bundle.read(name));histories.append(check_history(path,row))
    source=json.loads((out/names[-2]).read_text());asset=assets[source['asset']]
    require(safe_name(source['asset']) and source['asset'].startswith('Software-SB40-34-')
        and asset['size']==source['bytes'] and asset.get('digest')=='sha256:'+source['sha256'],
        'PUBLISHED_SOURCE_ZIP_METADATA_DIFFERS')
    path=out/source['asset']
    with fetch(ASSET_BASE+SB40_COMPLETE34_TAG+'/'+source['asset']) as remote,path.open('xb') as target:
        while block:=remote.read(1024**2):target.write(block)
    require(path.stat().st_size==source['bytes'] and file_hash(path)==source['sha256'],'PUBLISHED_SOURCE_BYTES_CHANGED')
    required=['BAIXAR_BLIND_WAR_40BB_34.bat','strategy/campaign_download.py','tools/check_hu_sb40_checkpoint.py',
        'tools/prepare_hu_sb40_complete34.py','docs/GUIA_SB40_34_FLOPS_20261116.txt','RELATORIO_SB40_34_FLOPS.txt']
    with zipfile.ZipFile(path) as archive:
        require(sum(i.file_size for i in archive.infolist())<4*1024**3,'UNEXPECTED_SOURCE_ZIP_SIZE')
        require(archive.testzip() is None and all('Software/'+name in archive.namelist() for name in required),'PUBLISHED_SOURCE_CRC_OR_REQUIRED_FILE_FAILED')
        report=archive.read('Software/RELATORIO_SB40_34_FLOPS.txt')
    require(report==(out/names[2]).read_bytes(),'EMBEDDED_TXT_DIFFERS_FROM_PUBLISHED_REPORT')
    proof=dict(schema='software.hu-sb40-34-publication-check.v1',status='PASS',complete_models=34,new_models=17,
        complete_prior_models_preserved=17,windows_run=args.run,native_catalog_asset=args.catalog_asset,
        source_asset=source['asset'],source_sha256=source['sha256'],source_bytes=source['bytes'],
        embedded_report_sha256=hashlib.sha256(report).hexdigest(),zip_crc_all_entries_valid=True,
        new_confirmed_json_histories=17,new_json_street_queries=51,new_exact_suit_street_queries=51,
        published_histories_checked=histories,metadata_hashes=hashes,required_source_paths=required,
        all_policy_bytes_redownloaded_in_this_check=False,pppoker_windows_validated=False,user_notebook_validated=False)
    atomic_json(out/'publicacao-final-verificada.json',proof)
    print(json.dumps(dict(status='PASS',models=34,new_models=17,report=names[2],source=source['asset'])));return 0


if __name__=='__main__':raise SystemExit(main())
