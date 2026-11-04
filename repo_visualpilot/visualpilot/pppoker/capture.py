"""Capture contexts are opened and used on the same worker thread."""

import sys
import numpy as np
from .core import Region


def enable_thread_dpi_awareness():
    """Use physical desktop pixels on worker threads as well as the GUI thread."""
    if sys.platform != 'win32':return
    import ctypes
    try:
        fn=ctypes.windll.user32.SetThreadDpiAwarenessContext
        fn.argtypes=[ctypes.c_void_p];fn.restype=ctypes.c_void_p
        fn(ctypes.c_void_p(-4))
    except (AttributeError,OSError):pass


def enable_dpi_awareness():
    if sys.platform != 'win32':return
    import ctypes
    enabled=False
    try:
        fn=ctypes.windll.user32.SetProcessDpiAwarenessContext
        fn.argtypes=[ctypes.c_void_p];fn.restype=ctypes.c_int
        enabled=bool(fn(ctypes.c_void_p(-4)))
    except (AttributeError,OSError):pass
    if not enabled:
        try:ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError,OSError):ctypes.windll.user32.SetProcessDPIAware()
    enable_thread_dpi_awareness()


class ScreenCapture:
    def __enter__(self):
        enable_thread_dpi_awareness()
        import mss
        self.sct = mss.mss()
        return self

    def __exit__(self, *_args):
        self.sct.close()

    def monitors(self):
        keys = ("left", "top", "width", "height")
        return [Region(**{k: int(m[k]) for k in keys}) for m in self.sct.monitors[1:]]

    def grab(self, region):
        # Copy out of the capture buffer; GUI never reads a reused OS buffer.
        bgra = np.asarray(self.sct.grab(region.to_dict()))
        return np.ascontiguousarray(bgra[:, :, :3][:, :, ::-1])
