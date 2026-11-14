"""Simulated tournament-finish path; never captures or sends input."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import Mock,patch
import numpy as np

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args()
sys.path.insert(0,str(args.root.resolve()))
import operar_mesa as op
from bot_control import BotControl
from table_reading.automatic_table_crops import TableCrop
control=BotControl();advisor=Mock();advisor.manifest.return_value=dict(sources=[],index_keys=0,total_nodes=0,collisions=[])
engine=Mock();engine.capture_frame.return_value=(np.zeros((700,400,3),np.uint8),{'status':'SUCCESS'})
closed=Mock(return_value=True)
with contextlib.ExitStack() as stack:
    changes=dict(configure_ocr=Mock(),PreflopAdvisor=Mock(),BotControl=Mock(return_value=control),
        WindowCaptureEngine=Mock(return_value=engine),
        discover_pppoker=Mock(return_value={'windows':[dict(hwnd=1,x=0,y=0,w=400,h=700)]}),
        detect_table_crops=Mock(return_value=[TableCrop((0,0,400,700),'COMPLETE_CANDIDATE',[],'SIMULATED')]),
        detect_tournament_end=Mock(return_value={'status':'TOURNAMENT_END','ranking':10,'sair_box':[0,0,40,20]}),
        _close_tournament_table=closed,record_tournament_end=Mock())
    changes['PreflopAdvisor'].from_file.return_value=advisor
    for name,value in changes.items():stack.enter_context(patch.object(op,name,value))
    stack.enter_context(patch.object(op.time,'sleep'))
    with contextlib.redirect_stdout(io.StringIO()):op.main(['--hwnd','0x1','--arm','--frames','1','--no-hotkeys'])
allowed=closed.call_args.args[-1]
result=dict(scope='All readers, captures and closing input explicitly mocked; no OS mouse.',
    control_state=control.state,close_called=closed.called,armed_argument_received_by_close=allowed,
    expected='Closing path must not receive input authorization while control is PAUSED.',
    satisfies=not allowed)
print(json.dumps(result,indent=2));raise SystemExit(not result['satisfies'])
