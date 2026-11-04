from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import mss
import numpy as np

from .vision import Profile, detect_tables, observe, pending


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class ScreenSource:
    def __enter__(self):
        self.capture = mss.mss()
        return self

    def frames(self):
        # monitors[0] é o desktop combinado; evita capturar as mesmas mesas duas vezes.
        return [(str(index), dict(monitor), np.asarray(self.capture.grab(monitor))[:, :, :3].copy())
                for index, monitor in enumerate(self.capture.monitors[1:], 1)]

    def __exit__(self, *args):
        self.capture.close()


class ReplaySource:
    """Um arquivo é um monitor por ciclo; não interpreta imagens como várias mesas."""
    def __init__(self, folder):
        self.files = sorted(Path(folder).glob('*.png'))
        if not self.files:
            raise ValueError('A pasta de reprodução precisa conter arquivos PNG')
        self.index = 0

    def __enter__(self):
        return self

    def frames(self):
        if self.index >= len(self.files):
            raise StopIteration
        path = self.files[self.index]
        self.index += 1
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f'Imagem inválida: {path.name}')
        return [('replay', {'left': 0, 'top': 0, 'width': image.shape[1], 'height': image.shape[0], 'file': path.name}, image)]

    def __exit__(self, *args):
        pass


class SessionWriter:
    def __init__(self, root, profile):
        stamp = datetime.now().astimezone()
        self.path = Path(root) / stamp.strftime('%Y-%m-%d') / (stamp.strftime('%H%M%S') + '-' + uuid.uuid4().hex[:8])
        (self.path / 'evidence').mkdir(parents=True)
        self.stream = (self.path / 'observations.jsonl').open('x', encoding='utf-8', buffering=1)
        digest = hashlib.sha256(profile.path.read_bytes()).hexdigest()
        self.write_json('session.json', {'schema_version': 1, 'started_at': utc_now(), 'profile': profile.path.name,
                                        'profile_sha256': digest, 'profile_config': profile.data,
                                        'mode': 'observation_only', 'timezone': str(stamp.tzinfo)})

    def write_json(self, filename, value):
        target = self.path / filename
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(target)

    def append(self, value):
        self.stream.write(json.dumps(value, ensure_ascii=False) + '\n')
        self.stream.flush()

    def close(self, metrics):
        try:
            self.write_json('metrics.json', {**metrics, 'ended_at': utc_now()})
        finally:
            self.stream.close()


