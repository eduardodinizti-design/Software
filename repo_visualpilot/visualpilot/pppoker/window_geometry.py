"""Read-only window geometry. Does not activate windows or move the mouse."""
import os
import sys


def native_windows():
    """Return visible top-level Windows windows, in front-to-back order."""
    if sys.platform != 'win32':
        return None
    from .capture import enable_thread_dpi_awareness
    enable_thread_dpi_awareness()
    import ctypes as c
    from ctypes import wintypes as w
    u = c.windll.user32
    callback_type = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    u.EnumWindows.argtypes = [callback_type, w.LPARAM]
    u.IsWindowVisible.argtypes = [w.HWND]
    u.IsIconic.argtypes = [w.HWND]
    u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
    u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
    u.GetWindowTextLengthW.argtypes = [w.HWND]
    u.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
    result = []

    @callback_type
    def visit(hwnd, _):
        if not u.IsWindowVisible(hwnd) or u.IsIconic(hwnd):
            return True
        rect, pid = w.RECT(), w.DWORD()
        if not u.GetWindowRect(hwnd, c.byref(rect)):
            return True
        u.GetWindowThreadProcessId(hwnd, c.byref(pid))
        title = c.create_unicode_buffer(u.GetWindowTextLengthW(hwnd) + 1)
        u.GetWindowTextW(hwnd, title, len(title))
        width, height = rect.right-rect.left, rect.bottom-rect.top
        if width > 0 and height > 0:
            result.append({'handle': int(hwnd), 'pid': pid.value, 'title': title.value,
                           'box': [rect.left, rect.top, width, height]})
        return True
    if not u.EnumWindows(visit, 0):
        raise OSError('Não foi possível consultar as janelas do Windows.')
    return result


def own_boxes(windows):
    return [item['box'] for item in windows or [] if item['pid'] == os.getpid()]


def intersects(a, b):
    return (a[0] < b[0]+b[2] and b[0] < a[0]+a[2]
            and a[1] < b[1]+b[3] and b[1] < a[1]+a[3])


def attach_windows(found, windows):
    """Keep visual detections even when Windows cannot provide a unique binding."""
    result = []
    for item in found:
        item = dict(item)
        item.update(window_key=None, window_box=None, binding='visual',
                    binding_reason='Mesa visual; janela nativa ainda não confirmada')
        x, y, width, height = item['box']
        cx, cy = x+width/2, y+height/2
        for win in windows or []:
            a, b, w, h = win['box']
            if a <= cx < a+w and b <= cy < b+h:
                oversized_host = (w > width * 1.5 and h > height * 1.2
                                  and w * h > width * height * 2)
                if ('pppoker' in win['title'].lower() and win['pid'] != os.getpid()
                        and not oversized_host):
                    item.update(window_key=f"{win['pid']}:{win['handle']}",
                                window_box=win['box'], binding='native',
                                binding_reason='Janela PPPoker confirmada')
                else:
                    item['binding_reason'] = (
                        'Mesa visual; janela hospedeira muito maior que a mesa'
                        if oversized_host else
                        'Mesa visual; título da janela não confirmou PPPoker')
                break
        result.append(item)
    counts = {}
    for item in result:
        key = item.get('window_key')
        if key:
            counts[key] = counts.get(key, 0) + 1
    for item in result:
        if counts.get(item.get('window_key'), 0) > 1:
            item['binding_reason'] = 'Mais de uma região de mesa na mesma janela; regiões mantidas separadas'
            item['capture_box'] = item['box']
        elif item.get('window_key') and item.get('window_box'):
            # Uma janela PPPoker vinculada a uma única mesa fornece o recorte
            # exato. A detecção pela âncora pode ficar alguns pixels para dentro
            # e cortar cartas/botões nas bordas.
            item['capture_box'] = item['window_box']
        else:
            item['capture_box'] = item['box']
    return result


def capture_blocked(item, windows, excluded):
    capture_box = item.get('capture_box', item['box'])
    if any(intersects(capture_box, box) for box in excluded):
        return 'coberta pelo Visual Pilot'
    if windows is None or not item.get('window_key'):
        return None
    for win in windows:
        key = f"{win['pid']}:{win['handle']}"
        if key == item['window_key']:
            return None if win['box'] == item['window_box'] else 'movida; aguardando busca'
        if intersects(capture_box, win['box']):
            return 'coberta por outra janela'
    return 'janela indisponível'
