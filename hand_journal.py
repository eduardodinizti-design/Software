"""Durable scalar-only hand evidence and at-most-once input claims.

SQLite transactions survive a restart between mouse-down and observation. An
UNKNOWN claim is never retried automatically. No images, credentials or network.
"""
import json
from pathlib import Path
import sqlite3
import threading
import time

from strategy.state_contract import digest


class HandJournal:
    def __init__(self, path='runtime/hu/hand-history.sqlite3', *, retain_hands=10000):
        self.path = str(Path(path).resolve()) if str(path) != ':memory:' else ':memory:'
        if self.path != ':memory:':
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.db = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS hands (
                identity TEXT PRIMARY KEY, table_id TEXT NOT NULL, hand_id TEXT NOT NULL,
                created REAL NOT NULL, terminal INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, identity TEXT NOT NULL, event_id TEXT NOT NULL,
                payload TEXT NOT NULL, previous_hash TEXT, event_hash TEXT NOT NULL,
                UNIQUE(identity,event_id));
            CREATE INDEX IF NOT EXISTS event_identity ON events(identity,id);
            CREATE TABLE IF NOT EXISTS claims (
                decision_id TEXT PRIMARY KEY, identity TEXT NOT NULL, state TEXT NOT NULL,
                details TEXT NOT NULL, updated REAL NOT NULL);
        ''')
        self.db.commit()
        self.retain_hands = max(100, int(retain_hands))

    @staticmethod
    def identity(table_id, hand_id):
        return digest([str(table_id), str(hand_id)])

    def append(self, table_id, hand_id, event_id, payload):
        identity = self.identity(table_id, hand_id)
        text = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
        with self._lock, self.db:
            self.db.execute('INSERT OR IGNORE INTO hands(identity,table_id,hand_id,created) VALUES(?,?,?,?)',
                            (identity, str(table_id), str(hand_id), time.time()))
            old = self.db.execute('SELECT payload,event_hash FROM events WHERE identity=? AND event_id=?',
                                  (identity, event_id)).fetchone()
            if old:
                if old[0] != text:
                    raise ValueError('JOURNAL_EVENT_ID_REUSED_WITH_DIFFERENT_DATA')
                return old[1]
            previous = self.db.execute('SELECT event_hash FROM events WHERE identity=? ORDER BY id DESC LIMIT 1',
                                       (identity,)).fetchone()
            previous = previous[0] if previous else None
            h = digest([previous, event_id, json.loads(text)])
            self.db.execute('INSERT INTO events(identity,event_id,payload,previous_hash,event_hash) VALUES(?,?,?,?,?)',
                            (identity, event_id, text, previous, h))
            return h

    def claim(self, table_id, hand_id, decision_id, details):
        identity = self.identity(table_id, hand_id)
        with self._lock, self.db:
            cursor = self.db.execute('UPDATE claims SET state=?,details=?,updated=? WHERE decision_id=? AND state=?',
                ('RESERVED', json.dumps(details, sort_keys=True), time.time(), decision_id, 'CANCELLED_BEFORE_INPUT'))
            if cursor.rowcount == 1:
                return True
            cursor = self.db.execute('INSERT OR IGNORE INTO claims VALUES(?,?,?,?,?)',
                (decision_id, identity, 'RESERVED', json.dumps(details, sort_keys=True), time.time()))
            return cursor.rowcount == 1

    def last_state(self, table_id, hand_id):
        for event in reversed(self.events(table_id, hand_id)):
            if event['payload'].get('event_type') == 'state_confirmed':
                return event['payload']
        return None

    def settle(self, decision_id, state, details):
        if state not in ('CANCELLED_BEFORE_INPUT', 'INPUT_STARTED', 'CONFIRMED', 'UNKNOWN_RESULT'):
            raise ValueError('INVALID_CLAIM_STATE')
        with self._lock, self.db:
            row = self.db.execute('SELECT state FROM claims WHERE decision_id=?', (decision_id,)).fetchone()
            if row is None:
                raise ValueError('MISSING_DECISION_CLAIM')
            if row[0] in ('CONFIRMED', 'UNKNOWN_RESULT') and row[0] != state:
                raise ValueError('TERMINAL_CLAIM_CANNOT_BE_REOPENED')
            self.db.execute('UPDATE claims SET state=?, details=?, updated=? WHERE decision_id=?',
                            (state, json.dumps(details, sort_keys=True), time.time(), decision_id))

    def events(self, table_id, hand_id):
        identity = self.identity(table_id, hand_id)
        with self._lock:
            rows = self.db.execute('SELECT event_id,payload,previous_hash,event_hash FROM events WHERE identity=? ORDER BY id',
                                   (identity,)).fetchall()
        return [dict(event_id=e, payload=json.loads(p), previous_hash=prev, event_hash=h) for e, p, prev, h in rows]

    def export_hand(self, table_id, hand_id):
        events = self.events(table_id, hand_id)
        previous = None
        for e in events:
            if e['previous_hash'] != previous or digest([previous, e['event_id'], e['payload']]) != e['event_hash']:
                raise ValueError('JOURNAL_HASH_CHAIN_BROKEN')
            previous = e['event_hash']
        identity = self.identity(table_id,hand_id)
        with self._lock:
            claims = self.db.execute('SELECT decision_id,state,details FROM claims WHERE identity=? ORDER BY updated', (identity,)).fetchall()
            row = self.db.execute('SELECT terminal FROM hands WHERE identity=?',(identity,)).fetchone()
        states = [e['payload']['state'] for e in events if e['payload'].get('event_type')=='state_confirmed']
        return dict(schema='software.confirmed-hand.v1', table_id=str(table_id), hand_id=str(hand_id),
                    events=events, chain_valid=True,
                    execution_claims=[dict(decision_id=d,state=s,details=json.loads(p)) for d,s,p in claims],
                    unresolved_input=any(s in ('INPUT_STARTED','UNKNOWN_RESULT','RESERVED') for _,s,_ in claims),
                    completeness=dict(hand_closed=bool(row and row[0]),
                        has_confirmed_root=any(e['payload'].get('event_type')=='root_confirmed' for e in events),
                        has_observation_gaps=any(e['payload'].get('event_type')=='observation_gap' for e in events),
                        last_confirmed_terminal=states[-1].get('terminal') if states else None),
                    note='Each event states its evidence and precision. Gaps are not fabricated actions.')

    def close_hand(self, table_id, hand_id):
        with self._lock, self.db:
            self.db.execute('UPDATE hands SET terminal=1 WHERE identity=?', (self.identity(table_id, hand_id),))
            old = self.db.execute('SELECT identity FROM hands WHERE terminal=1 ORDER BY created DESC LIMIT -1 OFFSET ?',
                                  (self.retain_hands,)).fetchall()
            for (identity,) in old:
                self.db.execute('DELETE FROM events WHERE identity=?', (identity,))
                self.db.execute('DELETE FROM claims WHERE identity=?', (identity,))
                self.db.execute('DELETE FROM hands WHERE identity=?', (identity,))

    def close(self):
        with self._lock:
            self.db.close()
