"""Registro de TAGS MANUAIS por jogador (uid -> tag) — [[nvt-exploit-anti-bot-pppoker]].

A marcação é NOSSA e MANUAL (Eduardo decide — [[nvt-autoridade-eduardo-decide]]): durante o
grind o Henrique marca o uid com uma etiqueta ('bote', 'station', 'bom', 'nvt', ou QUALQUER
tag nova que o Eduardo criar) e é a etiqueta que define o plano (via `tag_plan`). A auto-
detecção (`bot_exploit.detect_bot`) só SUGERE; quem grava é esta marcação manual.

Persistente em JSON (logs/player_tags.json por padrão). Puro armazenamento: não lê tela,
não clica, não decide poker. A camada de marcar clicando no HUD ao vivo pluga aqui depois.

    store = TagStore.load()
    store.set('11592929', 'bote', note='limp-reraise clássico')
    store.get('11592929')            # {'tag': 'bote', 'note': ..., 'source': 'manual', ...}
    store.by_tag('bote')             # ['11592929', ...]
    store.save()
"""
from __future__ import annotations

import json
import os
import time

DEFAULT_PATH = os.path.join('logs', 'player_tags.json')


def _norm_uid(uid):
    return str(uid).strip()


def _norm_tag(tag):
    """Normaliza a etiqueta: minúscula, sem espaços nas bordas. Mantém a tag como o Eduardo
    escreveu (livre); os ALIASES conhecidos ('bot'->'bote' etc.) ficam no `tag_plan`."""
    return str(tag).strip().lower()


class TagStore:
    def __init__(self, data=None, path=DEFAULT_PATH):
        self._data = dict(data or {})
        self.path = path

    # ---- leitura ----
    def get(self, uid):
        """Registro do uid ou None. {'tag','note','source','updated'}."""
        return self._data.get(_norm_uid(uid))

    def tag_of(self, uid):
        r = self.get(uid)
        return r['tag'] if r else None

    def all(self):
        return dict(self._data)

    def by_tag(self, tag):
        t = _norm_tag(tag)
        return [uid for uid, r in self._data.items() if r.get('tag') == t]

    def tags_in_use(self):
        return sorted({r['tag'] for r in self._data.values() if r.get('tag')})

    # ---- escrita ----
    def set(self, uid, tag, *, note='', source='manual'):
        """Marca/atualiza o uid com a etiqueta. Retorna o registro gravado."""
        uid = _norm_uid(uid)
        rec = dict(tag=_norm_tag(tag), note=str(note or ''), source=source,
                   updated=time.strftime('%Y-%m-%dT%H:%M:%S'))
        self._data[uid] = rec
        return rec

    def remove(self, uid):
        """Remove a marcação do uid. Retorna True se existia."""
        return self._data.pop(_norm_uid(uid), None) is not None

    # ---- persistência ----
    @classmethod
    def load(cls, path=DEFAULT_PATH):
        try:
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
        return cls(data if isinstance(data, dict) else {}, path=path)

    def save(self, path=None):
        p = path or self.path
        os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=1, sort_keys=True)
        return p
