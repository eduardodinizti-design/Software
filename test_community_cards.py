import os,json,unittest
from pathlib import Path
import cv2
import numpy as np
from table_reading.community_cards import read_board

class BoardTests(unittest.TestCase):
    def scene(self,n):
        image=np.full((1000,600,3),(160,65,30),np.uint8)
        for i in range(n):cv2.rectangle(image,(120+68*i,380),(179+68*i,469),(30,160,30),-1)
        return image
    def read(self,n,ranks,**kw):
        ranks=iter(ranks)
        return read_board(self.scene(n),_rank=lambda _:dict(rank=next(ranks)),_suit=lambda _:dict(suit='c'),**kw)
    def test_streets(self):
        for n,street in [(3,'FLOP'),(4,'TURN'),(5,'RIVER')]:
            result=self.read(n,list('A2345')[:n]);self.assertEqual(result['street'],street)
    def test_no_cards_does_not_claim_preflop(self):
        self.assertIsNone(self.read(0,[])['street'])
    def test_partial_rows_rejected(self):
        for n in [1,2]:self.assertEqual(self.read(n,[])['status'],'BOARD_NOT_CONFIRMED')
    def test_unknown_rank_not_a_partial_valid_board(self):
        self.assertEqual(self.read(3,['A',None,'3'])['status'],'BOARD_INCOMPLETE')
    def test_duplicate_and_hero_conflict(self):
        self.assertEqual(self.read(3,['A','A','3'])['status'],'BOARD_DUPLICATE_REJECTED')
        self.assertEqual(self.read(3,['A','2','3'],hero_cards=['Ac','Kh'])['status'],'BOARD_DUPLICATE_REJECTED')
    def test_development_empty_screens(self):
        root=Path(os.environ.get('VISUALPILOT_ASSETS','public/assets/aistudio'))
        rows=json.loads(Path('docs/table-reading/development-labels.json').read_text())['tables']
        for row in rows[:7]:
            im=cv2.imread(str(root/row['source']));x,y,w,h=row['box']
            def forbidden(_):self.fail('Empty board sent to OCR')
            result=read_board(im[y:y+h,x:x+w],_rank=forbidden)
            self.assertEqual(result['cards'],[])
