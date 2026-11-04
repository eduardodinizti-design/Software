"""One-table interruption and recovery with real TCP, OCR and session logs."""
import asyncio
import json
from pathlib import Path
import socket
from time import monotonic
import unittest
from unittest.mock import patch
import cv2
from visualpilot.viz.session import RemoteSession
from visualpilot.pppoker.transport_freshness import read_capture_ticket
from visualpilot.pppoker.stream_node import encode_frame, prepare_capture
from visualpilot.pppoker.observer.freshness import frame_sha256
from observation_assertions import assert_partial_trace
from lab_evidence import session_directory

class FreshnessTests(unittest.TestCase):
    def test_expire_from_observation_time_not_queue_delivery(self):
        session=RemoteSession()
        original=dict(hero=['As','Ks'],board=['2h','3h','4h'],street='flop')
        session.output.put(dict(kind='reading',table='one',observed=10.,reading=original,confirmed=True))
        with patch('visualpilot.viz.session.monotonic',return_value=16.): session.poll()
        self.assertTrue(session.tables['one']['stale'])
        self.assertEqual(session.tables['one']['reading']['hero'],[])
        self.assertFalse(session.tables['one']['confirmed'])
        self.assertEqual(original['hero'],['As','Ks'])
        session.output.put(dict(kind='partial_cards',table='one',observed=17.,reading=dict(hero=['Th','4d'])))
        with patch('visualpilot.viz.session.monotonic',return_value=17.): session.poll()
        self.assertFalse(session.tables['one'].get('stale',False))
        self.assertEqual(session.tables['one']['reading']['hero'],['Th','4d'])

class RemoteRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_expiry_reconnect_new_hand_three_cycles(self):
        await self.exercise(False)

    async def test_new_collector_sessions_replace_old_tables_three_cycles(self):
        await self.exercise(True)

    async def exercise(self, restart):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        with session_directory(f'remote-recovery-restart-{restart}') as tmp:
            root=Path(tmp);config=root/'stream_config.ini'
            config.write_text(f'[central]\nlisten_host=127.0.0.1\nport={port}\n')
            control=RemoteSession(root/'sessions',config);control.start()
            writer=None;seq=0;timings=[];captures={}
            try:
                for _ in range(200):
                    control.poll()
                    if control.folder or control.error:break
                    await asyncio.sleep(.05)
                self.assertIsNone(control.error);self.assertIsNotNone(control.folder)
                for cycle in range(3):
                    reader,writer=await asyncio.open_connection('127.0.0.1',port)
                    filename,expected=(('right_99.png',['5c','2s']) if cycle%2==0 else ('left_99.png',['Th','4d']))
                    image=cv2.cvtColor(cv2.imread(str(Path(__file__).parent/'fixtures/actions'/filename)),cv2.COLOR_BGR2RGB)
                    image=prepare_capture(image);start=monotonic();confirmed=False
                    session=f'restart-{cycle}' if restart else 'recovery'
                    table=f'table-{cycle}' if restart else 'one'
                    table_key=json.dumps(['lab',session,table],separators=(',',':'))
                    expected_source=dict(phase=cycle,hero=expected,
                        board=[] if cycle%2==0 else ['7h','As','Ts'],session=session,
                        frame_sha256=frame_sha256(image))
                    while monotonic()-start<25:
                        seq+=1
                        ticket=await read_capture_ticket(reader)
                        captures[table_key,seq]=expected_source
                        writer.write(encode_frame('lab',session,table,seq,image,capture_ticket=ticket));await writer.drain()
                        await asyncio.sleep(.15);control.poll()
                        if any(e['kind']=='reading' and (e.get('validation') or e.get('observation') or {}).get('ingress_observed',0)>=start and e['reading'].get('hero')==expected for e in control.tables.values()):
                            confirmed=True;break
                    self.assertTrue(confirmed,control.tables)
                    current=control.tables[table_key]
                    self.assertTrue(current['observation']['transport_verified'])
                    self.assertLessEqual(current['latency'],5.)
                    self.assertEqual(len(control.tables),1)
                    self.assertEqual(len(control.monitor.snapshot()),1)
                    self.assertTrue(next(iter(control.monitor.snapshot().values())).get('preview'))
                    timings.append(round(monotonic()-start,3))
                    writer.close();await writer.wait_closed();writer=None
                    # Real elapsed silence, not a mocked clock; OCR may finish in flight.
                    await asyncio.sleep(5.3);control.poll()
                    event=next(iter(control.tables.values()))
                    self.assertTrue(event.get('stale'),event)
                    self.assertEqual(event['reading']['hero'],[])
                    self.assertEqual(event['reading']['board'],[])
                print('RECOVERY_TIMINGS',dict(restart=restart,seconds=timings))
            finally:
                if writer:
                    writer.close();await writer.wait_closed()
                control.stop.set();await asyncio.to_thread(control.thread.join,20)
            self.assertFalse(control.thread.is_alive())
            entries=[json.loads(line) for line in (Path(control.folder)/'percepcao.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertGreater(len(entries),0)
            monitoring=Path(control.folder)/'acompanhamento/eventos.jsonl'
            self.assertTrue(monitoring.exists())
            samples=[json.loads(line) for line in monitoring.read_text(encoding='utf-8').splitlines() if json.loads(line)['kind']=='reading_sample']
            self.assertTrue(samples)
            self.assertTrue(any(row['evidence']['path'] for row in samples))
            self.assertEqual(len({entry['table'] for entry in entries}),3 if restart else 1)
            assert_partial_trace(self,entries,captures,3)
            metrics=json.loads((Path(control.folder)/'metricas.json').read_text(encoding='utf-8'))
            self.assertEqual(metrics['errors'],0)
