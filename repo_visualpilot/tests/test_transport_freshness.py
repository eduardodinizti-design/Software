"""Capture-to-publication freshness, independent of wall-clock synchronization."""
import unittest
from types import SimpleNamespace
import numpy as np
from visualpilot.pppoker.observer.runtime import Mailbox
from visualpilot.pppoker.stream_node import encode_frame
from visualpilot.pppoker.stream_receiver import StreamReceiver


class LegacyFreshnessTests(unittest.TestCase):
    def test_frame_without_capture_freshness_proof_is_rejected_by_default(self):
        runtime=SimpleNamespace(frames=Mailbox())
        receiver=StreamReceiver(runtime)
        packet=encode_frame('lab','session','one',1,np.zeros((40,30,3),np.uint8))
        with self.assertRaises(ValueError):receiver.accept_packet(packet[4:])
        self.assertFalse(runtime.frames.pending)


from unittest.mock import Mock, patch
from visualpilot.pppoker.transport_freshness import CaptureTicket, FreshnessError, read_capture_ticket
from visualpilot.pppoker.stream_node import FrameSender


class TicketTests(unittest.TestCase):
    def setUp(self):
        self.now=100.
        self.runtime=SimpleNamespace(frames=Mailbox(clock=lambda:self.now))
        self.receiver=StreamReceiver(self.runtime)
        self.image=np.zeros((100,100,3),np.uint8)

    def ticket(self):return CaptureTicket(clock=lambda:self.now)
    def packet(self,ticket,sequence=1):
        return encode_frame('lab','session','one',sequence,self.image,capture_ticket=ticket.token)[4:]

    def test_transit_age_survives_ingress_instead_of_resetting(self):
        ticket=self.ticket();packet=self.packet(ticket)
        self.now=104.
        self.assertTrue(self.receiver.accept_packet(packet,ticket))
        sample=self.runtime.frames.take()
        self.assertIsNotNone(sample)
        self.assertEqual(sample[2],100.)
        self.assertEqual(sample[0]['ingress_observed'],104.)
        self.assertEqual(sample[0]['transport']['age_upper_bound_at_receive'],4.)
        self.now=105.1
        self.runtime.frames.put(dict(table_key='one',transport=sample[0]['transport']),self.image)
        self.assertIsNone(self.runtime.frames.take())

    def test_expired_ticket_does_not_change_membership_or_queue(self):
        ticket=self.ticket();packet=self.packet(ticket);self.now=106.
        with self.assertRaisesRegex(FreshnessError,'expired_capture_ticket'):
            self.receiver.accept_packet(packet,ticket)
        self.assertEqual(self.receiver.sequences,{})
        self.assertEqual(self.receiver.members,{})
        self.assertFalse(self.runtime.frames.pending)

    def test_cross_connection_and_reused_ticket_are_rejected(self):
        first=self.ticket();second=self.ticket()
        with self.assertRaisesRegex(FreshnessError,'wrong_capture_ticket'):
            self.receiver.accept_packet(self.packet(first),second)
        self.assertTrue(self.receiver.accept_packet(self.packet(first),first))
        with self.assertRaisesRegex(FreshnessError,'ticket_already_used'):
            self.receiver.accept_packet(self.packet(first,2),first)
        self.assertEqual(list(self.receiver.sequences.values()),[1])

    def test_expiration_during_image_decode_is_checked_again(self):
        import cv2
        ticket=self.ticket();packet=self.packet(ticket)
        decode=cv2.imdecode
        def delayed(*args,**kwargs):
            self.now=106.
            return decode(*args,**kwargs)
        with patch('visualpilot.pppoker.stream_receiver.cv2.imdecode',side_effect=delayed):
            with self.assertRaisesRegex(FreshnessError,'expired_capture_ticket'):
                self.receiver.accept_packet(packet,ticket)
        self.assertEqual(self.receiver.sequences,{})

    def test_clock_skew_of_client_wall_time_is_irrelevant(self):
        ticket=self.ticket()
        with patch('time.time',return_value=-10**9):
            self.assertTrue(self.receiver.accept_packet(self.packet(ticket),ticket))
        self.assertEqual(self.runtime.frames.take()[2],100.)

    def test_legacy_mode_is_explicit_and_never_claims_transport_verified(self):
        receiver=StreamReceiver(self.runtime,allow_legacy=True)
        self.assertTrue(receiver.accept_packet(encode_frame('lab','session','one',1,self.image)[4:]))
        sample=self.runtime.frames.take()
        self.assertFalse(sample[0]['transport']['verified'])

    def test_legacy_rejection_reaches_panel_and_clears_on_verified_frame(self):
        from queue import Queue
        from visualpilot.viz.session import RemoteSession
        self.runtime.output=Queue(10)
        with self.assertRaises(ValueError):
            self.receiver.accept_packet(encode_frame('lab','session','one',1,self.image)[4:])
        panel=RemoteSession();panel.output=self.runtime.output;panel.poll()
        self.assertIn('Atualize a Central e o Coletor juntos',panel.transport_warning)
        ticket=self.ticket()
        self.receiver.accept_packet(self.packet(ticket),ticket)
        panel.poll()
        self.assertIsNone(panel.transport_warning)


