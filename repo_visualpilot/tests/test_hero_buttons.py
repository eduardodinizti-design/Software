import unittest
from pathlib import Path
import cv2
import numpy as np
from visualpilot.pppoker.observer.buttons import parse_button
from visualpilot.pppoker.observer.perception import CachedReader,read_table
from visualpilot.pppoker.replay.reader import ReplayReader
from visualpilot.pppoker.observer.validation import validate_latest

class HeroButtonTests(unittest.TestCase):
    def test_changed_button_invalidates_structured_amount(self):
        before=np.zeros((100,100,3),np.uint8)
        after=before.copy();after[90:100]=255
        reading=dict(actions=['Call 2 BB'],hero_buttons=[dict(action='call',amount=2)],
            evidence_size=[100,100],evidence=dict(actions=[[0,90,100,10]]))
        result=validate_latest(reading,before,after)
        self.assertEqual(result['hero_buttons'],[])
        self.assertEqual(result['actions'],[])

    def test_real_call_amount_and_player_action_separation(self):
        reader=CachedReader(ReplayReader())
        path=Path(__file__).parent/'fixtures/actions/right_99.png'
        reading=read_table(reader,cv2.cvtColor(cv2.imread(str(path)),cv2.COLOR_BGR2RGB))
        buttons=reading['hero_buttons']
        self.assertEqual([b['action'] for b in buttons],['fold','call','raise'])
        self.assertEqual(buttons[1]['amount'],2.5)
        self.assertEqual(buttons[1]['unit'],'BB')
        self.assertTrue(all(b['box'] for b in buttons))
        self.assertEqual(len(reading['observed_actions']),5)

    def test_all_five_labels_with_real_ocr_on_synthetic_text(self):
        reader=ReplayReader()
        for label,action,amount in [('Fold','fold',None),('Check','check',None),('Call 2.5 BB','call',2.5),('Bet 4 BB','bet',4.),('Raise 10 BB','raise',10.)]:
            image=np.full((90,420,3),240,np.uint8)
            cv2.putText(image,label,(15,58),cv2.FONT_HERSHEY_SIMPLEX,1.2,(10,10,10),2,cv2.LINE_AA)
            # field() receives a localized text crop, not an entire button row.
            x,y,w,h=cv2.boundingRect((image.min(2)<100).astype('uint8'))
            text,score=reader.field(image[y-3:y+h+3,x-3:x+w+3])
            with self.subTest(label=label):
                button=parse_button(text,score,[0,0,420,90])
                self.assertIsNotNone(button,(text,score))
                self.assertEqual(button['action'],action)
                self.assertEqual(button['amount'],amount)

    def test_illegible_or_ambiguous_amount_is_not_invented(self):
        for text in ('Call ? BB','Raise 1,2.3 BB'):
            self.assertIsNone(parse_button(text,.99,[])['amount'])
        self.assertIsNone(parse_button('Call 3 BB',.4,[]))
        self.assertIsNone(parse_button('Calling',.99,[]))
