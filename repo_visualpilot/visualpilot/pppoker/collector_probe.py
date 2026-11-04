"""Explicit laboratory probe: two synthetic frames to loopback, no screen capture."""
import argparse
import json
import os
from pathlib import Path
import sys

import numpy as np

from visualpilot.pppoker.stream_node import FrameSender
from visualpilot.pppoker.transport_freshness import VERSION


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--nonce',required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args(argv)
    if not 1<=args.port<=65535:parser.error('Invalid loopback port')
    if len(args.nonce)!=32 or any(c not in '0123456789abcdef' for c in args.nonce):
        parser.error('Nonce must contain 32 hexadecimal characters')
    sender=FrameSender('127.0.0.1',args.port,'lab-'+args.nonce)
    report=dict(status='failed',nonce=args.nonce,pid=os.getpid(),protocol=VERSION,
                executable=sys.executable,frozen=bool(getattr(sys,'frozen',False)),
                collector_session=sender.session,acknowledged_frames=0)
    item=dict(table_key='transport-probe')
    try:
        for sequence in (1,2):
            if not sender.before_capture(item):raise RuntimeError(sender.last_error)
            # The fixture is produced only after the normal pre-capture ticket.
            rgb=np.full((40,30,3),sequence,dtype=np.uint8)
            if not sender.send(item,rgb):raise RuntimeError(sender.last_error)
        # A next ticket is issued only after accepting the previous frame. A
        # successful socket write alone does not count as acceptance by Central.
        if not sender.before_capture(item):raise RuntimeError(sender.last_error)
        report.update(status='passed',acknowledged_frames=2)
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
    finally:
        sender.close()
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
