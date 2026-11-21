"""Capturador SEGURO de dataset (F1) — screenshots da mesa, ZERO Frida, ZERO clique.

Só observa: tira foto da janela do cliente, descarta quadros quase-iguais (dedup
por average-hash) e grava um número LIMITADO de PNGs + manifesto. Respeita a regra
(AGENTS.md): nada de gravar imagem continuamente/ilimitado; dedup + teto de disco.

Não injeta nada no jogo (não pode crashar o cliente). A rotulagem (cartas/stacks/
pote/posições) vem depois — por OCR do que a Suprema já escreve na tela e/ou pela
verdade do Frida read-only numa sessão dedicada (auto-rotulagem, F1).

Uso:
    python -I vision_yolo/capture_dataset.py --proc SupremaPoker.exe --site suprema
    python -I vision_yolo/capture_dataset.py --max 400 --interval 1.5 --minutes 25
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import os
import sys
import time
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))


def _dpi_aware():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def find_hwnd(proc_name: str):
    """Maior janela visível do processo dado (ex.: SupremaPoker.exe)."""
    import subprocess
    u = ctypes.windll.user32
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True).stdout
    pids = set()
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == proc_name.lower():
            try:
                pids.add(int(parts[1]))
            except ValueError:
                pass
    best = [None, 0, None]
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def cb(h, _):
        pid = wt.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in pids and u.IsWindowVisible(h) and not u.IsIconic(h):
            r = wt.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            area = (r.right - r.left) * (r.bottom - r.top)
            if area > best[1]:
                best[0], best[1], best[2] = h, area, (r.left, r.top, r.right, r.bottom)
        return True
    u.EnumWindows(WNDENUMPROC(cb), 0)
    return best[0], best[2]


def _ahash(img) -> int:
    """average-hash 8x8 (64 bits) — barato e bom p/ detectar quadro quase-igual."""
    g = img.convert("L").resize((8, 8))
    px = list(g.getdata())
    avg = sum(px) / len(px)
    bits = 0
    for i, p in enumerate(px):
        if p >= avg:
            bits |= (1 << i)
    return bits


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def run(proc_name: str, site: str, max_frames: int, interval: float,
        minutes: float, dup_dist: int, log=print) -> int:
    _dpi_aware()
    from PIL import ImageGrab
    hwnd, rect = find_hwnd(proc_name)
    if not hwnd:
        log("[erro] janela de %s não encontrada (visível?)." % proc_name)
        return 2
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = os.path.join(_HERE, "data", "raw", site, stamp)
    os.makedirs(outdir, exist_ok=True)
    manifest = os.path.join(outdir, "manifest.jsonl")
    log("[capture] %s hwnd=%s rect=%s -> %s" % (proc_name, hex(hwnd), rect, outdir))
    log("[capture] teto=%d quadros, intervalo=%.1fs, limite=%.0f min, dedup<=%d. Ctrl+C p/ parar."
        % (max_frames, interval, minutes, dup_dist))

    recent: list[int] = []
    saved = 0
    deadline = time.time() + minutes * 60
    try:
        with open(manifest, "a", encoding="utf-8") as mf:
            while saved < max_frames and time.time() < deadline:
                t0 = time.time()
                # relê o rect (a janela pode mover)
                r = wt.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
                bbox = (r.left, r.top, r.right, r.bottom)
                try:
                    img = ImageGrab.grab(bbox=bbox, all_screens=True)
                except Exception as e:
                    log("[grab erro] %s" % e)
                    time.sleep(interval)
                    continue
                h = _ahash(img)
                if any(_hamming(h, p) <= dup_dist for p in recent[-12:]):
                    time.sleep(max(0.0, interval - (time.time() - t0)))
                    continue                       # quase-igual: descarta
                recent.append(h)
                saved += 1
                name = "f%04d.png" % saved
                img.save(os.path.join(outdir, name))
                mf.write(json.dumps({
                    "file": name, "ts": datetime.now().isoformat(timespec="seconds"),
                    "ahash": h, "rect": bbox, "size": list(img.size), "site": site,
                }, ensure_ascii=False) + "\n")
                mf.flush()
                if saved % 10 == 0:
                    log("[capture] %d/%d quadros únicos salvos" % (saved, max_frames))
                time.sleep(max(0.0, interval - (time.time() - t0)))
    except KeyboardInterrupt:
        log("\n[capture] interrompido.")
    log("[capture] FIM. %d quadros únicos em %s" % (saved, outdir))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Captura segura de dataset (screenshots, sem Frida).")
    p.add_argument("--proc", default="SupremaPoker.exe", help="processo do cliente")
    p.add_argument("--site", default="suprema", help="rótulo do site (pasta do dataset)")
    p.add_argument("--max", type=int, default=400, help="teto de quadros únicos")
    p.add_argument("--interval", type=float, default=1.5, help="intervalo entre fotos (s)")
    p.add_argument("--minutes", type=float, default=25.0, help="limite de tempo (min)")
    p.add_argument("--dup-dist", type=int, default=4, help="distância de hash p/ considerar duplicado")
    a = p.parse_args(argv)
    return run(a.proc, a.site, a.max, a.interval, a.minutes, a.dup_dist)


if __name__ == "__main__":
    raise SystemExit(main())
