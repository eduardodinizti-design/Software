"""Passive Win32 capture to HU scenes. This file never sends input.

Screen coordinates derive exclusively from physical CLIENT pixels. Process
creation time is part of table identity, preventing HWND reuse after restart.
"""
import time
import uuid

import cv2

from table_reading.automatic_table_crops import detect_table_crops
from table_reading.action_buttons import read_action_buttons
from table_reading.hand_tracking import read_hand_id
from table_reading.community_cards import read_board
from table_reading.ocr_runtime import ocr_frame
from table_advisor import advise_table, read_hero_card_slots, _pair_from_slots
from raise_panel import read_raise_panel, read_selected_amount
from grade_reader import find_buyin_badges
from strategy.state_contract import StrategyError


def table_identity(meta, crop_key):
    required = ('hwnd','pid','process_created','client_rect','screen_origin')
    if any(meta.get(k) is None for k in required):
        raise StrategyError('HU_CAPTURE_PROCESS_IDENTITY_MISSING')
    if meta.get('status')!='SUCCESS' or meta.get('dpi_effective') is not True:
        raise StrategyError('HU_PHYSICAL_CLIENT_CAPTURE_NOT_CONFIRMED')
    return '%x:%s:%s:%s' % (meta['hwnd'],meta['pid'],meta['process_created'],crop_key)


def scene_from_result(result, buttons, meta, crop_box, table_key, sample_id, captured_at):
    table_identity(meta, table_key)  # validate; table_key already globally names the producer
    return dict(result=result, buttons=buttons, hwnd=meta['hwnd'], sample_id=str(sample_id),
                captured_at=captured_at, source_key=table_key,
                window_signature=(meta['hwnd'],meta['pid'],meta['process_created'],
                                  tuple(meta['client_rect']),tuple(meta['screen_origin']),tuple(crop_box)),
                screen_origin=tuple(meta['screen_origin']),crop_box=tuple(crop_box),
                phase='normal',source_kind='PPPOKER_WINDOWS',
                cards_fresh=_pair_from_slots(result.get('hero_slots') or ()) is not None,
                board_fresh=bool((result.get('board') or {}).get('cards')))


class LiveHUScenes:
    def __init__(self, *, engine, hwnd, crop_key, advisor, history, policy_observer,
                 profile, stabilizer=None, mode=None, stage=None, max_tables=6):
        self.engine,self.hwnd,self.crop_key = engine,hwnd,crop_key
        self.advisor,self.history,self.observer = advisor,history,policy_observer
        self.profile,self.stabilizer,self.mode,self.stage = profile,stabilizer,mode,stage
        self.max_tables = max_tables
        self.anchor = None

    def bind(self, scene):
        self.anchor = scene
        return self

    @staticmethod
    def local_key(box):
        return '%dx%d' % (int(box[0])//100,int(box[1])//100)

    def __call__(self, *, panel=False):
        at = time.monotonic()
        frame,meta = self.engine.capture_frame(hwnd=self.hwnd)
        if frame is None:
            raise StrategyError('HU_CAPTURE_FAILED:' + str(meta.get('status')))
        if panel and self.anchor:
            # The modal panel can hide the felt detector. Lease only its last
            # physical crop while the process and client geometry remain identical.
            box = self.anchor['crop_box']
            signature = (meta['hwnd'],meta['pid'],meta['process_created'],
                         tuple(meta['client_rect']),tuple(meta['screen_origin']),tuple(box))
            if signature != self.anchor['window_signature']:
                raise StrategyError('HU_PANEL_LEASE_GEOMETRY_CHANGED')
        else:
            crops = detect_table_crops(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB),max_tables=self.max_tables)
            if self.crop_key=='auto':
                matches=[]
                for p in crops:
                    px,py,pw,ph=map(int,p.box)
                    if not find_buyin_badges(frame[py:py+ph,px:px+pw]):matches.append(p)
            else:
                matches = [p for p in crops if self.local_key(p.box)==self.crop_key]
            if len(matches)!=1:
                raise StrategyError('HU_TABLE_CROP_MISSING_OR_AMBIGUOUS:' + ','.join(self.local_key(p.box) for p in matches))
            box = tuple(map(int,matches[0].box))
            if self.crop_key=='auto':self.crop_key=self.local_key(box)
        x,y,w,h = box
        crop = frame[y:y+h,x:x+w]
        if find_buyin_badges(crop):
            raise StrategyError('HU_LOBBY_IS_NOT_A_TABLE')
        table_id = table_identity(meta,self.crop_key)
        sample_id = uuid.uuid4().hex
        with ocr_frame():
            buttons = read_action_buttons(crop)
            if panel:
                slots = read_hero_card_slots(crop)
                hero = _pair_from_slots(slots)
                result = dict(hand=read_hand_id(crop),hero_cards=hero,hero_slots=slots,
                              board=read_board(crop,hero_cards=hero or [None,None]))
            else:
                result = advise_table(crop,self.advisor,mode=self.mode,stage=self.stage,
                    stabilizer=self.stabilizer,table_key=table_id,history=self.history,
                    buttons_result=buttons,sample_id=sample_id,captured_at=at,
                    observation_source='PPPOKER_WINDOWS_PHYSICAL_CLIENT_CAPTURE',
                    postflop_policy=self.observer,
                    observation_only=buttons.get('status')!='EXPERIMENTAL_BUTTON_ROW')
            scene = scene_from_result(result,buttons,meta,box,table_id,sample_id,at)
            if panel:
                scene['phase'] = 'panel'
                scene['panel'] = read_raise_panel(crop)
                if scene['panel'].get('confirm'):
                    scene['panel']['selected'] = read_selected_amount(crop,amount_box=self.profile.amount_box)
        return scene
