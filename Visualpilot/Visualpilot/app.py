"""Interface da coleta PPPoker; usa exclusivamente percepção passiva."""
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk
from queue import Queue, Empty
from pathlib import Path
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pppoker.runtime_bridge import session_factory

class VisualPilotApp:
    def __init__(self, root: tk.Tk, output_root: Path):
        self.root = root
        self.root.title("VisualPilot - Central Operacional PPPoker")
        self.root.geometry("1200x750")
        self.output_root = output_root
        self.worker: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.events = Queue(128)
        self.rows: dict[str, dict] = {}
        self.exclusions = ()
        self.closing = False

        style = ttk.Style()
        style.theme_use('clam')

        panel = ttk.Frame(root, padding=16)
        panel.pack(fill='both', expand=True)

        header = ttk.Label(panel, text='VisualPilot - Central Operacional PPPoker', font=('Segoe UI', 16, 'bold'))
        header.pack(anchor='w', pady=(0, 10))

        controls = ttk.Frame(panel)
        controls.pack(fill='x', pady=8)

        self.start_button = ttk.Button(controls, text='Iniciar', command=self.start)
        self.start_button.pack(side='left')
        
        self.stop_button = ttk.Button(controls, text='Parar', command=self.halt, state='disabled')
        self.stop_button.pack(side='left', padx=8)

        self.status = tk.StringVar(value='Pronto. Clique em Iniciar. Mantenha este painel fora das mesas.')
        ttk.Label(panel, textvariable=self.status, wraplength=1150).pack(fill='x', pady=14)

        columns = ('table', 'monitor', 'hero', 'board', 'stage', 'quality', 'age')
        self.tree = ttk.Treeview(panel, columns=columns, show='headings', height=7)
        for col, title, width in zip(columns, ('Mesa', 'Monitor', 'Hero', 'Board', 'Etapa', 'Qualidade', 'Idade'), (65, 65, 145, 180, 90, 360, 65)):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width)
        self.tree.pack(fill='x')
        self.tree.bind('<<TreeviewSelect>>', lambda event: self.details())

        ttk.Label(panel, text='Contexto observado', font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(16, 8))
        self.text = tk.Text(panel, height=10, state='disabled', wrap='word')
        self.text.pack(fill='both', expand=True)

        ttk.Label(panel, text='F12: parar · Leituras expiram após 5s', wraplength=1150).pack(anchor='w', pady=8)
        self.folder = tk.StringVar(value=f'Registros locais: {self.output_root.resolve()}')
        ttk.Label(panel, textvariable=self.folder, wraplength=1150).pack(anchor='w')

        root.bind('<F12>', lambda event: self.halt())
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(150, self.poll)

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        self.stop_event = threading.Event()
        self.events = Queue(128)
        self.rows.clear()
        self.tree.delete(*self.tree.get_children())
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.configure(state='disabled')
        self.update_exclusions()
        session = session_factory(self.output_root, self.stop_event, self.events, lambda: self.exclusions)
        self.worker = threading.Thread(target=session.run, name='pppoker-session', daemon=False)
        self.worker.start()
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.status.set('Buscando mesas nos monitores...')

    def update_exclusions(self):
        self.root.update_idletasks()
        self.exclusions = ((self.root.winfo_rootx(), self.root.winfo_rooty(),
                            self.root.winfo_width(), self.root.winfo_height()),)

    def halt(self):
        self.stop_event.set()
        self.stop_button.configure(state='disabled')
        self.status.set('Finalizando sessão...')

    def close(self):
        self.closing = True
        self.halt()
        if not self.worker or not self.worker.is_alive():
            self.root.destroy()

    def poll(self):
        self.update_exclusions()
        for _ in range(128):
            try:
                event = self.events.get_nowait()
            except Empty:
                break
            kind = event['kind']
            if kind == 'started':
                self.folder.set(f"Sessão: {Path(event['folder']).resolve()}")
            elif kind == 'tables':
                tables = event['value']['tables']
                active = {item['table_key']: item for item in tables if item['state'] == 'capturando'}
                for key in list(self.rows):
                    if key not in active:
                        self.rows.pop(key, None)
                        if self.tree.exists(key):
                            self.tree.delete(key)
                self.locations = active
                self.status.set(f'{len(active)} mesas capturadas · {len(tables)} rastreamentos ativos.')
            elif kind in ('reading', 'partial_cards') and not self.stop_event.is_set():
                self.rows[event['table']] = event
            elif kind == 'finished':
                self.stop_event.set()
                self.status.set('Sessão encerrada.')
        
        for key, event in self.rows.items():
            reading = event['reading']
            age = max(0, monotonic() - event['observed'])
            valid = age <= 5 and not self.stop_event.is_set()
            item = getattr(self, 'locations', {}).get(key, {})
            values = (event['number'], item.get('monitor', '?'),
                      ' '.join(reading.get('hero', [])) or 'pendente',
                      ' '.join(reading.get('board', [])) or 'pendente', reading.get('street') or 'desconhecida', 'OK', f'{age:.1f}s')
            if self.tree.exists(key):
                self.tree.item(key, values=values)
            else:
                self.tree.insert('', 'end', iid=key, values=values)
        self.details()
        if self.worker and not self.worker.is_alive():
            self.start_button.configure(state='normal')
            self.stop_button.configure(state='disabled')
        if self.closing and (not self.worker or not self.worker.is_alive()):
            self.root.destroy()
            return
        self.root.after(150, self.poll)

    def details(self):
        selected = self.tree.selection()
        if not selected:
            return
        event = self.rows.get(selected[0])
        if not event:
            return
        r = event['reading']
        lines = [f"Pote: {r.get('pot') or 'pendente'}", f"Stack do Hero: {r.get('hero_stack') or 'pendente'}"]
        value = '\n'.join(lines)
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', value)
        self.text.configure(state='disabled')

def main():
    root = tk.Tk()
    output_root = Path(os.environ.get('VISUALPILOT_LOGS', 'logs'))
    VisualPilotApp(root, output_root)
    root.mainloop()

if __name__ == '__main__':
    main()