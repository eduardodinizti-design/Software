"""Controle compartilhado da sessão remota, independente dos reruns do painel."""
import asyncio
from queue import Queue, Empty
import threading
from time import monotonic
from .monitor import LiveMonitor
from visualpilot.pppoker.observer.runtime import PerceptionSession
from visualpilot.pppoker.stream_receiver import run_remote_session
from visualpilot.pppoker.stream_control import HEARTBEAT_TIMEOUT


class RemoteSession:
    def __init__(self, root='sessions', config='stream_config.ini'):
        self.root, self.config = root, config
        self.thread = None
        self.stop = threading.Event()
        self.output = Queue(100)
        self.tables = {}
        self.error = None
        self.transport_warning = None
        self.folder = None
        self.stale_after = 5.0
        self.monitor = LiveMonitor()
        self.collectors = {}
        self.transport_revision = 0
        self.remote_epochs = {}

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop.clear()
        self.monitor = LiveMonitor()
        self.output = Queue(100)
        self.folder = None
        self.tables.clear()
        self.collectors.clear()
        self.transport_revision = 0
        self.remote_epochs = {}
        self.error = None
        self.transport_warning = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            runtime = PerceptionSession(self.root, self.stop, self.output, monitor=self.monitor)
            asyncio.run(run_remote_session(runtime, self.config))
        except Exception as exc:
            self.error = str(exc)

    def poll(self):
        while True:
            try:
                event = self.output.get_nowait()
            except Empty:
                break
            if event.get('kind') in ('reading', 'partial_cards', 'reading_invalidated'):
                if (event.get('remote_epoch') is not None
                        and event['remote_epoch']!=self.remote_epochs.get(event['table'])):
                    continue
                previous = self.tables.get(event['table'])
                if previous:
                    old_generation, generation = previous.get('generation'), event.get('generation')
                    if (old_generation is not None and generation is not None and generation < old_generation):
                        continue
                    if event.get('observed', -1) < previous.get('observed', -1):
                        continue
                    # A partial for the same source cannot overwrite its consolidated reading.
                    if (event.get('observed') == previous.get('observed') and
                            previous.get('kind') == 'reading' and event.get('kind') == 'partial_cards'):
                        continue
                self.tables[event['table']] = dict(event, received_at=monotonic())
            if event.get('kind') == 'tables':
                status=event['value']
                if 'transport_revision' in status:
                    if status['transport_revision']<self.transport_revision:continue
                    self.transport_revision=status['transport_revision']
                    self.remote_epochs=dict(status['remote_epochs'])
                active = {row['table_key'] for row in event['value']['tables']
                          if row['state'] == 'capturando'}
                self.tables = {key: value for key, value in self.tables.items() if key in active}
            if event.get('kind') == 'collector_status':
                self.collectors[event['member']]=dict(event)
            if event.get('kind') == 'transport_status':
                self.transport_warning=event.get('warning')
            if event.get('folder'):
                self.folder = event['folder']
            if event.get('error'):
                self.error = event['error']
        now = monotonic()
        for state in self.collectors.values():
            state['age_seconds']=max(0.,now-state['observed'])
            state['connected']=state['age_seconds']<=HEARTBEAT_TIMEOUT
        for key, event in list(self.tables.items()):
            stamp = event.get('observed', event.get('received_at', now))
            age = max(0., now - stamp)
            event['age_seconds'] = age
            if age > self.stale_after and not event.get('stale'):
                # Keep the immutable historical record on disk, but never show
                # a disconnected table's old cards as a current observation.
                self.tables[key] = dict(event, stale=True, confirmed=False,
                    field_confirmation={}, reading=dict(status='pending',
                    reason='Sem leitura recente do coletor. Aguardando novas imagens.',
                    hero=[], board=[], street=None))
