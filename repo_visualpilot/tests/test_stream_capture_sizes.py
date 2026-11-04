import unittest
from unittest.mock import Mock
from types import SimpleNamespace
import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from visualpilot.pppoker.stream_node import FrameSender
from visualpilot.pppoker.transport_freshness import CaptureTicket
from visualpilot.pppoker.stream_receiver import StreamReceiver
from visualpilot.pppoker.observer.runtime import Mailbox


class CaptureSizeTests(unittest.TestCase):
    def test_large_capture_is_sent_without_cropping(self):
        source = np.array(Image.open(Path(__file__).parent/'fixtures/actions/left_99.png').convert('RGB'))
        for scale in (1, 1.25, 1.5):
            with self.subTest(scale=scale):
                image = cv2.resize(source,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
                sender = FrameSender('unused',1,'lab')
                sender.socket = Mock()
                ticket=CaptureTicket();wire=ticket.wire()
                sender.socket.recv.side_effect=[wire[:4],wire[4:]]
                self.assertTrue(sender.before_capture({'table_key':'one'}))
                sender.send({'table_key':'one'},image)
                packet = sender.socket.sendall.call_args.args[0]
                runtime = SimpleNamespace(frames=Mailbox())
                receiver = StreamReceiver(runtime)
                self.assertTrue(receiver.accept_packet(packet[4:],ticket))
                received = runtime.frames.take()[1]
                self.assertEqual(received.shape[1],755)
                self.assertLessEqual(abs(received.shape[0]/received.shape[1]-image.shape[0]/image.shape[1]),.002)
