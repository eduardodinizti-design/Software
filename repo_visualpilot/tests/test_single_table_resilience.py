"""Falhas e recuperação no laboratório de uma mesa."""
import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from visualpilot.pppoker.observer.runtime import Mailbox
from visualpilot.pppoker.stream_node import encode_frame
from visualpilot.pppoker.transport_freshness import read_capture_ticket
from visualpilot.pppoker.stream_receiver import StreamReceiver
from visualpilot.viz.session import RemoteSession


class PacketTests(unittest.TestCase):
    def test_short_header_rejected_as_invalid_frame(self):
        receiver = StreamReceiver(SimpleNamespace(frames=Mailbox()))
        for packet in (b'', b'\x00', b'\x00\x00\x00'):
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                receiver.accept_packet(packet)
        self.assertEqual(receiver.sequences, {})


class RestartTests(unittest.TestCase):
    def test_restart_does_not_replay_previous_session(self):
        session = RemoteSession()
        session.folder = 'old-session'
        session.output.put({'kind': 'partial_cards', 'table': 'old', 'reading': {'hero': ['As','Ks']}})
        with patch('visualpilot.viz.session.threading.Thread'):
            session.start()
        session.poll()
        self.assertEqual(session.tables, {})
        self.assertIsNone(session.folder)


class ReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_bad_connection_then_reconnect_and_no_duplicate(self):
        runtime = SimpleNamespace(frames=Mailbox())
        receiver = StreamReceiver(runtime, '127.0.0.1', 0)
        address = await receiver.start()
        rgb = np.full((40, 30, 3), [40, 180, 90], np.uint8)
        async def send(data=None,sequence=None):
            reader, writer = await asyncio.open_connection(*address[:2])
            ticket=await read_capture_ticket(reader)
            if sequence is not None:data=encode_frame('lab','session','one',sequence,rgb,capture_ticket=ticket)
            writer.write(data)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        try:
            await send(struct.pack('!I', 999999999))
            await send(sequence=1)
            for _ in range(100):
                if runtime.frames.pending: break
                await asyncio.sleep(.01)
            first = runtime.frames.take()
            self.assertIsNotNone(first)
            np.testing.assert_array_equal(first[1],rgb)
            await send(sequence=1)  # Duplicata depois da reconexão não atualiza a idade.
            await send(sequence=2)
            for _ in range(100):
                if runtime.frames.pending: break
                await asyncio.sleep(.01)
            self.assertEqual(list(receiver.sequences.values()), [2])
            self.assertEqual(len(runtime.frames.pending),1)
        finally:
            await receiver.close()
