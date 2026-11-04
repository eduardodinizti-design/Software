"""Bounded visual evidence and explicit observational context for later study."""
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
import json
import cv2


class EvidenceArchive:
    def __init__(self, folder, interval=10.0, max_bytes=256*1024*1024):
        self.folder = Path(folder)
        self.interval = interval
        self.max_bytes = max_bytes
        self.bytes = 0
        self.last = {}
        self.files = {}
        self.count = 0

    def save(self, table, rgb, stamp):
        fingerprint = sha256(rgb.tobytes() + str(rgb.shape).encode()).hexdigest()
        if fingerprint in self.files:
            return dict(status='saved', path=self.files[fingerprint], sha256_pixels=fingerprint)
        if stamp - self.last.get(table, float('-inf')) < self.interval:
            return dict(status='throttled', path=None)
        if self.bytes >= self.max_bytes:
            return dict(status='limit_reached', path=None)
        try:
            ok, encoded = cv2.imencode('.png', cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_PNG_COMPRESSION, 3])
            if not ok:
                raise OSError('Falha ao codificar evidência.')
            if self.bytes + len(encoded) > self.max_bytes:
                return dict(status='limit_reached', path=None)
            target = self.folder / 'evidencias'
            target.mkdir(parents=True, exist_ok=True)
            name = 'evidencias/%06d.png' % (self.count + 1)
            (self.folder / name).write_bytes(encoded.tobytes())
            self.count += 1
            self.bytes += len(encoded)
            self.last[table] = stamp
            self.files[fingerprint] = name
            return dict(status='saved', path=name, sha256_pixels=fingerprint,
                        width=rgb.shape[1], height=rgb.shape[0])
        except Exception as exc:
            return dict(status='error', path=None, error=str(exc))


def study_record(record, raw_reading, evidence, age, now=None):
    """Never infer a player's motive or turn a persistent badge into an event."""
    now = now or datetime.now().astimezone()
    reading = record['reading']
    return dict(schema_version=2, at=now.isoformat(),
                captured_at_estimate=(now-timedelta(seconds=age)).isoformat(),
                capture_age_seconds=round(age, 4), **record,
                raw_reading=raw_reading, visual_evidence=evidence,
                study_context=dict(
                    hand_id=reading.get('hand_id'),
                    hero_cards=reading.get('hero', []),
                    board_cards=reading.get('board', []),
                    street=reading.get('street'),
                    pot_text=reading.get('pot'),
                    hero_stack_text=reading.get('hero_stack'),
                    available_buttons=reading.get('actions', []),
                    visible_badges=reading.get('observed_actions', []),
                    pko_observation=reading.get('pko'),
                    action_event_verified=False,
                    decision=dict(status='not_implemented', action=None,
                                  reason=None, strategy_version=None),
                    player_action_reason=None))
