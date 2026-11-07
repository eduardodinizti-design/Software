"""Source parity over all chip-EV unopened 15/25bb study nodes; not solver validation."""
import argparse
import json
from pathlib import Path
from preflop_study import RangeBook, exported_example, study_tables


def physical_cards(key):
    return [key[0]+'c', key[1]+('c' if key.endswith('s') else 'd')]


def validate(path):
    book = RangeBook(path)
    nodes = [n for n in book.nodes if n['spot']=='open_raise'
             and n['context']['mode']=='chip_ev' and n['context']['stack'] in (15,25)
             and n['context']['players']==9 and n['context']['stage']=='mid']
    tested, out_of_range, failures = 0, 0, []
    for n in nodes:
        for i,hand in enumerate(book.hands):
            scene = exported_example(book,n['id'],physical_cards(hand))
            result = study_tables([scene],book)[0]
            tested += 1
            if i in n.get('outOfRange',[]):
                ok = result.get('reason')=='HAND_OUT_OF_RANGE'
                out_of_range += 1
            else:
                expected = [dict(action=a,frequency=n['freq'][a][i]) for a in n['actions'] if n['freq'][a][i]>0]
                st = result.get('strategy') or {}
                ok = (result['status']=='STUDY_ONLY' and st.get('mix')==expected
                      and st.get('execution_allowed') is False and st.get('sizing') is None
                      and result['state']['chip_conservation'])
            if not ok:
                failures.append(dict(node=n['id'],hand=hand,result=result))
    return dict(scope='OFFLINE_EXPORTED_SCENARIO_PARITY_NOT_SOLVER_OR_WINDOWS_VALIDATION',
                provenance=book.provenance,nodes=len(nodes),queries=tested,
                out_of_range=out_of_range,failures=len(failures),examples=failures[:10],
                passed=bool(nodes) and tested>0 and not failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ranges',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    report = validate(args.ranges)
    output = Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
