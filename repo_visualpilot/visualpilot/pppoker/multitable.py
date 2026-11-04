"""Independent discovery and bounded multi-table previews. No poker inference."""
import threading
import os
from datetime import datetime, timezone
from queue import Queue, Empty, Full
from time import monotonic

import numpy as np
from PIL import Image

from .capture import ScreenCapture
from .core import Region, change_ratio
from .discovery import scan_monitors, table_anchor_visible
from .history import History
from .table_registry import TableRegistry, overlap
from .window_geometry import native_windows, own_boxes, attach_windows, capture_blocked


def latest(queue, value):
    try:
        queue.put_nowait(value)
    except Full:
        try:
            queue.get_nowait()
        except Empty:
            pass
        queue.put_nowait(value)


def discover(stop, results, exclusions, capture_factory=ScreenCapture,
             windows_reader=native_windows, interval=5.):
    try:
        with capture_factory() as capture:
            while not stop.is_set():
                windows = windows_reader()
                excluded = own_boxes(windows) + list(exclusions())
                reports, found = scan_monitors(capture, stop, excluded=excluded)
                if stop.is_set():
                    return
                found = attach_windows(found, windows)
                # Replayers/profiles can cover the blue table. Keep native portrait PPPoker
                # windows as candidates; the OCR classifier decides whether they are tables.
                for win in windows or []:
                    key=f"{win['pid']}:{win['handle']}"
                    x,y,w,h=win['box']
                    if (win['pid']==os.getpid() or 'pppoker' not in win['title'].lower() or not .35<w/max(1,h)<.9 or w<240
                            or any(d.get('window_key')==key or overlap(d['box'],win['box'])>.75 for d in found)):
                        continue
                    report=next((r for r in reports if r['region']['left']<=x+w/2<r['region']['left']+r['region']['width']
                                 and r['region']['top']<=y+h/2<r['region']['top']+r['region']['height']),None)
                    if report:
                        found.append(dict(monitor=report['monitor'],box=win['box'],score=1.,window_key=key,
                            window_box=win['box'],binding='native',binding_reason='Janela PPPoker; classificando mesa, replayer ou tela inicial',candidate_only=True))
                # Native association improves tracking but must not silently
                # erase a visual table. Visual-only targets never authorize clicks.
                for report in reports:
                    items = [d for d in found if d['monitor'] == report['monitor']]
                    report['tables'] = len(items)
                    report['native_bindings'] = sum(d['binding'] == 'native' for d in items)
                    report['visual_bindings'] = sum(d['binding'] == 'visual' for d in items)
                    report['candidates'] = [{'box': d['box'], 'binding': d['binding'],
                                             'reason': d['binding_reason']} for d in items]
                present = None if windows is None else [f"{w['pid']}:{w['handle']}"
                            for w in windows if 'pppoker' in w['title'].lower()]
                latest(results, {'reports': reports, 'found': found, 'present_windows': present})
                stop.wait(interval)
    except Exception as exc:
        latest(results, {'error': str(exc), 'reports': [], 'found': []})


