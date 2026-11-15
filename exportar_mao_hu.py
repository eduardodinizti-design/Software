"""Export an existing confirmed hand, verifying its journal hash chain."""
import argparse
import json
from pathlib import Path
from hand_journal import HandJournal


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--journal',default='runtime/hu/hand-history.sqlite3')
    p.add_argument('--table');p.add_argument('--hand');p.add_argument('--output')
    args=p.parse_args(argv)
    if not Path(args.journal).is_file():p.error('Diario ainda nao existe. Inicie o observador HU primeiro.')
    j=HandJournal(args.journal)
    try:
        if not args.table or not args.hand:
            rows=j.db.execute('SELECT table_id,hand_id,terminal FROM hands ORDER BY created DESC LIMIT 50').fetchall()
            print(json.dumps([dict(table=t,hand=h,closed=bool(c)) for t,h,c in rows],ensure_ascii=False,indent=2));return 0
        out=j.export_hand(args.table,args.hand)
        if not out['events']:p.error('Mao sem eventos confirmados neste diario')
        text=json.dumps(out,ensure_ascii=False,indent=2)
        if args.output:
            path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
            print(str(path.resolve()))
        else:print(text)
    finally:j.close()
    return 0


if __name__=='__main__':raise SystemExit(main())
