import sys,types,json,cv2,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
parser=argparse.ArgumentParser(description='Compare current detector with a supplied prior module snapshot; counts are not precision/recall.')
parser.add_argument('--before',required=True);parser.add_argument('--assets',required=True);parser.add_argument('--output',required=True)
args=parser.parse_args()
from table_reading.automatic_table_crops import detect_table_crops
m=types.ModuleType('table_reading.proposals_before');m.__package__='table_reading';sys.modules[m.__name__]=m;exec(Path(args.before).read_text(),m.__dict__)
rows=[]
for p in sorted(Path(args.assets).glob('*.png')):
 im=cv2.cvtColor(cv2.imread(str(p)),cv2.COLOR_BGR2RGB);b=[r.to_dict() for r in m.detect_table_crops(im)];a=[r.to_dict() for r in detect_table_crops(im)];rows.append(dict(source=p.name,before=b,after=a))
 if b!=a:print(p.name,'before',[(r['box'],r['status'])for r in b],'after',[(r['box'],r['status'])for r in a])
Path(args.output).write_text(json.dumps(rows,indent=2))
print('totals',*[sum(r['status']=='COMPLETE_CANDIDATE' for s in rows for r in s[k]) for k in ['before','after']])
