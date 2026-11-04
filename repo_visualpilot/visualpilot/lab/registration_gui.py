"""Adapter for our own in-memory browser fixture; no desktop input or client URL."""
import json
import hashlib
from pathlib import Path
from time import monotonic

import cv2
import numpy as np

from .registration import LabControl
from .button_locator import load_template, locate_button


class RegistrationGUI:
    def __init__(self, page, reader, output, control=None, capture_region=None):
        if page.url != 'about:blank':
            raise ValueError('Use uma página nova para o simulador isolado.')
        self.page, self.reader = page, reader
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.control = control or LabControl()
        self.sequence = 0
        self.current = None
        self.last_error = None
        self.capture_region = capture_region
        assets = Path(__file__).with_name('assets')/'registration'
        self.templates = {action: load_template(assets/(action+'.png'))
                          for action in ('increase', 'decrease', 'register')}
        self.page.set_content(Path(__file__).with_name('registration_simulator.html').read_text())

    def pixels(self):
        # Preserve native pixels. Convert only the final point to CSS coordinates.
        # No DOM lookup locates a popup or button.
        raw = self.page.screenshot(type='png', full_page=False, scale='device', animations='disabled')
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        viewport = self.page.viewport_size
        if not viewport:
            raise ValueError('Viewport de laboratório indefinido.')
        ratios = (image.shape[1]/viewport['width'], image.shape[0]/viewport['height'])
        origin = (0, 0)
        if self.capture_region is not None:
            x, y, width, height = self.capture_region
            if (any(type(v) is not int for v in self.capture_region) or min(x, y) < 0
                    or min(width, height) <= 0 or x+width > viewport['width'] or y+height > viewport['height']):
                raise ValueError('Região de captura fora da imagem.')
            x, y, width, height = (round(x*ratios[0]), round(y*ratios[1]),
                                   round(width*ratios[0]), round(height*ratios[1]))
            image = image[y:y+height, x:x+width].copy()
            origin = (x, y)
            raw = cv2.imencode('.png', image)[1].tobytes()
        return raw, image, origin, ratios

    def sync_control(self):
        if self.page.url != 'about:blank':
            raise ValueError('Página externa não pertence ao laboratório.')
        state = self.page.evaluate('({revision:lab.revision,mode:lab.mode,token:lab.token})')
        if state['mode'] != self.control.mode:
            self.control.set_mode(state['mode'])
        return state

    def capture(self):
        self.current = None
        state = self.sync_control()
        observed = monotonic()
        raw, image, origin, ratios = self.pixels()
        buttons = {action: locate_button(image, template, origin=origin)
                   for action, template in self.templates.items()}
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        rows = self.reader.detect(rgb)
        original_rows = list(rows)
        # A second recognition of the same crop may confirm a weak line. Never
        # replace its digits with a conflicting reading or lower the threshold.
        for index, (box, text, score) in enumerate(rows):
            if score >= .95:
                continue
            x = max(0, int(min(p[0] for p in box))-4)
            y = max(0, int(min(p[1] for p in box))-4)
            right = min(rgb.shape[1], int(max(p[0] for p in box))+5)
            bottom = min(rgb.shape[0], int(max(p[1] for p in box))+5)
            repeated, confidence = self.reader.field(rgb[y:bottom, x:right])
            if ''.join(repeated.split()) == ''.join(str(text).split()) and confidence > score:
                rows[index] = (box, repeated, confidence)
        self.sequence += 1
        name = f'capture-{self.sequence:03d}.png'
        (self.output/name).write_bytes(raw)
        record = dict(rows=rows, original_rows=original_rows, observed=observed,
                      revision=[state['revision'], self.sequence], lab_revision=state['revision'],
                      receipt_token=state['token'], source='laboratory', image=name,
                      buttons=buttons, origin=list(origin), shape=list(image.shape),
                      viewport_scale=list(ratios),
                      pixels_sha256=hashlib.sha256(image.tobytes()).hexdigest())
        with (self.output/'observations.jsonl').open('a') as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=float)+'\n')
        self.current = record
        return record

    def apply(self, action, revision, token):
        self.last_error = None
        if self.page.url != 'about:blank' or action not in ('increase', 'decrease', 'register'):
            self.last_error = 'invalid_action_or_page'
            return False
        sample = self.current
        self.current = None  # A coordinate can be consumed only once.
        if sample is None or sample['revision'] != revision:
            self.last_error = 'observation_replaced_or_consumed'
            return False
        target = sample['buttons'][action]
        reason = None
        if sample['buttons']['register']['status'] != 'found' or target['status'] != 'found':
            reason = 'visual_button_missing_or_ambiguous'
        else:
            _, image, origin, ratios = self.pixels()
            if (list(origin) != sample['origin'] or list(image.shape) != sample['shape']
                    or list(ratios) != sample['viewport_scale']
                    or hashlib.sha256(image.tobytes()).hexdigest() != sample['pixels_sha256']):
                reason = 'image_changed_before_click'
            elif not 0 <= monotonic()-sample['observed'] <= 5:
                reason = 'expired_coordinates'
        applied = False
        point = None
        if reason is None:
            # The target comes from image pixels. The fixture only guards identity,
            # mode and hit-testing; it never supplies the coordinates to the locator.
            point = [v/ratio for v, ratio in zip(target['point'], sample['viewport_scale'])]
            applied = self.page.evaluate('value=>applyLabAt(value)', dict(action=action,
                point=point, revision=sample['lab_revision'], token=token))
            if not applied:
                reason = 'fixture_rejected_click'
        with (self.output/'clicks.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(action=action, point=point, image_point=target.get('point'), applied=applied,
                reason=reason, image=sample['image'], pixels_sha256=sample['pixels_sha256']))+'\n')
        self.last_error = reason
        return applied
