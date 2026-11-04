"""Inicializador congelável que abre o painel Streamlit no navegador."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import socket
import threading
import time
import traceback
from urllib.request import urlopen
import webbrowser

PANEL_URL = 'http://127.0.0.1:8501'


def open_when_ready(timeout=60, opener=urlopen, browser=webbrowser.open):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with opener(PANEL_URL + '/_stcore/health', timeout=1) as response:
                ready = response.status == 200
            if ready:
                browser(PANEL_URL)
                return True
        except OSError:
            pass
        time.sleep(.25)
    return False


def application_dir():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()


BUILD_ID = 'central-live-20261031-r5-png-control'


def check_panel_port(url):
    """Do not mistake an older server's health response for this launch."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    with socket.socket() as probe:
        if sys.platform == 'win32':
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind((parsed.hostname, parsed.port))
        except OSError as exc:
            raise RuntimeError(f'A porta {parsed.port} do painel já está em uso ou indisponível. '
                'Feche as outras instâncias de VisualPilot_Central.exe no Gerenciador de Tarefas '
                'e abra esta Central novamente. Fechar a aba do navegador não encerra o programa.') from exc


def main():
    """Embedded server: never invoke the CLI's email/activation workflow."""
    import contextlib
    import json
    from datetime import datetime, timezone
    from urllib.parse import urlparse
    folder = application_dir()
    os.chdir(folder)
    lock = threading.Lock()
    state = dict(build=BUILD_ID, pid=os.getpid(), executable=sys.executable,
                 validation_token=os.environ.get('VISUALPILOT_VALIDATE_STARTUP', ''))

    def record(phase, **details):
        with lock:
            state.update(phase=phase, at=datetime.now(timezone.utc).isoformat(), **details)
            temporary = folder / 'central_status.tmp'
            temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
            temporary.replace(folder / 'central_status.json')

    # Always log, including double-click starts and redirected console starts.
    with (folder / 'central_startup.log').open('a', encoding='utf-8', buffering=1) as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            record('starting')
            print(f'VisualPilot {BUILD_ID} pid={os.getpid()}', flush=True)
            try:
                check_panel_port(PANEL_URL)
                # The CLI calls check_credentials even in headless mode when an
                # existing credentials.toml is invalid. Embedding bootstrap avoids
                # that optional onboarding, without modifying the user's profile.
                from streamlit import config
                from streamlit.web import bootstrap
                app = Path(__file__).with_name('app.py')
                if getattr(sys, 'frozen', False):
                    app = Path(sys._MEIPASS) / 'visualpilot' / 'viz' / 'app.py'
                if not app.is_file():
                    raise FileNotFoundError(f'Painel ausente: {app}')
                flags = {'server.headless': True, 'server.showEmailPrompt': False,
                         'browser.gatherUsageStats': False, 'global.developmentMode': False,
                         'server.address': '127.0.0.1', 'server.port': urlparse(PANEL_URL).port,
                         'server.enableCORS': True, 'server.enableXsrfProtection': True}
                config._main_script_path = str(app)
                bootstrap.load_config_options(flag_options=flags)
                record('configured', app=str(app), url=PANEL_URL)
                def ready():
                    def opened(url):
                        record('ready')
                        if not state['validation_token']:
                            webbrowser.open(url)
                    if not open_when_ready(browser=opened):
                        print('Painel não respondeu em 60 segundos.', flush=True)
                threading.Thread(target=ready, daemon=True).start()
                bootstrap.run(str(app), False, [], flags)
                record('stopped')
            except BaseException as exc:
                record('failed', error=f'{type(exc).__name__}: {exc}')
                traceback.print_exc()
                if sys.platform == 'win32' and not state['validation_token']:
                    import ctypes
                    ctypes.windll.user32.MessageBoxW(None,
                        'A Central não iniciou.\n' + str(exc) + '\n\nO diagnóstico foi salvo em:\n' + str(folder / 'central_startup.log'),
                        'VisualPilot — erro de inicialização', 16)
                # The error is already logged and, for interactive Windows
                # launches, shown above. A normal nonzero exit also avoids the
                # windowed PyInstaller bootloader opening a second error dialog.
                raise SystemExit(1) from None


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