class Collector:
    def __init__(self, profile, output='sessions', replay=None, interval=1.0, evidence_interval=10.0):
        if interval < .2 or evidence_interval < 1:
            raise ValueError('Intervalo mínimo: 0,2s; evidências: 1s')
        self.profile = profile
        self.output = output
        self.replay = replay
        self.interval = interval
        self.evidence_interval = evidence_interval
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.thread = None
        self.state = {'status': 'stopped', 'tables': {}, 'error': None, 'session': None}

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.state))

    def start(self):
        if self.thread and self.thread.is_alive():
            raise RuntimeError('Coleta já está em execução')
        self.stop_event.clear()
        with self.lock:
            self.state = {'status': 'starting', 'tables': {}, 'error': None, 'session': None}
        self.thread = threading.Thread(target=self._run, name='visualpilot-collector', daemon=False)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def join(self, timeout=None):
        if self.thread:
            self.thread.join(timeout)

    def _run(self):
        writer = None
        started = time.monotonic()
        metrics = {'cycles': 0, 'observations': 0, 'recognized_fields': 0, 'pending_fields': 0, 'empty_fields': 0,
                   'last_cycle_ms': 0, 'max_cycle_ms': 0, 'over_budget_cycles': 0, 'table_limit_exceeded': 0}
        last_evidence = {}
        active_locations = {}
        previous_samples = {}
        try:
            writer = SessionWriter(self.output, self.profile)
            with self.lock:
                self.state.update(status='running', session=str(writer.path))
            source = ReplaySource(self.replay) if self.replay else ScreenSource()
            with source:
                while not self.stop_event.is_set():
                    cycle_start = time.monotonic()
                    try:
                        frames = source.frames()
                    except StopIteration:
                        break
                    detected = []
                    for monitor_id, monitor, image in frames:
                        for box in detect_tables(image, self.profile):
                            detected.append((monitor_id, monitor, image, box))
                    if len(detected) > 6:
                        metrics['table_limit_exceeded'] += 1
                        raise RuntimeError('Mais de seis mesas detectadas; coleta interrompida para evitar seleção silenciosa')
                    visible = set()
                    next_locations = {}
                    for monitor_id, monitor, image, (x, y, w, h) in detected:
                        if self.stop_event.is_set():
                            break
                        location = (monitor_id, monitor['left'] + x, monitor['top'] + y, w, h)
                        # Um desaparecimento ou movimento cria outro rastreamento: não unir identidades por suposição.
                        table_id = active_locations.get(location, uuid.uuid4().hex[:12])
                        next_locations[location] = table_id
                        visible.add(table_id)
                        table = image[y:y+h, x:x+w]
                        raw = observe(table, self.profile)
                        result = stabilize_cards(raw, previous_samples.get(table_id))
                        previous_samples[table_id] = raw
                        timestamp = utc_now()
                        evidence = None
                        if cycle_start - last_evidence.get(table_id, -float('inf')) >= self.evidence_interval:
                            evidence = f'evidence/{table_id}-{time.time_ns()}.png'
                            if not cv2.imwrite(str(writer.path / evidence), table):
                                raise OSError('Falha ao salvar imagem de evidência')
                            last_evidence[table_id] = cycle_start
                        # Cada amostra é independente: nunca carregar cartas/ações de uma mão anterior.
                        record = {'schema_version': 1, 'type': 'observation', 'timestamp': timestamp,
                                  'table_track_id': table_id, 'monitor': monitor_id,
                                  'bounds': {'left': location[1], 'top': location[2], 'width': w, 'height': h},
                                  'hand_grouping': 'observed_id_only_no_inferred_hands',
                                  'evidence': evidence, **result}
                        statuses = list(field_statuses(result))
                        metrics['recognized_fields'] += statuses.count('recognized')
                        metrics['pending_fields'] += statuses.count('pending')
                        metrics['empty_fields'] += statuses.count('empty')
                        metrics['observations'] += 1
                        writer.append(record)
                        with self.lock:
                            self.state['tables'][table_id] = {**record, 'visible': True,
                                'recognized': statuses.count('recognized') + statuses.count('empty'), 'pending': statuses.count('pending')}
                    with self.lock:
                        for key, entry in self.state['tables'].items():
                            if key not in visible:
                                entry['visible'] = False
                    active_locations = next_locations
                    previous_samples = {key: value for key, value in previous_samples.items() if key in visible}
                    metrics['cycles'] += 1
                    elapsed = (time.monotonic() - cycle_start) * 1000
                    metrics['last_cycle_ms'] = round(elapsed, 1)
                    metrics['max_cycle_ms'] = round(max(metrics['max_cycle_ms'], elapsed), 1)
                    metrics['over_budget_cycles'] += int(elapsed > self.interval * 1000)
                    metrics['elapsed_seconds'] = round(time.monotonic() - started, 2)
                    with self.lock:
                        self.state['metrics'] = dict(metrics)
                    writer.write_json('metrics.json', metrics)
                    self.stop_event.wait(max(0, self.interval - elapsed / 1000))
        except Exception as exc:
            with self.lock:
                self.state.update(error=f'{type(exc).__name__}: {exc}', status='error')
        finally:
            metrics['elapsed_seconds'] = round(time.monotonic() - started, 2)
            if writer:
                try:
                    writer.close(metrics)
                except Exception as exc:
                    with self.lock:
                        self.state.update(error=f'Falha ao finalizar sessão: {exc}', status='error')
            with self.lock:
                if self.state['status'] != 'error':
                    self.state['status'] = 'stopped'


def field_statuses(value):
    if isinstance(value, dict):
        if 'status' in value:
            yield value['status']
        else:
            for child in value.values():
                yield from field_statuses(child)
    elif isinstance(value, list):
        for child in value:
            yield from field_statuses(child)


def stabilize_cards(current, previous):
    """Confirma cartas e etapa em dois ciclos; nunca conserva a leitura anterior."""
    result = json.loads(json.dumps(current))
    for group in ('hero_cards', 'board'):
        for index, reading in enumerate(result[group]):
            old = previous[group][index] if previous else None
            if reading['status'] in ('recognized', 'empty') and (
                old is None or old['status'] != reading['status'] or old['value'] != reading['value']
            ):
                reading.update(pending('aguardando confirmação no próximo ciclo'))
    stage = result['stage']
    if stage['status'] == 'recognized' and (
        not previous or previous['stage']['value'] != stage['value']
        or any(card['status'] == 'pending' for card in result['board'])
    ):
        stage.update(pending('etapa aguardando confirmação'))
    result['confirmation_policy'] = 'cards_and_stage_two_consecutive_samples'
    return result
