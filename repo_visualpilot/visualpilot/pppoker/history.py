"""Componente observacional recuperado do projeto enviado; ver docs/LEGACY_REUSE.md."""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4
HEADER = re.compile(b'PPPoker Hand #(\\d+(?:-\\d+)*):  Tournament #(\\d+), [^\\r\\n]+ - (\\d{4})/(\\d{2})/(\\d{2}) \\d{1,2}:\\d{2}(?::\\d{2})?(?: UTC)?\\r?\\n')

class History:

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'historico.sqlite3', timeout=15)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('\n        CREATE TABLE IF NOT EXISTS sessions (\n          id TEXT PRIMARY KEY, started TEXT NOT NULL, ended TEXT, status TEXT NOT NULL,\n          folder TEXT NOT NULL UNIQUE, kind TEXT NOT NULL);\n        CREATE TABLE IF NOT EXISTS observations (\n          session_id TEXT NOT NULL REFERENCES sessions(id), frame INTEGER NOT NULL,\n          payload TEXT NOT NULL, PRIMARY KEY(session_id,frame));\n        CREATE TABLE IF NOT EXISTS hands (\n          session_id TEXT NOT NULL REFERENCES sessions(id), hand_id TEXT NOT NULL,\n          tournament TEXT NOT NULL, date TEXT NOT NULL, ordinal INTEGER NOT NULL,\n          raw BLOB NOT NULL, PRIMARY KEY(session_id,hand_id));\n        ')

    def start(self, kind='capture', when=None):
        now = when or datetime.now().astimezone()
        sid = uuid4().hex
        relative = Path(now.strftime('%Y-%m-%d')) / ('Sessao_' + now.strftime('%H%M%S') + '_' + sid[:8])
        (self.root / relative).mkdir(parents=True)
        with self.db:
            self.db.execute('INSERT INTO sessions VALUES (?,?,NULL,?,?,?)', (sid, now.isoformat(), 'active', str(relative), kind))
        return sid

    def finish(self, sid, status='stopped'):
        with self.db:
            self.db.execute('UPDATE sessions SET ended=?,status=? WHERE id=?', (datetime.now().astimezone().isoformat(), status, sid))

    def observe(self, sid, payload):
        with self.db:
            self.db.execute('INSERT INTO observations VALUES (?,?,?)', (sid, payload['frame_count'], json.dumps(payload, ensure_ascii=False, allow_nan=False)))

    def folder(self, sid):
        row = self.db.execute('SELECT folder FROM sessions WHERE id=?', (sid,)).fetchone()
        if row is None:
            raise ValueError('Sessão inexistente.')
        return self.root / row[0]

    def close(self):
        self.db.close()

    def sessions(self):
        return self.db.execute('SELECT s.id,s.started,s.status,s.kind,COUNT(h.hand_id) FROM sessions s LEFT JOIN hands h ON h.session_id=s.id GROUP BY s.id ORDER BY s.started DESC').fetchall()
