"""Measure local action consistency, preserving unmeasured accuracy as unknown."""
import argparse
import json
from pathlib import Path
from preflop_tree_book import TreeBook


def summarize(directory):
    directory=Path(directory);book=TreeBook.from_directory(directory);records=[];cells=0
    for filename in sorted(directory.glob('*.json')):
        if filename.name=='summary.json':continue
        raw=json.loads(filename.read_text())
        if 'node' not in raw:continue
        node=next((n for n in book.records if n['id']==raw['id']),None)
        status=raw['status'];values=raw.get('action_values') or {}
        cells+=sum(len(row['actions']) for row in values.get('hands',[]))
        examples=[]
        for row in values.get('hands',[]):
            if row['hand'] not in ('AA','QQ','AKs','A5s','72o'):continue
            best=max(row['actions'],key=lambda a:a['ev_bb'])
            examples.append(dict(hand=row['hand'],best_immediate_action=best['label'],reference_ev_bb=best['ev_bb']))
        records.append(dict(id=raw['id'],iteration=status.get('iteration'),stop_reason=status.get('stop_reason'),
                            current_accuracy_measured=status.get('accuracy_iteration')==status.get('published_iteration') and status.get('accuracy_iteration') is not None,
                            global_gap_bb=status.get('gap_total') if status.get('accuracy_iteration') is not None else None,
                            conditional_quality=node.get('quality') if node else None,
                            use='STUDY_ONLY' if node is None or node['research_only'] else 'CONDITIONAL_MODEL_REFERENCE',
                            hand_rows=len(values.get('hands',[])),examples=examples))
    return dict(upstream='MatthewPDingle/GTOpen',commit='5c2989397abf314f229d293c16f96ea783c7ca5b',
                calculations=len(records),hand_rows=sum(r['hand_rows'] for r in records),action_ev_cells=cells,
                conditional_references=sum(r['use']=='CONDITIONAL_MODEL_REFERENCE' for r in records),
                study_only=sum(r['use']=='STUDY_ONLY' for r in records),
                independent_hrc_validation=False,pppoker_windows_validation=False,
                scope='Conditional EVs under a disclosed continuation approximation; local consistency is not Nash/global/empirical validation.',
                cases=records,import_errors=book.errors)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();result=summarize(args.directory);args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False))


if __name__=='__main__':main()
