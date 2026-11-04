from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    HAS_TKINTER = True
except ImportError:
    tk = None  # type: ignore
    filedialog = None  # type: ignore
    messagebox = None  # type: ignore
    ttk = None  # type: ignore
    HAS_TKINTER = False

# Suporte para execução direta: python repo_visualpilot/visualpilot/app.py
if __package__ is None or __package__ == "":
    _repo_dir = Path(__file__).resolve().parent.parent
    if str(_repo_dir) not in sys.path:
        sys.path.insert(0, str(_repo_dir))
    __package__ = "visualpilot"

try:
    import pytesseract

except ImportError:
    pytesseract = None

try:
    from .collector import Collector
    from .vision import Profile
except Exception as _import_err:
    Collector = None  # type: ignore
    Profile = None    # type: ignore
    _COLLECTOR_IMPORT_ERROR = str(_import_err)
else:
    _COLLECTOR_IMPORT_ERROR = None

try:
    from .boot_logger import (
        run_preflight_diagnostics,
        log_boot_event,
        TEMP_LOG_FILE,
        LOCAL_LOG_FILE,
    )
except Exception:
    def run_preflight_diagnostics(name: str = "app") -> bool:
        return True
    def log_boot_event(*args, **kwargs) -> None:
        pass
    TEMP_LOG_FILE = Path("/tmp/visualpilot_boot_debug.log")
    LOCAL_LOG_FILE = Path("logs/startup_debug.log")



