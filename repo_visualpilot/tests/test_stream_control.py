import asyncio
import json
from queue import Queue
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from visualpilot.pppoker.observer.runtime import Mailbox
from visualpilot.pppoker.stream_control import ControlSender, encode_status
from visualpilot.pppoker.stream_node import FrameSender, encode_frame
from visualpilot.pppoker.stream_receiver import StreamReceiver
from visualpilot.pppoker.transport_freshness import CaptureTicket
from visualpilot.viz.monitor import LiveMonitor
from visualpilot.viz.session import RemoteSession


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.runtime=SimpleNamespace(frames=Mailbox(),captures=Queue(1),output=Queue(100),monitor=LiveMonitor())
        self.receiver=StreamReceiver(self.runtime)

    def status(self,active,generation,sequence=1,member='pc',session='session',ticket=None,discovery_state='ready'):
        ticket=ticket or CaptureTicket()
        return self.receiver.accept_packet(encode_status(member,session,sequence,ticket.token,active,generation,discovery_state)[4:],ticket)

    def test_failed_discovery_is_not_a_confirmation_of_zero_tables(self):
        self.frame()
        self.status([],2,discovery_state='error')
        self.assertEqual(len(self.receiver.sequences),1)
        panel=RemoteSession();panel.output=self.runtime.output;panel.poll()
        self.assertEqual(panel.collectors['pc']['discovery_state'],'error')
        self.assertEqual(panel.collectors['pc']['visible_tables'],1)

    def frame(self,table='one',member='pc',generation=1,sequence=1):
        ticket=CaptureTicket()
        self.receiver.accept_packet(encode_frame(member,'session',table,sequence,np.zeros((100,60,3),np.uint8),
            capture_ticket=ticket.token,active_tables=[table],membership_generation=generation)[4:],ticket)

    def test_zero_tables_retires_pixels_queues_and_panel_without_an_image(self):
        self.frame()
        key=next(iter(self.receiver.sequences))
        epoch=self.runtime.frames.remote_epochs[key]
        panel=RemoteSession();panel.output=self.runtime.output
        panel.output.put(dict(kind='reading',table=key,remote_epoch=epoch,observed=0,reading={'hero':['As','Ks']}))
        self.status([],2)
        panel.poll()
        self.assertFalse(panel.tables)
        self.assertFalse(self.runtime.monitor.snapshot())
        self.assertFalse(self.runtime.frames.pending)
        self.assertFalse(self.receiver.sequences)
        self.assertEqual(panel.collectors['pc']['visible_tables'],0)
        self.assertEqual(self.receiver.metrics['accepted_verified'],1)
        self.assertEqual(self.receiver.metrics['accepted_controls'],1)

    def test_older_list_is_acknowledged_without_rolling_back_new_frames(self):
        self.frame('new',generation=3)
        self.status([],2)
        self.assertEqual([v[2] for v in self.receiver.identities.values()],['new'])
        self.assertEqual(self.receiver.memberships['pc','session'],(3,frozenset(['new'])))
        self.status(None,0,sequence=2)
        self.assertEqual(len(self.receiver.sequences),1)

    def test_conflict_duplicate_invalid_and_expired_controls_cannot_mutate(self):
        self.frame()
        self.status(['one'],1)
        expected=dict(self.receiver.sequences)
        now=[0.];expired=CaptureTicket(clock=lambda:now[0]);now[0]=6.
        for args in [([],1,2),([],2,1),(['same','same'],2,2),([],True,2),([],2,2,'pc','session',expired)]:
            with self.subTest(args=args),self.assertRaises(ValueError):self.status(*args)
            self.assertEqual(self.receiver.sequences,expected)

    def test_other_member_and_active_session_cannot_be_cleared(self):
        self.frame(member='other')
        self.frame()
        with self.assertRaises(ValueError):self.status([],2,session='replacement')
        self.status([],2)
        self.assertEqual([v[0] for v in self.receiver.identities.values()],['other'])

    def test_retired_session_cannot_send_control_after_replacement(self):
        self.status([],1)
        self.receiver.last_seen['pc']-=6
        self.status([],1,session='replacement')
        with self.assertRaises(ValueError):self.status([],2,sequence=2)
        self.assertEqual(self.receiver.members['pc'],'replacement')

    def test_unknown_discovery_is_distinct_from_zero_tables(self):
        self.status(None,0)
        panel=RemoteSession();panel.output=self.runtime.output;panel.poll()
        self.assertIsNone(panel.collectors['pc']['visible_tables'])
        self.assertFalse(self.receiver.memberships)

    def test_old_panel_events_do_not_recreate_retired_table_even_if_key_returns(self):
        panel=RemoteSession()
        def tables(revision,epochs):
            panel.output.put(dict(kind='tables',value=dict(transport_revision=revision,remote_epochs=epochs,
                tables=[dict(table_key=k,state='capturando') for k in epochs])))
        def reading(epoch):
            panel.output.put(dict(kind='reading',table='one',remote_epoch=epoch,observed=100,
                                  reading=dict(hero=['As','Ks'])))
        tables(1,{'one':1});reading(1)
        tables(2,{});reading(1);tables(1,{'one':1});reading(1)
        with patch('visualpilot.viz.session.monotonic',return_value=101):panel.poll()
        self.assertFalse(panel.tables)
        tables(3,{'one':2});reading(1)
        with patch('visualpilot.viz.session.monotonic',return_value=101):panel.poll()
        self.assertFalse(panel.tables)
        reading(2)
        with patch('visualpilot.viz.session.monotonic',return_value=101):panel.poll()
        self.assertEqual(panel.tables['one']['reading']['hero'],['As','Ks'])

    def test_heartbeat_does_not_rejuvenate_readings_and_expires_independently(self):
        panel=RemoteSession()
        panel.output.put(dict(kind='reading',table='one',observed=100,reading=dict(hero=['As','Ks'])))
        panel.output.put(dict(kind='collector_status',member='pc',session='session',observed=104,visible_tables=1))
        with patch('visualpilot.viz.session.monotonic',return_value=106):panel.poll()
        self.assertTrue(panel.collectors['pc']['connected'])
        self.assertTrue(panel.tables['one']['stale'])
        self.assertEqual(panel.tables['one']['reading']['hero'],[])
        with patch('visualpilot.viz.session.monotonic',return_value=111):panel.poll()
        self.assertFalse(panel.collectors['pc']['connected'])


class ControlSocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_png_and_controls_use_independent_sockets_then_clear_without_frames(self):
        runtime=SimpleNamespace(frames=Mailbox(),captures=Queue(1),output=Queue(100),monitor=LiveMonitor())
        receiver=StreamReceiver(runtime,'127.0.0.1',0)
        address=(await receiver.start())[:2]
        sender=FrameSender(*address,'pc')
        control=ControlSender(address,'pc',sender.session)
        try:
            sender.set_tables([dict(table_key='one')])
            def frames():
                for _ in range(3):
                    self.assertTrue(sender.before_capture(dict(table_key='one')))
                    self.assertTrue(sender.send(dict(table_key='one'),np.zeros((100,60,3),np.uint8)))
                self.assertTrue(sender.before_capture(dict(table_key='one')))
            await asyncio.gather(asyncio.to_thread(frames),
                                 asyncio.to_thread(control.exchange,*sender.membership_snapshot()))
            self.assertEqual(receiver.metrics['accepted_verified'],3)
            self.assertEqual(receiver.metrics['image_codecs'],{'png':3})
            stamp=next(iter(runtime.monitor.snapshot().values()))['received']
            await asyncio.to_thread(control.exchange,*sender.membership_snapshot())
            self.assertEqual(next(iter(runtime.monitor.snapshot().values()))['received'],stamp)
            sender.set_tables([])
            ack=await asyncio.to_thread(control.exchange,*sender.membership_snapshot())
            self.assertEqual(ack['control_sequence'],3)
            self.assertFalse(runtime.monitor.snapshot())
            self.assertFalse(receiver.sequences)
            self.assertGreater(sender.last_transport['total_bytes_sent'],0)
        finally:
            sender.close();await receiver.close()

    async def test_control_recovers_after_central_restarts(self):
        runtime=SimpleNamespace(frames=Mailbox())
        receiver=StreamReceiver(runtime,'127.0.0.1',0)
        address=(await receiver.start())[:2]
        sender=ControlSender(address,'pc','session')
        await asyncio.to_thread(sender.exchange,[],1)
        await receiver.close()
        with self.assertRaises(OSError):await asyncio.to_thread(sender.exchange,[],1)
        receiver=StreamReceiver(runtime,*address)
        await receiver.start()
        try:
            await asyncio.to_thread(sender.exchange,[],1)
            self.assertEqual(receiver.metrics['accepted_controls'],1)
        finally:await receiver.close()
