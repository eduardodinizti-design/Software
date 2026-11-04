"""Retain integration evidence before temporary sessions are removed."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile

EVIDENCE_ROOT = Path(__file__).resolve().parents[1] / 'diagnostics' / 'integration'


@contextmanager
def session_directory(name):
    with tempfile.TemporaryDirectory() as folder:
        failed = False
        try:
            yield folder
        except BaseException:
            failed = True
            raise
        finally:
            if failed or os.environ.get('VISUALPILOT_LAB_KEEP_EVIDENCE') == '1':
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                destination = EVIDENCE_ROOT / f'{name}-{stamp}'
                try:
                    shutil.copytree(folder, destination)
                    environment = dict(python=sys.version, platform=platform.platform(),
                        cpu_count=os.cpu_count(), commit=os.environ.get('GITHUB_SHA'), failed=failed)
                    if hasattr(os, 'sched_getaffinity'):
                        environment['cpu_affinity'] = sorted(os.sched_getaffinity(0))
                    (destination/'environment.json').write_text(
                        json.dumps(environment, indent=2), encoding='utf-8')
                    print(f'LAB_EVIDENCE {destination}', flush=True)
                    print('LAB_ENVIRONMENT ' + json.dumps(environment), flush=True)
                    for path in destination.rglob('metricas.json'):
                        metrics = json.loads(path.read_text(encoding='utf-8'))
                        print('LAB_METRICS ' + json.dumps(metrics, ensure_ascii=False), flush=True)
                    for path in destination.rglob('rejeicoes.jsonl'):
                        for line in path.read_text(encoding='utf-8').splitlines()[-10:]:
                            print('LAB_REJECTION ' + line, flush=True)
                except Exception as exc:
                    # An evidence write error must not replace the original failure.
                    print(f'LAB_EVIDENCE_ERROR {type(exc).__name__}: {exc}', flush=True)
