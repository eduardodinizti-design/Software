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

    def inspect_windows(self, windows, identities):
        import ctypes
        user = MagicMock()
        user.IsWindowVisible.return_value = True
        user.IsIconic.return_value = False
        user.GetForegroundWindow.return_value = 1
        user.GetWindowTextLengthW.return_value = 40
        def title(hwnd, buf, size):
            buf.value = windows[hwnd][0]
            return len(buf.value)
        def rect(hwnd, ptr):
            x,y,w,h = windows[hwnd][1]
            ptr._obj.left,ptr._obj.top = x,y
            ptr._obj.right,ptr._obj.bottom = x+w,y+h
            return 1
        def enumerate_windows(callback, param):
            for hwnd in windows: callback(hwnd, param)
            return 1
        user.GetWindowTextW.side_effect = title
        user.GetWindowRect.side_effect = rect
        user.GetClientRect.side_effect = rect
        user.ClientToScreen.return_value = 1
        user.EnumWindows.side_effect = enumerate_windows
        with patch.object(guardian.sys,'platform','win32'), patch.object(ctypes,'windll',types.SimpleNamespace(user32=user),create=True), patch.object(ctypes,'WINFUNCTYPE',lambda *args: lambda fn: fn,create=True), patch.object(guardian,'get_process_info_for_hwnd',side_effect=lambda hwnd: identities[hwnd]):
            result = guardian.WindowVisibilityGuardian().inspect_and_prepare_window()
        return result, user

    def test_browser_with_pppoker_title_is_not_fallback_target(self):
        result, user = self.inspect_windows(
            {1: ('PPPoker - Chrome', (0,0,800,1400))},
            {1: {'is_valid':False,'is_forbidden':True,'pid':11,'executable':'chrome.exe'}})
        self.assertFalse(result.is_found)
        self.assertEqual(result.occlusion_status,'WINDOW_NOT_FOUND')
        user.EnumWindows.assert_called_once()
        user.GetClientRect.assert_not_called()

    def test_terminal_above_real_client_blocks_capture(self):
        result, _ = self.inspect_windows(
            {1: ('Terminal', (0,0,800,700)), 2: ('PPPoker', (0,0,800,1400))},
            {1: {'is_valid':False,'is_forbidden':True,'pid':11,'executable':'cmd.exe'},
             2: {'is_valid':True,'is_forbidden':False,'pid':22,'executable':'pppoker.exe'}})
        self.assertTrue(result.is_found)
        self.assertEqual(result.process_info['pid'],22)
        self.assertEqual(result.occlusion_status,'WINDOW_OCCLUDED')
        self.assertFalse(result.frame_valid_for_ocr)
