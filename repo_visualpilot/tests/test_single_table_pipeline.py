"""Uma mesa real gravada, TCP real, OCR real e diário da sessão."""
import asyncio
import json
from pathlib import Path
from queue import Queue, Empty
import threading
import time
import unittest

import numpy as np
import cv2
from PIL import Image

from visualpilot.pppoker.observer.runtime import PerceptionSession
from visualpilot.pppoker.stream_node import encode_frame, prepare_capture
from visualpilot.pppoker.stream_receiver import StreamReceiver
from visualpilot.pppoker.transport_freshness import read_capture_ticket
from visualpilot.pppoker.roi_engine import REGIONS
from visualpilot.pppoker.observer.freshness import frame_sha256
from observation_assertions import assert_partial_trace
from lab_evidence import session_directory


class SingleTablePipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_tcp_real_ocr_hand_change_and_journal(self):
        root = Path(__file__).parent / 'fixtures/actions'
        cases = [('right_99.png', ['5c', '2s'], []),
                 ('left_99.png', ['Th', '4d'], ['7h', 'As', 'Ts'])]
        board_only = np.array(Image.open(root / 'left_99.png').convert('RGB'))
        empty = np.array(Image.open(root / 'right_99.png').convert('RGB'))
        for region in ('board_flop', 'board_turn', 'board_river'):
            y1, x1, y2, x2 = REGIONS[region][0]
            board_only[y1:y2, x1:x2] = empty[y1:y2, x1:x2]
        cases.append(('board-only-change', ['Th', '4d'], []))
        extra_images = {}
        flop = np.array(Image.open(root / 'left_99.png').convert('RGB'))
        for street, card, offset, board in (
                ('turn', '2h', 0, ['7h','As','Ts','2h']),
                ('river', '3c', 100, ['7h','As','Ts','2h','3c'])):
            source = np.array(Image.open(root.parent / 'synthetic_deck' / f'{card}.png').convert('RGB'))
            y1,x1,y2,x2 = REGIONS['board_turn'][0]
            flop[y1:y2,x1+offset:x2+offset] = source[y1:y2,x1:x2]
            extra_images[street] = flop.copy()
            cases.append((street, ['Th','4d'], board))
        for scale in (1.25, 1.5):
            name = f'window-{scale}'
            extra_images[name] = cv2.resize(flop,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
            cases.append((name, ['Th','4d'], ['7h','As','Ts','2h','3c']))

        stop = threading.Event()
        output = Queue(100)
        with session_directory('single-table-pipeline') as folder:
            runtime = PerceptionSession(folder, stop, output, workers=2)
            receiver = StreamReceiver(runtime, '127.0.0.1', 0)
            address = await receiver.start()
            worker = threading.Thread(target=runtime.run, kwargs={'capture': False})
            worker.start()
            reader, writer = await asyncio.open_connection(*address[:2])
            sequence = 0
            captures={}
            timings=[]
            table_key=json.dumps(['lab','one-session','one-table'],separators=(',',':'))
            try:
                for phase,(name, hero, board) in enumerate(cases):
                    rgb = (extra_images[name] if name in extra_images else board_only
                           if name == 'board-only-change' else np.array(Image.open(root / name).convert('RGB')))
                    prepared=prepare_capture(rgb)
                    expected=dict(phase=phase,hero=hero,board=board,session='one-session',
                                  frame_sha256=frame_sha256(prepared))
                    phase_first_sequence=sequence+1
                    phase_started = time.monotonic()
                    deadline = time.monotonic() + 35
                    found = False
                    consolidated = False
                    partial_seconds = complete_seconds = None
                    while time.monotonic() < deadline:
                        sequence += 1
                        ticket=await read_capture_ticket(reader)
                        captures[table_key,sequence]=expected
                        writer.write(encode_frame('lab', 'one-session', 'one-table', sequence, prepared,capture_ticket=ticket))
                        await writer.drain()
                        await asyncio.sleep(.2)
                        while True:
                            try:
                                event = output.get_nowait()
                            except Empty:
                                break
                            # A fila pode conter leituras já publicadas antes da
                            # troca. Valide o cenário pela captura de origem.
                            observation=event.get('validation') or event.get('observation') or {}
                            if observation.get('transport_sequence',phase_first_sequence)<phase_first_sequence:
                                continue
                            if event.get('kind') in ('reading','partial_cards'):
                                self.assertTrue(observation.get('transport_verified'),event)
                                self.assertLessEqual(event['latency'],5.)
                            if event.get('kind') == 'reading':
                                self.assertEqual(event['reading'].get('hero'), hero, event)
                                if len(board) in (3, 4, 5):
                                    self.assertEqual(event['reading'].get('board'), board, event)
                                    self.assertEqual(event['reading'].get('street'),
                                                     {3: 'flop', 4: 'turn', 5: 'river'}[len(board)], event)
                                self.assertNotEqual(event['reading'].get('reason'), 'Leitura expirada.')
                                consolidated = True
                                if complete_seconds is None:
                                    complete_seconds = time.monotonic() - phase_started
                            if event.get('kind') != 'partial_cards':
                                continue
                            self.assertEqual(event['reading']['hero'], hero, event)
                            self.assertEqual(event['reading']['board'], board, event)
                            if len(board) in (3,4,5):
                                self.assertEqual(event['reading']['street'], {3:'flop',4:'turn',5:'river'}[len(board)])
                            found = True
                            if partial_seconds is None:
                                partial_seconds = time.monotonic() - phase_started
                        if found and consolidated:
                            break
                    timings.append(dict(scenario=name, first_sequence=phase_first_sequence,
                        last_sequence=sequence, frame_sha256=expected['frame_sha256'],
                        elapsed_seconds=round(time.monotonic()-phase_started, 3),
                        partial_seconds=round(partial_seconds, 3) if partial_seconds is not None else None,
                        complete_seconds=round(complete_seconds, 3) if complete_seconds is not None else None))
                    (Path(folder)/'scenarios.json').write_text(json.dumps(timings, indent=2), encoding='utf-8')
                    print('LAB_TIMING ' + json.dumps(timings[-1]), flush=True)
                    self.assertTrue(found, f'Nenhuma leitura parcial para {name}')
                    self.assertTrue(consolidated, f'Nenhuma leitura completa para {name}')
                self.assertEqual(len(receiver.sequences), 1)
            finally:
                writer.close()
                await writer.wait_closed()
                stop.set()
                await receiver.close()
                await asyncio.to_thread(worker.join, 20)
            self.assertFalse(worker.is_alive())
            records = [json.loads(line) for line in next(Path(folder).rglob('percepcao.jsonl')).read_text(encoding='utf-8').splitlines()]
            partials = assert_partial_trace(self,records,captures,len(cases))
            self.assertEqual(len({r['table'] for r in partials}), 1)
