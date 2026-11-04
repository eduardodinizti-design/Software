"""A moved visual ROI must not leave an obsolete table in the remote panel."""
import asyncio
import json
from queue import Queue
from types import SimpleNamespace
import unittest

import numpy as np

from visualpilot.pppoker.observer.runtime import Mailbox
from visualpilot.pppoker.stream_node import FrameSender, encode_frame
from visualpilot.pppoker.stream_receiver import StreamReceiver
from visualpilot.pppoker.transport_freshness import CaptureTicket
from visualpilot.viz.monitor import LiveMonitor
from visualpilot.viz.session import RemoteSession


class MembershipTests(unittest.TestCase):
    def test_failed_or_missing_monitors_do_not_advertise_zero_tables(self):
        import tempfile
        import threading
        from unittest.mock import Mock
        from visualpilot.pppoker.multitable import observe_tables,latest
        class Capture:
            def __enter__(self):return self
            def __exit__(self,*args):pass
        for reports in ([],[{'state':'error','error':'grab failed'}],[{'state':'captured'}]):
            with self.subTest(reports=reports),tempfile.TemporaryDirectory() as root:
                stop=threading.Event();sink=Mock()
                def discover(cancel,results,*args):latest(results,dict(found=[],reports=reports))
                def event(value):
                    if value.get('discovery_complete'):stop.set()
                output=SimpleNamespace(put_nowait=event)
                timer=threading.Timer(3,stop.set);timer.start()
                try:
                    observe_tables(root,stop,output,interval=.01,capture_factory=Capture,
                                   windows_reader=lambda:[],discovery_fn=discover,tables_sink=sink)
                finally:timer.cancel()
                if reports and not reports[0].get('error'):sink.assert_called_once_with([])
                else:sink.assert_not_called()

    def test_shared_host_staying_open_does_not_keep_old_rois_in_membership(self):
        import tempfile
        import threading
        from unittest.mock import patch
        from visualpilot.pppoker.multitable import observe_tables, latest
        stop, advance = threading.Event(), threading.Event()
        lists = []
        found = [dict(monitor=1, box=[100*i, 0, 80, 100], score=.95,
                      window_key='shared', window_box=[0, 0, 2000, 1200]) for i in range(3)]

        def discovery(cancel, results, *args):
            latest(results, dict(reports=[], found=found, present_windows=['shared']))
            if advance.wait(3):
                moved = [dict(item, box=[item['box'][0], 500, 80, 100]) for item in found]
                latest(results, dict(reports=[], found=moved, present_windows=['shared']))

        def membership(items):
            lists.append({item['table_key'] for item in items})
            if len(lists) == 1:
                advance.set()
            else:
                stop.set()

        class Capture:
            def __enter__(self): return self
            def __exit__(self, *args): pass

        timer = threading.Timer(5, stop.set)
        timer.start()
        try:
            with tempfile.TemporaryDirectory() as root, patch(
                    'visualpilot.pppoker.multitable.capture_blocked', return_value='aguardando'):
                observe_tables(root, stop, Queue(1), interval=.01,
                    capture_factory=Capture, windows_reader=lambda: [],
                    discovery_fn=discovery, tables_sink=membership)
        finally:
            timer.cancel()
        self.assertEqual(len(lists), 2)
        self.assertEqual([len(items) for items in lists], [3, 3])
        self.assertTrue(lists[0].isdisjoint(lists[1]))

    def setUp(self):
        self.runtime = SimpleNamespace(frames=Mailbox(), captures=Queue(1), monitor=LiveMonitor())
        self.receiver = StreamReceiver(self.runtime)
        self.image = np.full((100, 100, 3), 128, np.uint8)

    def packet(self, table, active, generation, *, ticket=None, member='pc', sequence=1):
        ticket = ticket or CaptureTicket()
        packet = encode_frame(member, 'session', table, sequence, self.image,
            capture_ticket=ticket.token, active_tables=active, membership_generation=generation)[4:]
        return packet, ticket

    def test_eight_rearrangements_remove_old_rois_without_exhausting_six_slots(self):
        panel = RemoteSession()
        for generation in range(1, 10):
            active = [f'{generation}-{index}' for index in range(3)]
            for table in active:
                self.assertTrue(self.receiver.accept_packet(*self.packet(table, active, generation)))
            expected = {json.dumps(['pc', 'session', t], separators=(',', ':')) for t in active}
            self.assertEqual(set(self.receiver.sequences), expected)
            self.assertEqual(set(self.runtime.monitor.snapshot()), expected)
            self.assertEqual(set(self.runtime.frames.pending), expected)
            panel.tables = {key: dict(reading=dict(hero=['As', 'Ks']), observed=0) for key in
                            [*panel.tables, *expected]}
            panel.output.put(dict(kind='tables', value=self.runtime.captures.get_nowait()))
            panel.poll()
            self.assertEqual(set(panel.tables), expected)

    def test_expired_invalid_and_older_membership_cannot_retire_current_tables(self):
        self.receiver.accept_packet(*self.packet('current', ['current'], 2))
        original = dict(self.receiver.sequences)
        now = [0.]
        expired = CaptureTicket(clock=lambda: now[0])
        now[0] = 6.
        cases = [self.packet('old', ['old'], 1),
                 self.packet('other', ['other'], 2),
                 self.packet('bad', [], 3),
                 self.packet('bad', ['bad'], 3, ticket=expired)]
        packet, ticket = self.packet('broken-image', ['broken-image'], 3)
        cases.append((packet[:-10], ticket))
        for packet, ticket in cases:
            with self.assertRaises(ValueError):
                self.receiver.accept_packet(packet, ticket)
            self.assertEqual(self.receiver.sequences, original)

    def test_one_member_never_removes_another_members_tables(self):
        self.receiver.accept_packet(*self.packet('other', ['other'], 1, member='other-pc'))
        self.receiver.accept_packet(*self.packet('old', ['old'], 1))
        self.receiver.accept_packet(*self.packet('new', ['new'], 2))
        self.assertEqual({v[0] for v in self.receiver.identities.values()}, {'pc', 'other-pc'})
        self.assertEqual({v[2] for v in self.receiver.identities.values()}, {'new', 'other'})


class MembershipSocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_central_can_stop_while_collector_connection_is_still_open(self):
        receiver = StreamReceiver(SimpleNamespace(frames=Mailbox()), '127.0.0.1', 0)
        host, port = (await receiver.start())[:2]
        reader, writer = await asyncio.open_connection(host, port)
        try:
            from visualpilot.pppoker.transport_freshness import read_capture_ticket
            await read_capture_ticket(reader)
            await asyncio.wait_for(receiver.close(), 2)
            self.assertEqual(await asyncio.wait_for(reader.read(), 2), b'')
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_actual_sender_advertises_rearranged_tables_over_tcp(self):
        runtime = SimpleNamespace(frames=Mailbox(), monitor=LiveMonitor())
        receiver = StreamReceiver(runtime, '127.0.0.1', 0)
        host, port = (await receiver.start())[:2]
        sender = FrameSender(host, port, 'pc')
        def send(table):
            item = dict(table_key=table)
            self.assertTrue(sender.before_capture(item))
            self.assertTrue(sender.send(item, np.zeros((100, 100, 3), np.uint8)))
        try:
            sender.set_tables([dict(table_key='before-move')])
            await asyncio.to_thread(send, 'before-move')
            sender.set_tables([dict(table_key='after-move')])
            await asyncio.to_thread(send, 'after-move')
            # Receipt of the next ticket acknowledges receiver processing.
            await asyncio.to_thread(sender.before_capture, dict(table_key='after-move'))
            self.assertEqual([identity[2] for identity in receiver.identities.values()], ['after-move'])
            self.assertEqual(receiver.metrics['accepted_verified'], 2)
        finally:
            sender.close()
            await receiver.close()
