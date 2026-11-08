"""PPPoker table discovery for VisualPilot (discovery/identity only).

Scope is deliberately PPPoker-only (see the handoff: do not pull multi-room
support into the recognizer). This layer answers one question: among the live
top-level windows, which are PPPoker TABLES (green felt) and which are lobby/
login. It does not capture cards, move windows, open accounts or send input.

VisualPilot keeps its own validated capture: this only tells it which HWNDs to
observe. Identity still comes from VisualPilot binding each HWND to
pid + process_created at capture time; the pid here is informational.
"""
import argparse

from .detector import Detector, RoomRule
from .windows import enum_windows

PPPOKER_PROCESS = 'PPPoker.exe'

# A table window is PPPoker.exe, at least 150x150, showing green felt. The lobby
# and login windows are the same process without felt, so they are excluded.
PPPOKER_RULE = RoomRule(name='PPPoker', processes=[PPPOKER_PROCESS],
                        min_w=150, min_h=150, content_check='green')


def _as_dict(w, kind):
    return dict(hwnd=w.hwnd, pid=w.pid, process=w.process, title=w.title,
                rect=list(w.rect), x=w.x, y=w.y, w=w.w, h=w.h,
                minimized=w.minimized, room=w.room, kind=kind)


def discover_pppoker(windows=None):
    """Return {'tables': [...], 'lobbies': [...]} for PPPoker windows only.

    `windows` is an optional pre-enumerated list of WindowInfo (injected in
    tests); otherwise the live top-level windows are enumerated."""
    detector = Detector([PPPOKER_RULE])
    windows = detector.classify(windows if windows is not None else enum_windows())
    pppoker = [w for w in windows if w.process.lower() == PPPOKER_PROCESS.lower()]
    tables = [_as_dict(w, 'table') for w in pppoker if w.extra.get('is_table')]
    lobbies = [_as_dict(w, 'lobby') for w in pppoker if w.extra.get('is_lobby')]
    return {'tables': tables, 'lobbies': lobbies}


def pppoker_table_hwnds(windows=None, max_tables=6):
    """Live PPPoker table HWNDs (lobbies excluded), capped at max_tables."""
    tables = discover_pppoker(windows)['tables']
    return [t['hwnd'] for t in tables[:max_tables]]


def main(argv=None):
    parser = argparse.ArgumentParser(description='Lista as mesas PPPoker abertas (sem cliques, sem captura de cartas).')
    parser.add_argument('--json', action='store_true', help='Saida em JSON')
    args = parser.parse_args(argv)
    found = discover_pppoker()
    if args.json:
        import json
        print(json.dumps(found, ensure_ascii=False, indent=2))
        return 0
    tables, lobbies = found['tables'], found['lobbies']
    if not tables and not lobbies:
        print('Nenhuma janela PPPoker encontrada. Abra o PPPoker e tente novamente.')
        return 2
    for t in tables:
        print(f"MESA  | HWND {t['hwnd']} | PID {t['pid']} | {t['w']}x{t['h']} em ({t['x']},{t['y']}) | {t['title']}")
    for lob in lobbies:
        print(f"LOBBY | HWND {lob['hwnd']} | PID {lob['pid']} | {lob['title']} (ignorado para leitura)")
    print(f"\n{len(tables)} mesa(s) PPPoker, {len(lobbies)} lobby/login.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
