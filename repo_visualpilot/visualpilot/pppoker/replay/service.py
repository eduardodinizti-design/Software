"""Componente observacional recuperado do projeto enviado; ver docs/LEGACY_REUSE.md."""
import multiprocessing as mp
from queue import Empty
from time import monotonic
import numpy as np
import cv2

def _worker(requests, responses):
    from .reader import ReplayReader
    from ..observer.perception import CachedReader, read_table
    from ..card_reader import CardRegionReader
    # O paralelismo já é feito entre processos. Pools internos competiam com o
    # receptor e com os outros workers em CPUs limitadas, vencendo a captura
    # antes de terminar o texto. Limite somente este processo filho.
    cv2.setNumThreads(1)
    reader = CachedReader(ReplayReader(intra_op_num_threads=1))
    card_reader = CardRegionReader(reader)
    while True:
        job = requests.get()
        if job is None:
            return
        token, kind, rgb = job
        try:
            if kind == 'perception':
                result = read_table(reader, rgb)
            elif kind == 'card_region':
                if not isinstance(rgb, dict):
                    raise ValueError('Trabalho de cartas inválido')
                required = {'table_key','generation','region','image'}
                if not required.issubset(rgb):
                    raise ValueError('Trabalho de cartas sem identidade completa')
                reading = card_reader.read_region(
                    rgb['region'], rgb['image'], occupied=rgb.get('occupied', ()))
                result = dict(kind='card_region', table_key=rgb['table_key'],
                              generation=rgb['generation'], region=rgb['region'],
                              reading=reading)
            else:
                raise ValueError('Somente observação passiva é suportada')
            responses.put((token, result, None))
        except Exception as exc:
            responses.put((token, None, str(exc)))

class OCRService:

    def __init__(self, timeout=45):
        self.timeout = timeout
        self.process = None
        self.serial = 0
        self.completed_calls = 0
        self.total_seconds = 0.0

    def _start(self):
        ctx = mp.get_context('spawn')
        self.requests = ctx.Queue(1)
        self.responses = ctx.Queue(1)
        self.process = ctx.Process(target=_worker, args=(self.requests, self.responses), daemon=True)
        self.process.start()

    def start(self):
        """Start loading the OCR model before the first captured frame arrives."""
        if self.process is None or not self.process.is_alive():
            self.close()
            self._start()

    def call(self, kind, rgb, stop):
        if stop.is_set():
            raise InterruptedError('Parado.')
        started = monotonic()
        if self.process is None or not self.process.is_alive():
            self.close()
            self._start()
        self.serial += 1
        token = self.serial
        self.requests.put((token, kind, rgb), timeout=2)
        deadline = monotonic() + (min(self.timeout, 1.4) if kind == 'profile' else self.timeout)
        while True:
            if stop.is_set():
                self.close()
                raise InterruptedError('Parado.')
            if monotonic() > deadline:
                self.close()
                raise TimeoutError('OCR excedeu o limite; coleta será retomada.')
            try:
                received, result, error = self.responses.get(timeout=0.1)
            except Empty:
                if not self.process.is_alive():
                    self.close()
                    raise RuntimeError('Processo OCR encerrou inesperadamente.')
                continue
            if received != token:
                continue
            if error:
                raise ValueError(error)
            self.completed_calls += 1
            self.total_seconds += monotonic() - started
            return result

    def read_cards(self, table_key, generation, region, image, stop, occupied=()):
        """Lê uma região mantendo identidade suficiente para rejeitar atrasos."""
        if not isinstance(table_key, str) or not table_key:
            raise ValueError('table_key obrigatório')
        if not isinstance(generation, int) or generation < 0:
            raise ValueError('generation deve ser inteiro não negativo')
        payload = dict(table_key=table_key, generation=generation, region=region,
                       image=image, occupied=tuple(occupied))
        return self.call('card_region', payload, stop)

    def close(self):
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=1)
            for queue in (self.requests, self.responses):
                queue.cancel_join_thread()
                queue.close()
            self.process = None
