import unittest
from unittest.mock import patch, Mock
import sys
from tools.validate_distribution import matches_startup, stop_process_tree
from visualpilot.viz import launcher


class LauncherTests(unittest.TestCase):
    def test_occupied_port_fails_before_health_thread_can_open_other_central(self):
        import json, os, socket, subprocess, tempfile
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        with socket.socket() as server, tempfile.TemporaryDirectory() as folder:
            server.bind(('127.0.0.1', 0))
            server.listen()
            port = server.getsockname()[1]
            code = ("from visualpilot.viz import launcher; "
                    f"launcher.PANEL_URL='http://127.0.0.1:{port}'; "
                    "launcher.open_when_ready=lambda **kw: (_ for _ in ()).throw(AssertionError('health thread must not start')); "
                    "launcher.main()")
            result = subprocess.run([sys.executable, '-c', code], cwd=folder, timeout=10,
                env=dict(os.environ, PYTHONPATH=str(root), VISUALPILOT_VALIDATE_STARTUP='busy-port'),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertNotEqual(result.returncode, 0)
            state = json.loads((Path(folder)/'central_status.json').read_text())
            self.assertEqual(state['phase'], 'failed')
            self.assertIn(f'porta {port}', state['error'])
            self.assertIn('Gerenciador de Tarefas', state['error'])
            self.assertNotIn('health thread must not start', (Path(folder)/'central_startup.log').read_text())

    def test_browser_waits_for_health(self):
        response = Mock()
        response.__enter__ = Mock(return_value=Mock(status=200))
        response.__exit__ = Mock(return_value=False)
        opener = Mock(side_effect=[OSError('starting'), response])
        browser = Mock()
        with patch.object(launcher.time, 'sleep'):
            self.assertTrue(launcher.open_when_ready(opener=opener, browser=browser))
        browser.assert_called_once_with(launcher.PANEL_URL)

    def test_browser_does_not_open_on_timeout(self):
        browser = Mock()
        self.assertFalse(launcher.open_when_ready(timeout=0, browser=browser))
        browser.assert_not_called()

    def test_embedded_startup_without_stdin_or_valid_credentials(self):
        import json, os, socket, subprocess, tempfile, time, uuid
        from pathlib import Path
        from urllib.request import urlopen
        root=Path(__file__).resolve().parents[1]
        for credentials in (None, 'email = ""', '[general]\nemail = ""'):
            with self.subTest(credentials=credentials), tempfile.TemporaryDirectory() as folder:
                path=Path(folder);settings=path/'.streamlit';settings.mkdir()
                if credentials is not None:(settings/'credentials.toml').write_text(credentials)
                (settings/'config.toml').write_text('[server]\nheadless = false\nenableCORS = false\n')
                with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
                token=uuid.uuid4().hex
                env=dict(os.environ,HOME=folder,USERPROFILE=folder,PYTHONPATH=str(root),VISUALPILOT_VALIDATE_STARTUP=token)
                code=f"import sys; sys.stdin=None; sys.stdout=None; sys.stderr=None; from visualpilot.viz import launcher; launcher.PANEL_URL='http://127.0.0.1:{port}'; launcher.main()"
                process=subprocess.Popen([sys.executable,'-c',code],cwd=folder,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    ready=False
                    for _ in range(100):
                        if process.poll() is not None:break
                        try:
                            state=json.loads((path/'central_status.json').read_text())
                            if matches_startup(state, token, launcher.BUILD_ID, f'http://127.0.0.1:{port}'):
                                with urlopen(f'http://127.0.0.1:{port}/_stcore/health',timeout=1) as response:ready=response.status==200
                                if ready:break
                        except (OSError,ValueError):pass
                        time.sleep(.1)
                    self.assertTrue(ready,(path/'central_startup.log').read_text() if (path/'central_startup.log').exists() else 'no log')
                    self.assertEqual(state['validation_token'],token)
                    self.assertEqual(state['build'],launcher.BUILD_ID)
                    if credentials is not None:self.assertEqual((settings/'credentials.toml').read_text(),credentials)
                    self.assertNotIn('lost sys.stdin',(path/'central_startup.log').read_text())
                finally:
                    stop_process_tree(process)

    def test_identity_accepts_child_pid_but_rejects_other_launches(self):
        state=dict(pid=5168,phase='ready',validation_token='unique-run',build=launcher.BUILD_ID,url=launcher.PANEL_URL)
        self.assertTrue(matches_startup(state,'unique-run',launcher.BUILD_ID,launcher.PANEL_URL))
        for field,value in [('validation_token','previous-run'),('build','old-build'),('url','http://127.0.0.1:8502'),('phase','configured')]:
            self.assertFalse(matches_startup(dict(state,**{field:value}),'unique-run',launcher.BUILD_ID,launcher.PANEL_URL))
        self.assertFalse(matches_startup(dict(state,validation_token=''),'',launcher.BUILD_ID,launcher.PANEL_URL))

    def test_windows_cleanup_terminates_launcher_and_children(self):
        process=Mock(pid=20448)
        process.poll.return_value=None
        with patch('tools.validate_distribution.sys.platform','win32'), patch('tools.validate_distribution.subprocess.run') as run:
            stop_process_tree(process)
        self.assertEqual(run.call_args.args[0],['taskkill','/PID','20448','/T','/F'])
        process.wait.assert_called_once_with(timeout=10)
