"""Codec selection, real socket recovery and unchanged freshness guarantees."""
import asyncio
from io import BytesIO
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
from PIL import Image, JpegImagePlugin

from visualpilot.pppoker.collector_app import Collector, read_encoding_settings, save_settings
from visualpilot.pppoker.observer.runtime import Mailbox
from visualpilot.pppoker.stream_node import FrameSender, encode_frame
from visualpilot.pppoker.stream_receiver import StreamReceiver
from visualpilot.pppoker.transport_freshness import CaptureTicket, FreshnessError


def parts(packet):
    size = struct.unpack('!I', packet[4:8])[0]
    return json.loads(packet[8:8+size]), packet[8+size:]


def repack(header, payload):
    data = json.dumps(header).encode()
    return struct.pack('!I', len(data)) + data + payload


class JPEGPacketTests(unittest.TestCase):
    def setUp(self):
        self.rgb = np.full((90, 120, 3), [180, 70, 20], np.uint8)
        self.runtime = SimpleNamespace(frames=Mailbox())
        self.receiver = StreamReceiver(self.runtime)

    def test_declared_codecs_and_old_png_are_accepted_with_rgb_order(self):
        for codec in ('png', 'jpeg', 'old-png'):
            with self.subTest(codec=codec):
                ticket = CaptureTicket()
                header, payload = parts(encode_frame('lab', 'one', codec, 1, self.rgb,
                    capture_ticket=ticket.token, image_codec='png' if codec=='old-png' else codec))
                if codec=='old-png': header.pop('image_codec')
                self.assertTrue(self.receiver.accept_packet(repack(header, payload), ticket))
                received = self.runtime.frames.take()[1]
                self.assertEqual(received.shape, self.rgb.shape)
                self.assertLessEqual(np.abs(received.astype(int)-self.rgb).max(), 2 if codec=='jpeg' else 0)

    def test_bad_codec_corruption_and_shape_never_consume_ticket_or_mutate_membership(self):
        for mode in ('mismatch', 'unknown', 'wrong_type', 'truncated', 'corrupt', 'shape'):
            with self.subTest(mode=mode):
                ticket = CaptureTicket()
                header, payload = parts(encode_frame('lab','one','table',1,self.rgb,
                    capture_ticket=ticket.token, image_codec='jpeg',
                    active_tables=['table'], membership_generation=1))
                if mode=='mismatch': header['image_codec']='png'
                if mode=='unknown': header['image_codec']='webp'
                if mode=='wrong_type': header['image_codec']=[]
                if mode=='truncated': payload=payload[:-2]
                if mode=='corrupt': payload=b'\xff\xd8\xffbroken\xff\xd9'
                if mode=='shape': header['shape']=[50,50,3]
                with self.assertRaises(ValueError):
                    self.receiver.accept_packet(repack(header,payload),ticket)
                self.assertFalse(ticket.used)
                self.assertFalse(self.receiver.memberships)
                self.assertFalse(self.receiver.sequences)
                self.assertFalse(self.runtime.frames.pending)

    def test_jpeg_expiring_during_decode_is_rejected(self):
        now = [100.]
        ticket = CaptureTicket(clock=lambda:now[0])
        packet = encode_frame('lab','one','table',1,self.rgb,
                              capture_ticket=ticket.token,image_codec='jpeg')
        original = cv2.imdecode
        def delayed(*args):
            now[0] = 106.
            return original(*args)
        with patch('visualpilot.pppoker.stream_receiver.cv2.imdecode',side_effect=delayed):
            with self.assertRaisesRegex(FreshnessError,'expired_capture_ticket'):
                self.receiver.accept_packet(packet[4:],ticket)
        self.assertFalse(self.runtime.frames.pending)
        self.assertFalse(self.receiver.sequences)

    def test_quality_and_codec_are_validated_before_connecting(self):
        for quality in (0,101,True,95.5,'95'):
            with self.subTest(quality=quality), self.assertRaises(ValueError):
                FrameSender('unused',1,'lab',image_codec='jpeg',jpeg_quality=quality)
        with self.assertRaises(ValueError): FrameSender('unused',1,'lab',image_codec='jpg')

    def test_encoded_jpeg_really_preserves_full_chroma_resolution(self):
        _,payload=parts(encode_frame('lab','one','table',1,self.rgb,image_codec='jpeg'))
        with Image.open(BytesIO(payload)) as image:
            self.assertEqual(image.format,'JPEG')
            self.assertEqual(JpegImagePlugin.get_sampling(image),0)  # 0 means 4:4:4.

    def test_repeated_pixels_require_new_ticket_and_sequence(self):
        first=CaptureTicket()
        packet=encode_frame('lab','one','table',1,self.rgb,capture_ticket=first.token,image_codec='jpeg')
        self.assertTrue(self.receiver.accept_packet(packet[4:],first))
        original=self.runtime.frames.take()[1]
        with self.assertRaisesRegex(FreshnessError,'ticket_already_used'):
            self.receiver.accept_packet(packet[4:],first)
        second=CaptureTicket()
        duplicate=encode_frame('lab','one','table',1,self.rgb,capture_ticket=second.token,image_codec='jpeg')
        self.assertFalse(self.receiver.accept_packet(duplicate[4:],second))
        self.assertFalse(self.runtime.frames.pending)
        fresh=encode_frame('lab','one','table',2,self.rgb,capture_ticket=second.token,image_codec='jpeg')
        self.assertTrue(self.receiver.accept_packet(fresh[4:],second))
        np.testing.assert_array_equal(original,self.runtime.frames.take()[1])

    def test_collector_loads_transport_config_and_save_preserves_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'stream_config.ini'
            self.assertEqual(read_encoding_settings(path),dict(image_codec='png',jpeg_quality=100))
            path.write_text('[transport]\nimage_codec=jpeg\njpeg_quality=90\n')
            values=save_settings(path,dict(host='127.0.0.1',port=48735,member='lab'))
            factory=Mock(return_value=Mock(session='lab',last_error=None))
            factory.return_value.membership_snapshot.return_value=(None,0)
            control=Mock();control.exchange.return_value={}
            collector=Collector(directory,observe=Mock(),sender_factory=factory,control_factory=Mock(return_value=control))
            try:
                collector.start(values)
                collector.thread.join(3)
                factory.assert_called_once_with(**values,image_codec='jpeg',jpeg_quality=90)
                self.assertEqual(collector.snapshot()['image_codec'],'jpeg')
            finally: collector.close()
            path.write_text('[transport]\nimage_codec=jpeg\njpeg_quality=bad\n')
            with self.assertRaises(ValueError): read_encoding_settings(path)


class JPEGSocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_sender_six_tables_then_reconnect_and_retire_old_layout(self):
        runtime=SimpleNamespace(frames=Mailbox())
        receiver=StreamReceiver(runtime,'127.0.0.1',0)
        address=await receiver.start()
        sender=FrameSender(*address[:2],'lab',image_codec='jpeg',jpeg_quality=95)
        try:
            for ids in ([str(i) for i in range(6)], ['moved']):
                sender.set_tables([dict(table_key=i) for i in ids])
                for table in ids:
                    def send():
                        item=dict(table_key=table)
                        self.assertTrue(sender.before_capture(item),sender.last_error)
                        return sender.send(item,np.full((90,120,3),[180,70,20],np.uint8))
                    self.assertTrue(await asyncio.to_thread(send))
                target=6 if len(ids)==6 else 7
                for _ in range(100):
                    if receiver.metrics['accepted_verified']==target: break
                    await asyncio.sleep(.01)
                self.assertEqual(receiver.metrics['accepted_verified'],target)
                self.assertEqual(len(receiver.sequences),len(ids))
                self.assertEqual(len(runtime.frames.pending),len(ids))
                for sample in runtime.frames.pending.values():
                    self.assertTrue(sample[0]['transport']['verified'])
                    self.assertEqual(sample[0]['image_codec'],'jpeg')
                sender.close()
            self.assertEqual(receiver.metrics['rejected'],{})
            self.assertEqual(receiver.metrics['image_codecs'],{'jpeg':7})
        finally:
            sender.close()
            await receiver.close()
