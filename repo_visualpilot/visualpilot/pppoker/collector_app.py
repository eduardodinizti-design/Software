"""Visible setup and diagnostics for the normal desktop collector entry point."""
import configparser
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import threading
from time import monotonic

from visualpilot.pppoker.multitable import observe_tables
from visualpilot.pppoker.stream_node import FrameSender, encoding_settings
from visualpilot.pppoker.stream_control import ControlSender, HEARTBEAT_INTERVAL


def settings(host, port, member):
    host, member = host.strip(), member.strip()
    if not host or host in ('0.0.0.0', '::') or any(c.isspace() for c in host) or '/' in host:
        raise ValueError('Informe o IPv4 ou nome do notebook onde a Central está aberta.')
    if not member or len(member) > 128 or member.upper().startswith('INFORME'):
        raise ValueError('Informe o ID do membro. O texto de exemplo não é uma configuração válida.')
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise ValueError('A porta deve ser um número entre 1 e 65535.') from None
    if not 1 <= port <= 65535:
        raise ValueError('A porta deve ser um número entre 1 e 65535.')
    return dict(host=host, port=port, member=member)


def read_settings(path):
    config = configparser.ConfigParser(interpolation=None)
    config.read(path, encoding='utf-8-sig')
    return dict(host=config.get('central', 'host', fallback=''),
                port=config.get('central', 'port', fallback='48735'),
                member=config.get('member', 'id', fallback=''))


def read_encoding_settings(path):
    config = configparser.ConfigParser(interpolation=None)
    config.read(path, encoding='utf-8-sig')
    return encoding_settings(config.get('transport', 'image_codec', fallback='png').strip().lower(),
                             config.getint('transport', 'jpeg_quality', fallback=100))


def save_settings(path, values):
    values = settings(**values)
    config = configparser.ConfigParser(interpolation=None)
    if path.exists():
        try:
            config.read(path, encoding='utf-8-sig')
        except configparser.Error:
            # The user explicitly pressed Save; retain the invalid original.
            backup = path.with_name(path.name + '.invalid-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
            backup.write_bytes(path.read_bytes())
            config = configparser.ConfigParser(interpolation=None)
    for section in ('central', 'member'):
        if not config.has_section(section):
            config.add_section(section)
    config.set('central', 'host', values['host'])
    config.set('central', 'port', str(values['port']))
    config.set('member', 'id', values['member'])
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as file:
        config.write(file)
    temporary.replace(path)
    return values


class Collector:
    def __init__(self, root, *, observe=observe_tables, sender_factory=FrameSender, control_factory=ControlSender):
        self.root = Path(root)
        self.observe, self.sender_factory = observe, sender_factory
        self.control_factory=control_factory
        self.control_thread=None
        self.control_error=None
        self.discovery_state='pending'
        self.stop = threading.Event()
        self.thread = None
        self.sender = None
        self.failed = False
        self.lock = threading.Lock()
        self.state = dict(phase='setup', message='Configure a conexão com a Central.',
                          frames_sent=0, tables=[], reports=[], pid=os.getpid())
        self.last_write = -1e9
        self.logger = logging.Logger('collector')
        self.handler = RotatingFileHandler(self.root/'collector.log', maxBytes=2*1024*1024,
                                          backupCount=2, encoding='utf-8')
        self.handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        self.logger.addHandler(self.handler)
        self.update(**self.state)

    def update(self, **changes):
        with self.lock:
            old = (self.state.get('phase'), self.state.get('message'))
            self.state.update(changes, at=datetime.now(timezone.utc).isoformat())
            changed = old != (self.state.get('phase'), self.state.get('message'))
            if changed:
                self.logger.info('%s: %s', self.state['phase'], self.state['message'])
            if changed or monotonic()-self.last_write >= 1:
                temporary = self.root/'collector_status.tmp'
                temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding='utf-8')
                temporary.replace(self.root/'collector_status.json')
                self.last_write = monotonic()

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def start(self, values):
        if self.thread and self.thread.is_alive():
            return
        values = settings(**values)
        encoding = read_encoding_settings(self.root/'stream_config.ini')
        self.stop.clear()
        self.failed = False
        self.sender = self.sender_factory(**values, **encoding)
        self.control=self.control_factory((values['host'],values['port']),values['member'],self.sender.session)
        self.control_error=None
        self.discovery_state='pending'
        self.update(phase='connecting', message=f"Conectando à Central em {values['host']}:{values['port']}...",
                    target=f"{values['host']}:{values['port']}", collector_session=self.sender.session,
                    frames_sent=0, tables=[], reports=[], folder=None,
                    control_connected=False,control_error=None,**encoding)
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        self.control_thread=threading.Thread(target=self.run_control,daemon=True)
        self.control_thread.start()
        try:
            # Check connectivity even with no table visible; never retain this ticket.
            while not self.stop.is_set():
                reachable = self.sender.before_capture({'table_key': 'connection-check'})
                self.sender.close()
                if reachable:
                    break
                self.update(phase='connection_error', message=self.network_error())
                self.stop.wait(2)
            if self.stop.is_set():
                self.update(phase='stopped', message='Coleta parada.')
                return
            self.update(phase='discovering', message='Central acessível. Procurando mesas nos monitores...')
            self.observe(self.root/'sessions', self.stop, self, frame_sink=self.send,
                         max_tables=6, interval=.2, before_capture=self.sender.before_capture,
                         tables_sink=self.sender.set_tables)
        except Exception as exc:
            self.failed = True
            self.logger.exception('Falha no Coletor')
            self.update(phase='error', message=f'Falha no Coletor: {exc}')
        finally:
            self.stop.set()
            self.sender.close()
            self.control_thread.join(5)

    def run_control(self):
        while not self.stop.is_set():
            try:
                active,generation=self.sender.membership_snapshot()
                metrics=self.control.exchange(active,generation,self.discovery_state)
                if self.control_error:self.logger.info('Canal de estado reconectado')
                self.control_error=None
                self.update(control_connected=True,control_error=None,**metrics)
            except (OSError,ValueError) as exc:
                error=f'{type(exc).__name__}: {exc}'
                if error!=self.control_error:self.logger.warning('Falha no canal de estado: %s',error)
                self.control_error=error
                self.update(control_connected=False,control_error=error)
            self.stop.wait(HEARTBEAT_INTERVAL)

    def network_error(self):
        return ('Não foi possível conectar à Central. Confira o endereço do notebook, '
                'a porta, o botão Iniciar coleta na Central e a liberação no firewall. '
                f'Detalhe: {self.sender.last_error}')

    def send(self, item, rgb, stamp):
        sent = self.sender.send(item, rgb, stamp)
        if sent:
            with self.lock:
                self.state['frames_sent'] += 1
                self.state.update(self.sender.last_transport)
        return sent

    def put_nowait(self, event):
        """Consume observer status immediately; never discard its final error."""
        if event.get('finished'):
            self.failed = bool(event.get('error'))
            self.update(phase='error' if self.failed else 'stopped',
                        message=f"Falha na captura: {event['error']}" if self.failed else 'Coleta parada.')
            return
        rows = [{k: v for k, v in row.items() if k != 'preview'} for row in event['tables']]
        reports = event['reports']
        errors = [r['error'] for r in reports if r.get('error')]
        self.discovery_state=('error' if errors or (not reports and event.get('discovery_complete'))
                              else 'ready' if reports else 'pending')
        if self.sender.last_error:
            phase, message = 'connection_error', self.network_error()
        elif self.control_error:
            phase, message = 'connection_error', 'Central sem confirmação do estado do Coletor: '+self.control_error
        elif errors:
            phase, message = 'capture_error', 'Falha ao examinar monitor: ' + '; '.join(errors)
        elif not reports and event.get('discovery_complete'):
            phase, message = 'capture_error', 'Nenhum monitor disponível para captura nesta sessão do Windows.'
        elif not reports:
            phase, message = 'discovering', 'Central acessível. Procurando mesas nos monitores...'
        elif not rows:
            phase, message = 'no_tables', 'Central acessível. Nenhuma mesa reconhecida; deixe a mesa visível no PC.'
        elif any(row['state'] == 'capturando' for row in rows):
            phase, message = 'capturing', 'Capturando mesas e enviando imagens à Central.'
        else:
            phase = 'capture_pending'
            message = '; '.join(f"Mesa {r['number']}: {r['state']} {r['detail']}".strip() for r in rows)
        self.update(phase=phase, message=message, tables=rows, reports=reports, folder=event.get('folder'))

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(10)
        self.handler.close()


