"""Real screenshot/OCR adapter for the isolated lobby/details/modal/receipt page."""
import hashlib
import json
from pathlib import Path
from time import monotonic

from .lobby_gui import LobbyGUI


class RegistrationFlowGUI(LobbyGUI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page.set_content(Path(__file__).with_name('registration_flow_simulator.html').read_text())

    def set_mode(self, mode):
        if mode not in ('automatic', 'manual', 'paused') or self.page.url != 'about:blank':
            raise ValueError('Controle inválido.')
        self.page.evaluate('mode=>{lab.mode=mode;lab.revision++}', mode)

    def capture_stage(self, stage):
        if stage not in ('details', 'modal', 'receipt') or self.page.url != 'about:blank':
            raise ValueError('Etapa inválida.')
        # Bounded readiness, not a blind delay followed by a click. DOM is only a
        # fixture guard; all fields and button coordinates below come from pixels.
        self.page.wait_for_function('stage=>lab.stage===stage||lab.mode!=="automatic"', arg=stage, timeout=2000)
        image, sample = self.snapshot(stage)
        sample['rows'], sample['original_rows'] = self.read_rows(image)
        state = self.page.evaluate('({stage:lab.stage,token:lab.token})')
        if state['stage'] != stage:
            raise ValueError('Tela esperada não está disponível.')
        sample['receipt_token'] = state['token']
        sample['buttons'] = {}
        for action, label in (('open_modal', 'Registrar'), ('confirm', 'Confirmar')):
            matches = [(box, score) for box, text, score in sample['rows'] if str(text).strip() == label]
            if len(matches) == 1 and .95 <= matches[0][1] <= 1:
                box, score = matches[0]
                x = (min(p[0] for p in box)+max(p[0] for p in box))/2
                y = (min(p[1] for p in box)+max(p[1] for p in box))/2
                sample['buttons'][action] = [x+sample['origin'][0], y+sample['origin'][1]]
        self.current = self.save(sample)
        return self.current

    def apply_step(self, action, revision, token=None):
        sample = self.current
        self.current = None
        self.last_error = None
        point = None
        applied = False
        if (self.page.url != 'about:blank' or sample is None or sample['revision'] != revision
                or action not in ('open_modal', 'confirm')):
            self.last_error = 'observation_replaced_or_consumed'
        elif action not in sample['buttons']:
            self.last_error = 'button_missing_or_ambiguous'
        else:
            _, image, origin, ratios = self.pixels()
            if (list(image.shape) != sample['shape'] or list(origin) != sample['origin']
                    or list(ratios) != sample['viewport_scale']
                    or hashlib.sha256(image.tobytes()).hexdigest() != sample['pixels_sha256']):
                self.last_error = 'image_changed_before_click'
            elif not 0 <= monotonic()-sample['observed'] <= 5:
                self.last_error = 'expired_coordinates'
            else:
                point = [v/r for v, r in zip(sample['buttons'][action], ratios)]
                applied = self.page.evaluate('value=>applyFlowAt(value)', dict(action=action, point=point,
                    revision=sample['lab_revision'], token=token))
                if not applied:
                    self.last_error = 'fixture_rejected_click'
        with (self.output/'flow-clicks.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(action=action,point=point,applied=applied,reason=self.last_error))+'\n')
        return applied
