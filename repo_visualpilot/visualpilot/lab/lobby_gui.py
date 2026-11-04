"""PNG/OCR adapter for the isolated lobby fixture, without OS input."""
import hashlib
import json
from pathlib import Path
from time import monotonic

import cv2

from .registration_gui import RegistrationGUI
from .lobby import parse_card, segment_cards


class LobbyGUI(RegistrationGUI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page.set_content(Path(__file__).with_name('lobby_simulator.html').read_text())

    def read_rows(self, image):
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        rows = self.reader.detect(rgb)
        original = list(rows)
        for i, (box, text, score) in enumerate(rows):
            if score >= .95: continue
            x=max(0,int(min(p[0] for p in box))-4); y=max(0,int(min(p[1] for p in box))-4)
            right=min(rgb.shape[1],int(max(p[0] for p in box))+5)
            bottom=min(rgb.shape[0],int(max(p[1] for p in box))+5)
            repeated, confidence = self.reader.field(rgb[y:bottom,x:right])
            if ''.join(repeated.split()) == ''.join(str(text).split()) and confidence > score:
                rows[i]=(box,repeated,confidence)
        return rows, original

    def snapshot(self, kind):
        self.current = None
        state = self.sync_control()
        observed = monotonic()
        raw,image,origin,ratios = self.pixels()
        self.sequence += 1
        name = f'{kind}-{self.sequence:03d}.png'
        (self.output/name).write_bytes(raw)
        sample=dict(source='laboratory',observed=observed,image=name,revision=[state['revision'],self.sequence],
                    lab_revision=state['revision'],origin=list(origin),shape=list(image.shape),viewport_scale=list(ratios),
                    pixels_sha256=hashlib.sha256(image.tobytes()).hexdigest(),kind=kind)
        return image, sample

    def save(self, sample):
        # Keep evidence and ledger payloads serializable without NumPy scalars.
        encoded = json.dumps(sample,ensure_ascii=False,default=float)
        with (self.output/'observations.jsonl').open('a') as stream: stream.write(encoded+'\n')
        return json.loads(encoded)

    def capture_lobby(self):
        image,sample = self.snapshot('lobby')
        cards=[]
        for index, geometry in enumerate(segment_cards(image,tuple(sample['origin']))):
            x,y,width,height=geometry['local_box']
            crop=image[y:y+height,x:x+width]
            name=f'card-{self.sequence:03d}-{index:02d}.png'
            cv2.imwrite(str(self.output/name),crop)
            rows,original=self.read_rows(crop)
            cards.append(dict(parse_card(rows),**geometry,rows=rows,original_rows=original,image=name))
        sample['cards']=cards
        self.current=self.save(sample)
        return self.current

    def capture_details(self):
        image,sample=self.snapshot('details')
        sample['rows'],sample['original_rows']=self.read_rows(image)
        return self.save(sample)

    def open_card(self, selection, revision):
        sample=self.current; self.current=None; self.last_error=None
        if self.page.url!='about:blank' or sample is None or sample['revision']!=revision:
            self.last_error='observation_replaced_or_unknown_card';return False
        keys=('tournament','name','buyin','kind','registration','stack','start_time','box','point','readable')
        if not any(all(selection.get(k)==card.get(k) for k in keys) for card in sample['cards']):
            self.last_error='observation_replaced_or_unknown_card';return False
        _,image,origin,ratios=self.pixels()
        if (list(origin)!=sample['origin'] or list(image.shape)!=sample['shape'] or list(ratios)!=sample['viewport_scale']
                or hashlib.sha256(image.tobytes()).hexdigest()!=sample['pixels_sha256']):
            self.last_error='lobby_changed_before_click'
        elif not 0<=monotonic()-sample['observed']<=5:
            self.last_error='expired_lobby'
        point=[v/ratio for v,ratio in zip(selection['point'],sample['viewport_scale'])]
        applied=False
        if self.last_error is None:
            applied=self.page.evaluate('value=>openLabCardAt(value)',dict(point=point,
                revision=sample['lab_revision'],id=selection['tournament']))
            if not applied:self.last_error='fixture_rejected_click'
        with (self.output/'clicks.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(tournament=selection['tournament'],point=point,applied=applied,
                                         reason=self.last_error,image=sample['image']))+'\n')
        return applied