class Application:
    def __init__(self, root, args):
        self.root = root
        self.args = args
        self.collector = None
        self.closing = False
        root.title('Visual Pilot • Coleta de simulações')
        root.geometry('1120x700')
        root.minsize(900, 550)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview', rowheight=32)
        container = ttk.Frame(root, padding=24)
        container.pack(fill='both', expand=True)
        ttk.Label(container, text='VISUAL PILOT', font=('Segoe UI', 22, 'bold')).pack(anchor='w')
        ttk.Label(container, text='Observação de mesas • Fichas fictícias • Sem execução de jogadas').pack(anchor='w', pady=(4, 20))
        controls = ttk.Frame(container)
        controls.pack(fill='x')
        last_profile = ''
        try:
            last_profile = json.loads(Path('.visualpilot.json').read_text(encoding='utf-8')).get('profile', '')
        except (OSError, ValueError, AttributeError):
            pass
        self.profile_path = tk.StringVar(value=args.profile or last_profile)
        ttk.Label(controls, text='Perfil:').pack(side='left')
        self.entry = ttk.Entry(controls, textvariable=self.profile_path, width=55)
        self.entry.pack(side='left', padx=8)
        self.browse = ttk.Button(controls, text='Selecionar', command=self.choose)
        self.browse.pack(side='left')
        self.start_button = ttk.Button(controls, text='Iniciar', command=self.start)
        self.start_button.pack(side='left', padx=(20, 8))
        self.stop_button = ttk.Button(controls, text='Parar', command=self.stop, state='disabled')
        self.stop_button.pack(side='left')
        self.status = tk.StringVar(value='Selecione um perfil calibrado para iniciar. Leituras incertas ficam pendentes.')
        ttk.Label(container, textvariable=self.status, wraplength=1050).pack(anchor='w', pady=16)
        columns = ('table', 'monitor', 'hero', 'board', 'stage', 'quality', 'age')
        self.tree = ttk.Treeview(container, columns=columns, show='headings', height=7)
        labels = ('Mesa / estado', 'Monitor', 'Hero', 'Board', 'Etapa', 'Lidos / pendentes', 'Idade')
        for key, label, width in zip(columns, labels, (160, 65, 145, 180, 90, 130, 70)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=50)
        self.tree.pack(fill='x')
        self.tree.bind('<<TreeviewSelect>>', lambda _: self.show_details())
        ttk.Label(container, text='Contexto, botões do Hero e ações observadas', font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(20, 8))
        self.details = tk.Text(container, height=10, wrap='word', state='disabled', font=('Consolas', 10))
        self.details.pack(fill='both', expand=True)
        self.footer = tk.StringVar(value=f'Sessões: {Path(args.output).resolve()}')
        ttk.Label(container, textvariable=self.footer, wraplength=1050).pack(anchor='w', pady=(12, 0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(250, self.refresh)

    def choose(self):
        path = filedialog.askopenfilename(filetypes=[('Perfil Visual Pilot', '*.json')])
        if path:
            self.profile_path.set(path)

    def start(self):
        try:
            profile = Profile.load(self.profile_path.get())
            # Verifica o executável antes da sessão quando o perfil utiliza OCR.
            if profile.data.get('text_fields') or profile.data.get('hero_buttons') or profile.data.get('players'):
                if pytesseract is None:
                    raise RuntimeError("A biblioteca 'pytesseract' não está instalada no ambiente Python.\nExecute: pip install pytesseract\nou execute o script: setup_environment.bat")
                pytesseract.get_tesseract_version()
            self.collector = Collector(profile, self.args.output, self.args.replay, self.args.interval)
            self.collector.start()
            try:
                Path('.visualpilot.json').write_text(json.dumps({'profile': str(profile.path)}), encoding='utf-8')
            except OSError:
                pass  # Preferência local opcional; não impede a coleta.
            self.tree.delete(*self.tree.get_children())
        except Exception as exc:
            messagebox.showerror('Não foi possível iniciar', str(exc))

    def stop(self):
        if self.collector:
            self.collector.stop()
            self.status.set('Finalizando e salvando sessão…')

    def close(self):
        self.closing = True
        self.stop()
        if not self.collector or not self.collector.thread or not self.collector.thread.is_alive():
            self.root.destroy()

    def refresh(self):
        if self.collector:
            state = self.collector.snapshot()
            alive = self.collector.thread.is_alive()
            self.start_button.configure(state='disabled' if alive else 'normal')
            self.stop_button.configure(state='normal' if alive else 'disabled')
            self.entry.configure(state='disabled' if alive else 'normal')
            self.browse.configure(state='disabled' if alive else 'normal')
            metrics = state.get('metrics', {})
            self.status.set(state['error'] or f"{'Reprodução' if self.args.replay else 'Captura'}: {state['status']} | "
                            f"{metrics.get('cycles', 0)} ciclos | último ciclo {metrics.get('last_cycle_ms', 0)} ms | "
                            f"{metrics.get('over_budget_cycles', 0)} ciclos acima do intervalo")
            for key, table in state['tables'].items():
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(table['timestamp'])).total_seconds()
                cards = lambda values: ' '.join(v['value'] or ('—' if v['status'] == 'empty' else 'pendente') for v in values)
                board_cards = ' '.join(v['value'] or ('—' if v['status'] == 'empty' else '?') for v in table['board'])
                row = (key + ('' if table['visible'] else ' · ausente'), table['monitor'], cards(table['hero_cards']),
                       board_cards, table['stage']['value'] or 'desconhecida',
                       f"{table['recognized']} / {table['pending']}", f'{age:.1f}s')
                if self.tree.exists(key):
                    self.tree.item(key, values=row)
                else:
                    self.tree.insert('', 'end', iid=key, values=row)
            self.show_details()
            if state['session']:
                self.footer.set(f"Registros e evidências: {Path(state['session']).resolve()}")
            if self.closing and not alive:
                self.root.destroy()
                return
        self.root.after(250, self.refresh)

    def show_details(self):
        selected = self.tree.selection()
        if not selected or not self.collector:
            return
        table = self.collector.snapshot()['tables'].get(selected[0])
        if not table:
            return
        def display(reading):
            return str(reading['value']) if reading['value'] is not None else 'pendente (' + reading.get('reason', 'ilegível') + ')'

        labels = {'hand_id': 'Mão', 'pot': 'Pote', 'stack': 'Stack do Hero', 'table_name': 'Nome da mesa'}
        lines = [f"{labels[key]}: {display(reading)}" for key, reading in table['context'].items()]
        lines.append('\nBotões do Hero:')
        for button in table['hero_buttons']:
            action = button['value']
            lines.append('  ' + ((action['action'] + ' ' + (action['amount'] or '')).strip() if action else display(button)))
        if not table['hero_buttons']:
            lines.append('  pendente: regiões não configuradas')
        lines.append('\nAções observadas dos jogadores:')
        for player in table['players']:
            action = player['action']['value']
            action_label = ((action['action'] + ' ' + (action['amount'] or '')).strip() if action else display(player['action']))
            suffix = '' if player['association'] == 'recognized' else ' [associação pendente]'
            lines.append(f"  Assento {player['seat']} • {display(player['name'])}: {action_label}{suffix}")
        if not table['players']:
            lines.append('  pendente: regiões não configuradas')
        lines.append('\nBoard: ? = pendente; — = slot vazio confirmado. Ações são amostras visuais, não histórico completo.')
        value = '\n'.join(lines)
        self.details.configure(state='normal')
        self.details.delete('1.0', 'end')
        self.details.insert('1.0', value)
        self.details.configure(state='disabled')


def _log_app_startup(msg: str) -> None:
    try:
        import tempfile
        log_file = Path(tempfile.gettempdir()) / "visualpilot_app_debug.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def main():
    import traceback
    try:
        log_boot_event("APP", f"Iniciando visualpilot.app | Python: {sys.executable} | CWD: {Path.cwd()}")
        _log_app_startup(f"Iniciando visualpilot.app | Python: {sys.executable} | CWD: {Path.cwd()}")

        # Executa a esteira de pré-voo com auditoria de caminhos, permissões e dependências
        preflight_ok = run_preflight_diagnostics("visualpilot.app")

        parser = argparse.ArgumentParser(description='Coleta observacional para mesas simuladas')
        parser.add_argument('--profile', help='Perfil JSON calibrado')
        parser.add_argument('--output', default='sessions')
        parser.add_argument('--replay', help='Pasta com sequência PNG em ordem alfabética')
        parser.add_argument('--interval', type=float, default=1.0)
        parser.add_argument('--tesseract', help='Caminho do tesseract.exe se não estiver no PATH')
        parser.add_argument('--headless', action='store_true', help='Executar coleta sem interface (Ctrl+C para parar)')
        args = parser.parse_args()

        if not preflight_ok:
            err_details = (
                "Foram detectadas pendências críticas (dependências ausentes, caminhos ou permissões).\n"
                "Para solucionar, execute o script no terminal CMD:\n"
                "    corrigir_instalacao.bat\n"
                "ou:\n"
                "    pip install -r requirements.txt\n\n"
                f"Relatório completo registrado em: {TEMP_LOG_FILE}"
            )
            print(f"\n[FALHA DE AMBIENTE]\n{err_details}\n", file=sys.stderr)
            try:
                root_err = tk.Tk()
                root_err.withdraw()
                messagebox.showerror(
                    "VisualPilot - Dependências Ausentes",
                    "Bibliotecas Python obrigatórias não foram encontradas!\n\n"
                    "Execute 'corrigir_instalacao.bat' ou 'setup_environment.bat' "
                    "para instalar PyAutoGUI, PyGetWindow, Pillow, OpenCV, etc.\n\n"
                    f"Consulte o arquivo de log: {TEMP_LOG_FILE}",
                )
                root_err.destroy()
            except Exception:
                pass
            if sys.stdin and sys.stdin.isatty():
                input("\nPressione ENTER para fechar...")
            sys.exit(1)

        if args.tesseract:
            if pytesseract is not None:
                pytesseract.pytesseract.tesseract_cmd = args.tesseract
            else:
                print("[AVISO] pytesseract não está instalado. Argumento --tesseract ignorado.")

        if not args.profile and not args.replay:
            from .pppoker.capture import enable_dpi_awareness
            enable_dpi_awareness()
            if args.headless:
                import threading
                from queue import Queue
                from .pppoker.runtime_bridge import session_factory
                stop = threading.Event()
                events = Queue(128)
                session = session_factory(args.output, stop, events)
                worker = threading.Thread(target=session.run, daemon=False)
                worker.start()
                try:
                    while worker.is_alive():
                        worker.join(.2)
                except KeyboardInterrupt:
                    stop.set()
                    worker.join()
                finished = None
                while not events.empty():
                    event = events.get_nowait()
                    if event['kind'] == 'finished':
                        finished = event
                if not finished:
                    raise SystemExit('Sessão encerrada sem confirmação de salvamento')
                print(finished['error'] or f"Sessão salva: {finished['folder']}")
                if finished['error']:
                    raise SystemExit(1)
            else:
                from .pppoker.app import PPPokerApp
                root = tk.Tk()
                PPPokerApp(root, args.output)
                root.mainloop()
            return
        if args.headless:
            if not args.profile:
                parser.error('--headless exige --profile')
            if Collector is None or Profile is None:
                raise RuntimeError(f"Módulo de visão/coleta indisponível: {_COLLECTOR_IMPORT_ERROR}")
            collector = Collector(Profile.load(args.profile), args.output, args.replay, args.interval)
            collector.start()
            try:
                while collector.thread.is_alive():
                    collector.join(.2)
            except KeyboardInterrupt:
                collector.stop()
                collector.join()
            state = collector.snapshot()
            print(state['error'] or f"Sessão salva: {state['session']}")
            if state['error']:
                raise SystemExit(1)
        else:
            if Collector is None or Profile is None:
                raise RuntimeError(f"Módulo de visão/coleta indisponível: {_COLLECTOR_IMPORT_ERROR}")
            root = tk.Tk()
            Application(root, args)
            root.mainloop()
    except Exception as exc:
        err_msg = f"ERRO CRÍTICO NA EXECUÇÃO DE visualpilot.app:\n{traceback.format_exc()}"
        _log_app_startup(err_msg)
        log_boot_event("FATAL", "Exceção não tratada em visualpilot.app", details=traceback.format_exc(), status="FAIL")
        print(f"\n======================================================\n{err_msg}\n======================================================", file=sys.stderr)
        if sys.stdin and sys.stdin.isatty():
            input("\nPressione ENTER para fechar...")
        raise


if __name__ == '__main__':
    main()

