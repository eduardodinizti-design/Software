"""Lossless multipart archives and a checked catalog for the next 16 NVT flops."""
import hashlib
import json
from pathlib import Path

from strategy.batch_jobs import canonical_flop,catalogue_flops,case_id
from strategy.hu_engine import HOLDOUT_FLOPS
from strategy.state_contract import StrategyError,digest

REPOSITORY='eduardodinizti-design/Software'
BATCH_TAG='hu-btn-bb-nvt-next16-20261115'
PILOT_TAG='hu-btn-bb-nvt-reference-20261115'


def make_batch_plan(game_path):
    game=json.loads(Path(game_path).read_text())
    excluded={canonical_flop(game['root']['board'])}|{canonical_flop(b.split()) for b in HOLDOUT_FLOPS}
    boards=[b for b in catalogue_flops(100) if canonical_flop(b) not in excluded][:16]
    cases=[dict(ordinal=i+1,case_id=case_id(b),board=b) for i,b in enumerate(boards)]
    value=dict(schema='software.hu-next16-plan.v1',tag=BATCH_TAG,game=game,cases=cases,
        already_solved_board=game['root']['board'],preserved_holdout_flops=[b.split() for b in HOLDOUT_FLOPS],
        max_parallel_hosts=8,workers_per_host=1,settings=dict(iterations=2001,accuracy_pct=.5,
            threads=4,memory_mb=10240,work_disk_mb=12288,timeout_seconds=18000))
    value['plan_sha256']=digest(value);return value


def checked_batch_plan(path):
    value=json.loads(Path(path).read_text());body=dict(value);expected=body.pop('plan_sha256')
    if value.get('schema')!='software.hu-next16-plan.v1' or digest(body)!=expected:
        raise StrategyError('NEXT16_PLAN_HASH_MISMATCH')
    boards=[canonical_flop(c['board']) for c in value['cases']]
    forbidden={canonical_flop(value['already_solved_board'])}|{canonical_flop(b) for b in value['preserved_holdout_flops']}
    if (len(boards)!=16 or len(set(boards))!=16 or set(boards)&forbidden
            or [c['ordinal'] for c in value['cases']]!=list(range(1,17))
            or any(c['case_id']!=case_id(c['board']) for c in value['cases'])):
        raise StrategyError('NEXT16_REQUIRES_NEW_DISTINCT_FLOPS_AND_PRESERVED_HOLDOUTS')
    return value


def split_archive(path,destination,prefix,*,part_bytes=1024**3):
    if type(part_bytes) is not int or part_bytes<1:raise StrategyError('POSITIVE_ARCHIVE_PART_SIZE_REQUIRED')
    if not prefix or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in prefix):
        raise StrategyError('SAFE_ARCHIVE_PREFIX_REQUIRED')
    destination=Path(destination)
    if destination.exists():raise StrategyError('ARCHIVE_PART_OUTPUT_MUST_BE_NEW')
    destination.mkdir(parents=True);parts=[];total=hashlib.sha256()
    with Path(path).open('rb') as source:
        while True:
            first=source.read(min(part_bytes,1024**2))
            if not first:break
            name=f'{prefix}.zip.part{len(parts)+1:03d}';sha=hashlib.sha256();size=0
            with (destination/name).open('xb') as out:
                block=first
                while block:
                    out.write(block);sha.update(block);total.update(block);size+=len(block)
                    if size==part_bytes:break
                    block=source.read(min(1024**2,part_bytes-size))
            parts.append(dict(name=name,bytes=size,sha256=sha.hexdigest()))
    if not parts:raise StrategyError('EMPTY_REFERENCE_ARCHIVE')
    return dict(archive_bytes=sum(p['bytes'] for p in parts),archive_sha256=total.hexdigest(),parts=parts)


def verify_remote_parts(manifest,assets):
    by_name={a['name']:a for a in assets}
    for part in manifest['parts']:
        actual=by_name.get(part['name'])
        if (not actual or actual.get('state')!='uploaded' or actual['size']!=part['bytes']
                or actual.get('digest')!='sha256:'+part['sha256']):
            raise StrategyError('REMOTE_REFERENCE_PART_NOT_VERIFIED:'+part['name'])
    return True


def make_catalog(plan,manifests):
    entries=[]
    for case in plan['cases']:
        candidates=[m for m in manifests if m.get('plan_sha256')==plan['plan_sha256'] and m.get('case_id')==case['case_id']]
        if any(m.get('board')!=case['board'] for m in candidates):raise StrategyError('PUBLISHED_CASE_BOARD_CHANGED')
        if any(m.get('schema')!='software.hu-batch-case.v1' or not m.get('coverage',{}).get('structurally_complete')
               or set(m.get('lookup_streets',()))!={'flop','turn','river'} for m in candidates):
            raise StrategyError('PUBLISHED_CASE_IS_NOT_A_COMPLETE_QUERY_VALIDATED_POLICY')
        bound=2*plan['game']['root']['pot_bb']*plan['settings']['accuracy_pct']/100
        if any(m['native_target_met'] and (type(m['global_gap_bb']) not in (float,int) or not 0<=m['global_gap_bb']<=bound+1e-9) for m in candidates):
            raise StrategyError('NATIVE_TARGET_LABEL_DISAGREES_WITH_REPORTED_GAP')
        if candidates:
            candidates.sort(key=lambda m:(not m['native_target_met'],m['global_gap_bb'] if m['global_gap_bb'] is not None else float('inf'),m['archive_sha256']))
            entries.append(candidates[0])
    learned=sum(e['native_target_met'] for e in entries)
    return dict(schema='software.hu-batch-catalog.v1',tag=plan['tag'],plan_sha256=plan['plan_sha256'],
        status='COMPLETE' if learned==16 else 'PARTIAL',planned_new_flops=16,published_new_flops=len(entries),
        native_target_met_flops=learned,cases=entries,pilot_tag=PILOT_TAG,
        context=plan['game']['context'],root_template=plan['game']['root'],
        already_solved_board=plan['already_solved_board'],preserved_holdout_flops=plan['preserved_holdout_flops'],
        source_ranges='USER_APPROVED_NVT_REFERENCE',pppoker_windows_validated=False)
