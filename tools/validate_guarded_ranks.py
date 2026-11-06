"""Independent protected-rank regression on real board crops and explicit transforms."""
import os
os.environ.setdefault('OMP_THREAD_LIMIT','1')
import argparse,hashlib,json,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from table_reading.community_cards import read_board
from table_reading.rank_templates import OCR_ONLY_RANKS
ROOT=Path(__file__).resolve().parents[1]

def run(assets,output,reference):
    rows=json.loads((ROOT/'docs/table-reading/colored-board-expansion.json').read_text())
    previous={r['case']:r for r in json.loads(reference.read_text())['results']}
    split=json.loads((ROOT/'table_reading/rank_template_assets/source_split.json').read_text())
    training=set(split['training_sources']);cases=[];sources={}
    def load(source,digest=None):
        data=(assets/source).read_bytes();actual=hashlib.sha256(data).hexdigest()
        if digest:assert actual==digest,source
        sources[source]=actual
        return cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
    for index,row in enumerate(rows):
        image=load(row['source'],row['sha256']);x,y,w,h=row['box'];crop=image[y:y+h,x:x+w]
        for width in (575,702,835):
            cases.append((f'{index}:width-{width}',cv2.resize(crop,(width,round(h*width/w))),row['expected'],row['source']))
        cases.append((f'{index}:dim70',np.uint8(crop.astype(float)*.7),row['expected'],row['source']))
        if len(row['expected'])==5:
            for pos in (0,1,2):
                altered=crop.copy();cx,cy,cw,ch=row['result']['candidates'][pos]
                altered[cy-2:cy+ch+2,cx-2:cx+cw+2]=(160,65,30)
                cases.append((f'{index}:occluded-card-{pos}',altered,None,row['source']))
    source='_8C143E80-F85C-4DE6-ADCD-0641771AE2E6__2a4e7ea0.png'
    image=load(source);crop=image[54:54+1237,703:703+703]
    for width in (575,703,835):
        cases.append((f'eight:width-{width}',cv2.resize(crop,(width,round(1237*width/703))),['2s','8h','5h'],source))
    def evaluate(case):
        name,image,expected,source=case;result=json.loads(json.dumps(read_board(image)))
        accepted=result['status']=='EXPERIMENTAL_BOARD'
        outcome=('correct' if result['cards']==expected else 'wrong') if accepted else 'abstained'
        prior=previous.get(name)
        return dict(case=name,source=source,source_split='training_source' if sources[source] in training else 'source_disjoint',expected=expected,outcome=outcome,
                    reference_outcome=prior['outcome'] if prior else None,exact_result_parity=result==prior['result'] if prior else None,result=result)
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(evaluate,cases))
    errors=[]
    if OCR_ONLY_RANKS!=frozenset({'A','4','3','8'}):errors.append('PROTECTED_RANK_SET_CHANGED')
    for r in results:
        if r['outcome']=='wrong':errors.append(r['case']+':WRONG_ACCEPTED')
        if r['exact_result_parity'] is False:errors.append(r['case']+':RESULT_PARITY_CHANGED')
        if r['case'].startswith('eight:') and r['outcome']!='correct':errors.append(r['case']+':EIGHT_REGRESSION')
        if r['case'] in ('2:width-575','4:width-702') and r['outcome']!='abstained':errors.append(r['case']+':KNOWN_AMBIGUITY_CHANGED')
    report=dict(scope='26 transformed board calls on six reused real sources. 23 compared exactly with the previous expanded-atlas result; three positive-eight calls. Source-disjoint means excluded from glyph atlas, not untouched holdout. Detector bypassed. Parallel execution is not latency measurement.',
                reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),protected_ranks=sorted(OCR_ONLY_RANKS),sources=sources,
                summary={key:sum(r['outcome']==key for r in results) for key in ('correct','wrong','abstained')},errors=errors,results=results)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2))
    print(report['summary']);print('exact_parity',sum(r['exact_result_parity'] is True for r in results),'/23');print('errors',errors)
    return bool(errors)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference',type=Path,default=ROOT/'docs/table-reading/board-expanded-atlas-regression.json')
    a=p.parse_args();raise SystemExit(run(a.assets,a.output,a.reference))