def main(root):
    import tkinter as tk
    from tkinter import ttk
    from visualpilot.pppoker.capture import enable_dpi_awareness
    enable_dpi_awareness()
    window = tk.Tk()
    window.title('VisualPilot — Coletor')
    window.geometry(f'500x420+{max(20, window.winfo_screenwidth()-520)}+40')
    window.minsize(440, 390)
    frame = ttk.Frame(window, padding=16)
    frame.pack(fill='both', expand=True)
    collector = Collector(root)
    path = Path(root)/'stream_config.ini'
    try:
        values = read_settings(path)
        config_error = None
    except (OSError, configparser.Error) as exc:
        values = dict(host='', port='48735', member='')
        config_error = str(exc)
    fields = {}
    for key, label in [('host', 'Endereço do notebook (Central)'), ('port', 'Porta da Central'), ('member', 'ID do membro')]:
        ttk.Label(frame, text=label).pack(anchor='w')
        fields[key] = tk.StringVar(value=values[key])
        ttk.Entry(frame, textvariable=fields[key]).pack(fill='x', pady=(0, 7))
    message, counts = tk.StringVar(), tk.StringVar()
    ttk.Label(frame, textvariable=message, wraplength=450).pack(anchor='w', pady=10)
    ttk.Label(frame, textvariable=counts).pack(anchor='w')
    controls = ttk.Frame(frame)
    controls.pack(fill='x', pady=12)

    def start():
        try:
            collector.start(save_settings(path, {k: v.get() for k, v in fields.items()}))
        except (ValueError, OSError, configparser.Error) as exc:
            collector.update(phase='setup', message=str(exc))

    start_button = ttk.Button(controls, text='Salvar e iniciar', command=start)
    start_button.pack(side='left')
    ttk.Button(controls, text='Parar', command=collector.stop.set).pack(side='left', padx=8)
    ttk.Label(frame, text='Diagnóstico: collector.log e collector_status.json nesta pasta.',
              wraplength=450).pack(anchor='w')

    def refresh():
        state = collector.snapshot()
        message.set(state['message'])
        counts.set(f"Monitores: {len(state['reports'])}   Mesas: {len(state['tables'])}   Quadros enviados: {state['frames_sent']}")
        start_button.configure(state='disabled' if collector.thread and collector.thread.is_alive() else 'normal')
        window.after(200, refresh)

    try:
        if config_error:
            collector.update(phase='setup', message=f'Não foi possível ler stream_config.ini: {config_error}')
        else:
            try:
                collector.start(settings(**values))
            except ValueError as exc:
                collector.update(phase='setup', message=str(exc))
        refresh()
        window.mainloop()
    finally:
        collector.close()
    return 1 if collector.failed else 0
