"""Interface da coleta PPPoker; usa exclusivamente percepção passiva."""
from queue import Empty, Queue
from time import monotonic
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk

from .runtime_bridge import session_factory


class PPPokerApp:
    def __init__(self, root, output='sessions'):
        self.root = root
        self.output_root = Path(output)
        self.worker = None
        self.stop_event = threading.Event()
        self.events = Queue(128)
        self.rows = {}
        self.exclusions = ()
        self.closing = False
        root.title('Visual Pilot • PPPoker • Observação')
        root.geometry('1250x700')
        root.minsize(950, 550)
        panel = ttk.Frame(root, padding=18)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='VISUAL PILOT', font=('Segoe UI', 22, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='PPPoker · mesas visíveis · somente observação · fichas fictícias').pack(anchor='w', pady=(4, 16))
        controls = ttk.Frame(panel)
        controls.pack(fill='x')
        self.start_button = ttk.Button(controls, text='Iniciar', command=self.start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(controls, text='Parar', command=self.halt, state='disabled')
        self.stop_button.pack(side='left', padx=8)
        self.status = tk.StringVar(value='Pronto. Clique em Iniciar. Mantenha este painel fora das mesas; tema azul e baralho de quatro cores.')
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
        ttk.Label(panel, text='F12: parar · Leituras expiram após 5s · Sem recomendações ou cliques · Até seis mesas', wraplength=1150).pack(anchor='w', pady=8)
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
        self.status.set('Buscando mesas nos monitores. Inicializando dois processos OCR…')

    def update_exclusions(self):
        # Snapshot Tk somente na thread de interface; a captura recebe tuplas imutáveis.
        self.root.update_idletasks()
        self.exclusions = ((self.root.winfo_rootx(), self.root.winfo_rooty(),
                            self.root.winfo_width(), self.root.winfo_height()),)

    def halt(self):
        self.stop_event.set()
        self.stop_button.configure(state='disabled')
        self.status.set('Finalizando sessão e salvando métricas…')

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
                failures = [r for r in event['value'].get('reports', []) if r.get('state') == 'error']
                self.status.set(f'{len(active)} mesas capturadas · {len(tables)} rastreamentos · ' +
                                ('falha em monitor: ' + '; '.join(r.get('error', '?') for r in failures) if failures else 'Captura a cada 0,5s; leitura OCR tem ritmo próprio.'))
            elif kind in ('reading', 'partial_cards') and not self.stop_event.is_set():
                self.rows[event['table']] = event
            elif kind == 'finished':
                self.stop_event.set()
                metrics = event['metrics']
                self.status.set((f"Erro: {event['error']} · " if event.get('error') else '') +
                                f"Sessão encerrada · OCR: {metrics['ocr']} · erros: {metrics['errors']} · "
                                f"expiradas: {metrics['stale']} · Hero lido: {metrics.get('coverage', {}).get('hero_read', 0)}/{metrics.get('coverage', {}).get('published', 0)}")
                self.folder.set(f"Sessão salva: {Path(event['folder']).resolve()}")
        names = {'confirmed': 'confirmado', 'observed': 'lido, confirmando', 'pending': 'pendente', 'not_dealt': 'sem cartas'}
        for key, event in self.rows.items():
            reading = event['reading']
            age = max(0, monotonic() - event['observed'])
            valid = age <= 5 and not self.stop_event.is_set()
            fields = event.get('field_confirmation', {})
            quality = ' · '.join(label + ': ' + names.get(fields.get(field, {}).get('state'), 'pendente')
                                 for field, label in [('hero', 'Hero'), ('board', 'Board')])
            if not valid:
                quality = 'Parado' if self.stop_event.is_set() else 'Expirada; aguardando leitura'
            item = getattr(self, 'locations', {}).get(key, {})
            values = (event['number'], item.get('monitor', '?'),
                      ' '.join(reading.get('hero', [])) or 'pendente',
                      ' '.join(reading.get('board', [])) or 'pendente', reading.get('street') or 'desconhecida', quality, f'{age:.1f}s')
            if not valid:
                values = (values[0], values[1], 'pendente', 'pendente', 'desconhecida', quality, values[-1])
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
        age = monotonic() - event['observed']
        if age > 5 or self.stop_event.is_set():
            value = 'Leitura expirada ou coleta parada. Consulte os registros para revisar a observação anterior.'
        else:
            r = event['reading']
            lines = [f"ID da mão: {r.get('hand_id') or 'pendente'}", f"Pote: {r.get('pot') or 'pendente'}",
                     f"Stack do Hero: {r.get('hero_stack') or 'pendente'}", '\nBotões disponíveis ao Hero:']
            lines.extend('  ' + button for button in r.get('actions', []))
            if not r.get('actions'):
                lines.append('  pendente')
            lines.append('\nEtiquetas visíveis dos jogadores (não são histórico completo):')
            lines.extend(f"  {action.get('player_label') or 'nome pendente'}: {action['action']}" for action in r.get('observed_actions', []))
            if not r.get('observed_actions'):
                lines.append('  nenhuma etiqueta reconhecida')
            lines.extend(['', r.get('hero_reason') or '', r.get('reason') or ''])
            value = '\n'.join(lines)
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', value)
        self.text.configure(state='disabled')
