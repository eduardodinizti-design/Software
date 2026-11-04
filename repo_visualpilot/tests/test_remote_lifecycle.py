import asyncio
import socket
import tempfile
from pathlib import Path
import unittest
from visualpilot.viz.session import RemoteSession


class RemoteLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_real_sessions_release_port_and_keep_separate_logs(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0))
            port = probe.getsockname()[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root/'stream_config.ini'
            config.write_text(f'[central]\nlisten_host=127.0.0.1\nport={port}\n')
            control = RemoteSession(root/'sessions',config)
            folders=[]
            for _ in range(2):
                control.start()
                try:
                    for attempt in range(100):
                        control.poll()
                        if control.folder or control.error: break
                        await asyncio.sleep(.05)
                    self.assertIsNone(control.error)
                    self.assertIsNotNone(control.folder)
                    folders.append(control.folder)
                    reader,writer = await asyncio.open_connection('127.0.0.1',port)
                    writer.close()
                    await writer.wait_closed()
                finally:
                    control.stop.set()
                    await asyncio.to_thread(control.thread.join,20)
                self.assertFalse(control.thread.is_alive())
                self.assertTrue((Path(control.folder)/'metricas.json').exists())
                self.assertTrue((Path(control.folder)/'percepcao.jsonl').exists())
            self.assertNotEqual(*folders)
            with socket.socket() as probe:
                probe.bind(('127.0.0.1',port))
