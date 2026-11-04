import unittest
from types import SimpleNamespace
from queue import Queue
from unittest.mock import patch
import numpy as np
from visualpilot.pppoker.observer.runtime import Mailbox
from visualpilot.pppoker.stream_receiver import StreamReceiver
from visualpilot.pppoker.stream_node import encode_frame
from visualpilot.viz.session import RemoteSession

class CollectorRestartTests(unittest.TestCase):
    def test_eight_restarts_retire_old_tables_without_exhausting_slots(self):
        runtime=SimpleNamespace(frames=Mailbox(),captures=Queue(10))
        receiver=StreamReceiver(runtime,allow_legacy=True)  # Identity-only compatibility tests.
        image=np.full((100,100,3),128,np.uint8)
        old=None
        for i in range(8):
            packet=encode_frame('member',f'session-{i}',f'table-{i}',1,image)[4:]
            with patch('visualpilot.pppoker.stream_receiver.monotonic',return_value=10+i*6):
                self.assertTrue(receiver.accept_packet(packet))
                if old:self.assertFalse(receiver.accept_packet(old))
            self.assertEqual(len(receiver.sequences),1)
            self.assertEqual(list(receiver.numbers.values()),[1])
            self.assertEqual(len(runtime.frames.pending),1)
            old=packet
        panel=RemoteSession();panel.tables={'old':dict(reading=dict(hero=['As','Ks']))}
        while not runtime.captures.empty():
            panel.output.put(dict(kind='tables',value=runtime.captures.get()))
        panel.poll();self.assertEqual(panel.tables,{})

    def test_running_collector_cannot_be_replaced_by_second_instance(self):
        receiver=StreamReceiver(SimpleNamespace(frames=Mailbox()),allow_legacy=True)
        image=np.zeros((100,100,3),np.uint8)
        with patch('visualpilot.pppoker.stream_receiver.monotonic',return_value=10):
            self.assertTrue(receiver.accept_packet(encode_frame('m','first','t',1,image)[4:]))
        with patch('visualpilot.pppoker.stream_receiver.monotonic',return_value=12):
            self.assertFalse(receiver.accept_packet(encode_frame('m','second','t2',1,image)[4:]))
        self.assertEqual(receiver.members,{'m':'first'})
