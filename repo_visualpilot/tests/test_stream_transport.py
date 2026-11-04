import asyncio
import unittest
from types import SimpleNamespace
import numpy as np
from visualpilot.pppoker.observer.runtime import Mailbox
from visualpilot.pppoker.stream_node import encode_frame
from visualpilot.pppoker.stream_receiver import StreamReceiver
from visualpilot.pppoker.transport_freshness import read_capture_ticket


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_six_concurrent_tables_rgb_and_duplicate_rejection(self):
        from visualpilot.viz.monitor import LiveMonitor
        runtime = SimpleNamespace(frames=Mailbox(), monitor=LiveMonitor())
        receiver = StreamReceiver(runtime, '127.0.0.1', 0)
        host, port = await receiver.start()
        rgb = np.full((40, 30, 3), [180, 70, 20], np.uint8)
        async def send(index):
            reader, writer = await asyncio.open_connection(host, port)
            ticket=await read_capture_ticket(reader)
            packet = encode_frame('member', 'session', str(index), 1, rgb,capture_ticket=ticket)
            writer.write(packet[:3]); await writer.drain()
            writer.write(packet[3:] + packet); await writer.drain()
            writer.close(); await writer.wait_closed()
        try:
            await asyncio.gather(*(send(i) for i in range(6)))
            for _ in range(100):
                if len(runtime.frames.pending) == 6:
                    break
                await asyncio.sleep(.01)
            self.assertEqual(len(runtime.frames.pending), 6)
            self.assertEqual(runtime.frames.replaced, 0)
            self.assertEqual(len(runtime.monitor.snapshot()), 6)
            self.assertTrue(all(x.get("preview") for x in runtime.monitor.snapshot().values()))
            for sample in runtime.frames.pending.values():
                np.testing.assert_array_equal(sample[1], rgb)
        finally:
            await receiver.close()

    async def test_invalid_packet_rejected(self):
        receiver = StreamReceiver(SimpleNamespace(frames=Mailbox()))
        with self.assertRaises(ValueError):
            receiver.accept_packet(b'\x00\x00\x20\x00garbage')
