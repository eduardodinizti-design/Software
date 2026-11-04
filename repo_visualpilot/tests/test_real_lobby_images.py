"""OCR regression on original PNGs supplied in imagens.rar, without OS actions."""
import hashlib
import json
from pathlib import Path
import unittest

import numpy as np
from PIL import Image

from visualpilot.lab.pppoker_lobby_reference import (
    annotated_crops, recognize_reference_field, lobby_card, compare_details, compare_modal, name_key)
from visualpilot.pppoker.replay.reader import ReplayReader

ROOT=Path(__file__).resolve().parents[1]


class RealLobbyImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile=json.loads((ROOT/'docs/lab-lobby-real/uploaded-reference.json').read_text())
        cls.source=json.loads((ROOT/'tests/fixtures/lobby_real/source.json').read_text())
        reader=ReplayReader();cls.samples={}
        for view in ('lobby','details','modal'):
            path=ROOT/'tests/fixtures/lobby_real'/f'{view}.png'
            if hashlib.sha256(path.read_bytes()).hexdigest()!=cls.source['files'][view]['sha256']:
                raise AssertionError('Original PNG changed: '+view)
            with Image.open(path) as image:rgb=np.asarray(image.convert('RGB'))
            cls.samples[view]=[]
            for crop in annotated_crops(rgb,cls.profile['views'][view]):
                rows={name:recognize_reference_field(reader,pixels,name)[0] for name,pixels in crop['fields'].items()}
                cls.samples[view].append(dict(crop,fields=rows))

    def test_only_corujao_is_candidate_for_inspection(self):
        readings=[lobby_card(c['fields'],complete=c['complete']) for c in self.samples['lobby']]
        self.assertEqual([i for i,r in enumerate(readings) if r['can_inspect_details']],[2])
        self.assertEqual(name_key(readings[2]['name']),'CORUJAOHYPERPKO10K')
        self.assertEqual(readings[2]['buyin'],'50.00')
        self.assertEqual(readings[2]['start'],'10/31 22:00')
        self.assertEqual(readings[1]['reason'],'buyin_limit')
        self.assertEqual(readings[1]['buyin'],'200.00')
        for index in (0,3,4):self.assertIsNone(readings[index]['buyin'])

    def test_real_details_and_modal_values_match_without_registration_authority(self):
        selection=lobby_card(self.samples['lobby'][2]['fields'])
        detail=compare_details(selection,self.samples['details'][0]['fields'])
        modal=compare_modal(detail,self.samples['modal'][0]['fields'])
        self.assertTrue(detail['matches'],detail)
        self.assertTrue(modal['matches'],modal)
        self.assertEqual(detail['initial_stack'],20000)
        self.assertTrue(detail['register_text_visible'])
        self.assertTrue(modal['confirm_text_visible'])
        self.assertFalse(modal['adjustable_amount'])
        for result in (selection,detail,modal):self.assertFalse(result['can_register'])

    def test_regions_are_native_image_coordinates_not_desktop_positions(self):
        self.assertEqual(self.samples['lobby'][2]['image_point'],[405.0,992.0])
        self.assertEqual(len(self.samples['lobby']),5)
        self.assertFalse(self.profile['automatic_segmentation'])
        with self.assertRaises(ValueError):
            annotated_crops(np.zeros((1115,623,3),np.uint8),self.profile['views']['lobby'])


if __name__=='__main__':unittest.main()
