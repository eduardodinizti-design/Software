"""Fake input only: controller timing model, imports and blank-frame contract.

No real mouse, screen capture, table, Gemini API or user runtime is accessed.
"""
import argparse
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

import numpy as np

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args()
root=args.root.resolve();bot=root/'python_bot';sys.path[:0]=[str(bot),str(bot/'modules')]
fake=types.ModuleType('pyautogui');fake.position=lambda:types.SimpleNamespace(x=40,y=40)
fake.PAUSE=0.;fake.FAILSAFE=True;fake.moveTo=lambda *a,**k:None;fake.click=lambda *a,**k:None
sys.modules['pyautogui']=fake
mouse=importlib.import_module('modules.mouse_controller')
trials=[]
for steps,use_max in [(20,False),(35,True)]:
    elapsed=[0.];moves=[];clicks=[]
    def move(x,y,**kwargs):moves.append((x,y));elapsed[0]+=fake.PAUSE
    def click(x,y,**kwargs):clicks.append((x,y));elapsed[0]+=fake.PAUSE
    fake.moveTo=move;fake.click=click
    mouse.random.randint=lambda a,b:steps
    mouse.random.uniform=lambda a,b:b if use_max else a
    mouse.time.sleep=lambda delay:elapsed.__setitem__(0,elapsed[0]+delay)
    # Silence the controller's own success print: no OS event has been sent.
    import contextlib,io
    with contextlib.redirect_stdout(io.StringIO()):mouse.HumanizedMouseController.click(100,100)
    trials.append(dict(steps=steps,move_calls=len(moves),click_calls=len(clicks),
        modeled_seconds=round(elapsed[0],6),final_point=moves[-1],target=[100,100]))
try:
    importlib.import_module('modules.engine_bridge')
    bridge={'imported':True}
except Exception as e:bridge={'imported':False,'type':type(e).__name__,'error':str(e)}
ocr=importlib.import_module('modules.ocr_processor');ocr.WIN32_AVAILABLE=False;ocr.MSS_AVAILABLE=True
processor=object.__new__(ocr.PPPokerOCRProcessor)
processor.sct=types.SimpleNamespace(grab=lambda monitor:np.zeros((600,800,4),dtype=np.uint8))
blank=processor.read_cards_and_pot('0x1234')
cli=[]
for flags in [['--help'],['--human-mouse'],['--bounty-bb'],['--overlay']]:
    r=subprocess.run([sys.executable,str(bot/'operar_mesa.py'),'--hwnd','0x1234',*flags],
        cwd=bot,text=True,capture_output=True,timeout=8)
    cli.append(dict(flags=flags,returncode=r.returncode,
        error_tail='\n'.join((r.stderr or r.stdout).splitlines()[-3:])))
print(json.dumps(dict(scope='All mouse/capture operations explicitly mocked; timings model Python waits plus pyautogui.PAUSE, not hardware throughput.',
    timing_trials=trials,engine_bridge=bridge,blank_frame_result=blank,cli=cli),ensure_ascii=False,indent=2))
