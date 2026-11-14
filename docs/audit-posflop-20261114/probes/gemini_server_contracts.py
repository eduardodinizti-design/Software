"""Local HTTP reproduction, no Python executable and no client input.

The preload changes only host/port. PATH intentionally contains no python3.
No /api/analyze-hands request is sent and no data goes to Gemini.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args()
root=args.root.resolve();node=shutil.which('node')
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
with tempfile.TemporaryDirectory() as folder:
    folder=Path(folder);bin_dir=folder/'bin';bin_dir.mkdir();(bin_dir/'node').symlink_to(node)
    env=dict(os.environ,PATH=str(bin_dir),NODE_ENV='production',AUDIT_LOCAL_PORT=str(port))
    log=folder/'server.log'
    with log.open('w') as output:
        proc=subprocess.Popen([node,'--import',str(Path(__file__).with_name('server_loopback_preload.mjs')),
            '--import','tsx','server.ts'],cwd=root,env=env,stdout=output,stderr=subprocess.STDOUT)
        def request(route,data=None):
            req=urllib.request.Request(f'http://127.0.0.1:{port}/api/'+route,
                data=json.dumps(data).encode() if data is not None else None,
                headers={'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(req,timeout=2) as r:return {'http':r.status,'body':json.load(r)}
            except urllib.error.HTTPError as e:return {'http':e.code,'body':json.load(e)}
        try:
            ready=False
            for _ in range(80):
                if proc.poll() is not None:break
                try:request('bot/status');ready=True;break
                except (OSError,urllib.error.URLError):time.sleep(.1)
            if not ready:raise RuntimeError('Test server did not start: '+log.read_text()[-1500:])
            default_ui=request('bot/start',{'hwnd':'0x12FA, 0x34BC','bounty':True,'overlay':True,'mouse':True})
            try:no_python=request('bot/start',{'hwnd':'0x1234','overlay':False,'mouse':False,'bounty':False})
            except Exception as e:no_python={'client_error':str(e)}
            try:code=proc.wait(timeout=4)
            except subprocess.TimeoutExpired:code=None
            result=dict(scope='Isolated loopback server, nonexistent Python executable, no real input/registration/AI request.',
                default_ui_start=default_ui,missing_python_start=no_python,server_exit_after_spawn_error=code,
                spawn_error_seen='spawn python3 ENOENT' in log.read_text())
            print(json.dumps(result,ensure_ascii=False,indent=2))
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=4)
