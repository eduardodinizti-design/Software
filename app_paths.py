"""Caminhos PORTÁTEIS — o Henrique roda em QUALQUER PC, sem path absoluto hardcoded.

base_dir() entende PyInstaller (--onefile/onedir, sys.frozen). find_data() acha um
arquivo de dado (ranges, exploit_db) procurando em vários locais candidatos, então
funciona tanto rodando do fonte quanto empacotado quanto copiado p/ outra máquina.
"""
import os
import sys


def base_dir():
    """Pasta base do app: do EXE quando empacotado (frozen), senão a do repo."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def find_data(filename, *, subdirs=('', 'data', 'ranges', 'logs')):
    """1º caminho EXISTENTE de `filename`, procurando (nesta ordem): bundle do
    PyInstaller (_MEIPASS), pasta do app + subdirs, pasta PAI do app + subdirs
    (compat com o layout atual: ranges ficam ao lado do repo), e o CWD. Se não
    achar, devolve o candidato na pasta do app (p/ erro claro, não path de outra
    máquina)."""
    cands = []
    mp = getattr(sys, '_MEIPASS', None)
    b = base_dir()
    roots = [mp, b, os.path.dirname(b), os.getcwd()]
    for root in roots:
        if not root:
            continue
        for s in subdirs:
            cands.append(os.path.join(root, s, filename) if s else os.path.join(root, filename))
    for c in cands:
        try:
            if os.path.exists(c):
                return c
        except Exception:
            pass
    return os.path.join(b, filename)


def data_dir(name, *, create=True):
    """Pasta de dados GRAVÁVEL (logs/maos) relativa à base do app."""
    p = os.path.join(base_dir(), name)
    if create:
        try:
            os.makedirs(p, exist_ok=True)
        except Exception:
            pass
    return p