def observe_tables(root, stop, output, exclusions=lambda: (), interval=.5,
                   capture_factory=ScreenCapture, windows_reader=native_windows,
                   discovery_fn=discover, frame_sink=None, session_id=None, max_tables=None, before_capture=None,
                   tables_sink=None):
    """One full ROI at a time; only small per-table previews are retained."""
    results = Queue(maxsize=1)
    finder = threading.Thread(target=discovery_fn, daemon=True,
                              args=(stop, results, exclusions, capture_factory, windows_reader))
    registry = TableRegistry()
    tracks, reports, states = [], [], {}
    db = None
    session = None
    counter = 0
    reason = 'stopped'
    error = None
    discovery_complete = False
    try:
        db = History(root)
        session = session_id or db.start('multitable')
        folder = str(db.folder(session))
        finder.start()

        def record(payload):
            nonlocal counter
            counter += 1
            db.observe(session, dict(payload, frame_count=counter,
                                     recorded_at=datetime.now(timezone.utc).isoformat()))

        with capture_factory() as capture:
            while not stop.is_set():
                started = monotonic()
                try:
                    result = results.get_nowait()
                except Empty:
                    result = None
                if result is not None:
                    discovery_complete = True
                    reports = result['reports']
                    if result.get('error'):
                        raise RuntimeError(result['error'])
                    tracks, retired = registry.update(result['found'], result.get('present_windows'))
                    if max_tables is not None:
                        if sum(t['visible'] for t in tracks) > max_tables:
                            raise RuntimeError('Mais de seis mesas detectadas; reduza as mesas visíveis antes de iniciar.')
                    for item in retired:
                        states.pop(item['table_key'], None)
                        record({'state': 'table_lost', 'table_key': item['table_key'],
                                'number': item['number']})
                    record({'state': 'table_discovery', 'tables': tracks, 'monitors': reports})
                    visible_tracks=[t for t in tracks if t['visible']]
                    # A failed/unavailable monitor is not evidence of zero tables.
                    empty_confirmed=bool(reports) and not any(r.get('error') for r in reports)
                    if tables_sink is not None and (visible_tracks or empty_confirmed):
                        # A still-open host can contain several rearranged ROIs.
                        # Retained identity tracks are not evidence that an old
                        # ROI remains a current table on the remote panel.
                        tables_sink(visible_tracks)
                windows = windows_reader()
                excluded = own_boxes(windows) + list(exclusions())
                rows = []
                for item in tracks:
                    if stop.is_set():
                        break
                    key = item['table_key']
                    state = states.setdefault(key, {'count': 0, 'small': None,
                                                     'last_log': 0., 'last_state': None})
                    status = 'aguardando nova detecção'
                    detail, captured_at, delta = '', None, None
                    preview = None
                    try:
                        blocked = capture_blocked(item, windows, excluded)
                        if blocked:
                            status = blocked
                        elif item['visible'] and before_capture is not None and not before_capture(item):
                            status='aguardando autorização temporal da Central'
                        elif item['visible']:
                            rgb = capture.grab(Region(*item.get('capture_box', item['box'])))
                            post_windows = windows_reader()
                            blocked = capture_blocked(item, post_windows,
                                                      own_boxes(post_windows)+list(exclusions()))
                            if blocked:
                                status = blocked
                            elif item.get('binding') == 'visual' and not table_anchor_visible(rgb):
                                status = 'mesa não confirmada nesta captura'
                            else:
                                preview = Image.fromarray(rgb)
                                preview.thumbnail((220, 370))
                                small = np.array(preview)
                                if state['small'] is not None and state['small'].shape == small.shape:
                                    delta = round(change_ratio(state['small'], small), 6)
                                state['small'] = small
                                state['count'] += 1
                                captured_at = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
                                status = 'capturando'
                                if frame_sink is not None:
                                    if frame_sink(item,rgb,captured_at) is False:
                                        status='envio não confirmado; aguardando nova captura'
                            del rgb
                    except Exception as exc:
                        status, detail = 'erro de captura', str(exc)
                    row = dict(item, state=status, detail=detail, captures=state['count'],
                               captured_at=captured_at, delta=delta,
                               identity_state='pending', hand_state='not_analyzed')
                    if state['last_state'] != status or monotonic()-state['last_log'] >= 5:
                        record(row)
                        state.update(last_log=monotonic(), last_state=status)
                    rows.append(dict(row, preview=preview))
                latest(output, {'tables': rows, 'reports': reports, 'session': session,
                                'folder': folder, 'finished': False,
                                'discovery_complete': discovery_complete,
                                'cycle_ms': round((monotonic()-started)*1000, 1)})
                stop.wait(max(0., interval-(monotonic()-started)))
    except Exception as exc:
        error, reason = str(exc), 'error'
    finally:
        stop.set()
        if finder.ident is not None:
            finder.join()
        if db:
            try:
                if session and session_id is None:
                    db.finish(session, reason)
            except Exception as exc:
                error = str(exc)
            finally:
                db.close()
        latest(output, {'finished': True, 'error': error, 'tables': [], 'reports': []})
