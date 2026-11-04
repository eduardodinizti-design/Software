import ast
import logging
from pathlib import Path
import types
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image
from visualpilot.pppoker import window_visibility_guardian as guardian

class WindowsCaptureContract(unittest.TestCase):
    def capture_function(self):
        source=Path(guardian.__file__).with_name('table_bot_runner.py').read_text()
        tree=ast.parse(source)
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='capture_window_frame')
        function.returns=None
        for arg in function.args.args:arg.annotation=None
        ns={'logger':logging.getLogger('capture-test')}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),'capture-test','exec'),ns)
        return ns['capture_window_frame']
    def test_negative_monitor_origin(self):
        with patch('PIL.ImageGrab.grab',return_value=Image.new('RGB',(5760,2160))) as grab:
            result=self.capture_function()((-1920,0,5760,2160))
            self.assertEqual(result.shape,(2160,5760,3))
            grab.assert_called_once_with(bbox=(-1920,0,3840,2160),all_screens=True)
    def test_wrong_capture_size_is_rejected(self):
        with patch('PIL.ImageGrab.grab',return_value=Image.new('RGB',(100,100))):
            self.assertIsNone(self.capture_function()((0,0,700,1400)))
    def test_access_denied_never_fabricates_pppoker(self):
        import ctypes
        user=types.SimpleNamespace(GetWindowThreadProcessId=MagicMock())
        def pid_query(hwnd,pid):pid._obj.value=123;return 1
        user.GetWindowThreadProcessId.side_effect=pid_query
        kernel=types.SimpleNamespace(OpenProcess=MagicMock(return_value=0),GetLastError=MagicMock(return_value=5),QueryFullProcessImageNameW=MagicMock(),CloseHandle=MagicMock())
        with patch.object(guardian.sys,'platform','win32'),patch.object(ctypes,'windll',types.SimpleNamespace(user32=user,kernel32=kernel),create=True):
            result=guardian.get_process_info_for_hwnd(1234)
        self.assertFalse(result['is_valid'])
        self.assertEqual(result['executable'],'')
        self.assertIn('PROCESS_ACCESS_DENIED',result['error'])
        kernel.CloseHandle.assert_not_called()