class SenderOrderTests(unittest.TestCase):
    def setUp(self):
        self.image=np.zeros((40,30,3),np.uint8)
        self.item=dict(table_key='one')
        self.sender=FrameSender('unused',1,'lab')
        self.socket=Mock();self.sender.socket=self.socket

    def test_send_without_before_capture_never_writes_pixels(self):
        self.assertFalse(self.sender.send(self.item,self.image))
        self.socket.sendall.assert_not_called()

    def test_permit_is_obtained_before_grab_and_consumed_once(self):
        ticket=CaptureTicket();wire=ticket.wire()
        self.socket.recv.side_effect=[wire[:4],wire[4:]]
        order=[]
        self.assertTrue(self.sender.before_capture(self.item));order.append('permit')
        image=self.image.copy();order.append('grab')
        self.assertTrue(self.sender.send(self.item,image));order.append('send')
        self.assertEqual(order,['permit','grab','send'])
        packet=self.socket.sendall.call_args.args[0]
        runtime=SimpleNamespace(frames=Mailbox());receiver=StreamReceiver(runtime)
        self.assertTrue(receiver.accept_packet(packet[4:],ticket))
        self.assertFalse(self.sender.send(self.item,image))
        self.assertEqual(self.socket.sendall.call_count,1)

    def test_failed_send_is_not_retried_with_old_pixels(self):
        ticket=CaptureTicket();wire=ticket.wire()
        self.socket.recv.side_effect=[wire[:4],wire[4:]]
        self.assertTrue(self.sender.before_capture(self.item))
        self.socket.sendall.side_effect=OSError('simulated disconnect')
        self.assertFalse(self.sender.send(self.item,self.image))
        self.assertIsNone(self.sender.socket)
        self.assertFalse(self.sender.send(self.item,self.image))
        self.assertEqual(self.socket.sendall.call_count,1)


import asyncio
import threading
import time

class RealSocketFreshnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_sender_capture_exchange_and_two_sequential_frames(self):
        runtime=SimpleNamespace(frames=Mailbox())
        receiver=StreamReceiver(runtime,'127.0.0.1',0)
        address=await receiver.start()
        sender=FrameSender(*address[:2],'lab')
        try:
            def capture_and_send():
                item=dict(table_key='one')
                self.assertTrue(sender.before_capture(item),sender.last_error)
                image=np.full((100,100,3),80,np.uint8)  # Simulated grab AFTER permit.
                return sender.send(item,image)
            for sequence in (1,2):
                self.assertTrue(await asyncio.to_thread(capture_and_send))
                for _ in range(100):
                    if list(receiver.sequences.values())==[sequence]:break
                    await asyncio.sleep(.01)
                self.assertEqual(list(receiver.sequences.values()),[sequence])
                sample=runtime.frames.take()
                self.assertTrue(sample[0]['transport']['verified'])
                self.assertLessEqual(time.monotonic()-sample[2],5.)
        finally:sender.close();await receiver.close()

    async def test_delayed_frame_over_real_tcp_is_rejected(self):
        runtime=SimpleNamespace(frames=Mailbox())
        receiver=StreamReceiver(runtime,'127.0.0.1',0)
        # Shorten ONLY this test's permit to make transport-delay injection fast.
        receiver.new_ticket=lambda:CaptureTicket(max_age=.2)
        address=await receiver.start()
        reader,writer=await asyncio.open_connection(*address[:2])
        try:
            token=await read_capture_ticket(reader)
            image=np.zeros((40,30,3),np.uint8)
            packet=encode_frame('lab','session','one',1,image,capture_ticket=token)
            await asyncio.sleep(.3)
            writer.write(packet);await writer.drain()
            self.assertEqual(await asyncio.wait_for(reader.read(),2),b'')
            self.assertFalse(runtime.frames.pending)
            self.assertEqual(receiver.metrics['rejected'].get('expired_capture_ticket'),1)
        finally:
            writer.close();await writer.wait_closed();await receiver.close()




class CaptureLoopOrderTests(unittest.TestCase):
    def test_real_capture_loop_obtains_permission_before_grab(self):
        import tempfile
        from queue import Queue
        from visualpilot.pppoker.multitable import observe_tables,latest
        order=[];stop=threading.Event()
        class Capture:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def grab(self,region):
                order.append('grab')
                return np.zeros((100,100,3),np.uint8)
        def finder(stop,results,*args):
            latest(results,dict(found=[dict(monitor=1,box=[0,0,100,100],score=.99)],reports=[]))
        def permit(item):order.append('permit');return True
        def sink(item,rgb,stamp):order.append('send');stop.set();return True
        with tempfile.TemporaryDirectory() as root,patch('visualpilot.pppoker.multitable.table_anchor_visible',return_value=True):
            observe_tables(root,stop,Queue(10),interval=.01,capture_factory=Capture,
                           discovery_fn=finder,windows_reader=lambda:[],frame_sink=sink,before_capture=permit)
        self.assertEqual(order,['permit','grab','send'])

    def test_refused_permission_prevents_capture(self):
        import tempfile
        from queue import Queue
        from visualpilot.pppoker.multitable import observe_tables,latest
        stop=threading.Event();grabbed=[]
        class Capture:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def grab(self,region):grabbed.append(True);return np.zeros((100,100,3),np.uint8)
        def finder(stop,results,*args):
            latest(results,dict(found=[dict(monitor=1,box=[0,0,100,100],score=.99)],reports=[]))
        def permit(item):stop.set();return False
        with tempfile.TemporaryDirectory() as root:
            observe_tables(root,stop,Queue(10),interval=.01,capture_factory=Capture,
                           discovery_fn=finder,windows_reader=lambda:[],before_capture=permit)
        self.assertFalse(grabbed)

if __name__=='__main__':unittest.main()
