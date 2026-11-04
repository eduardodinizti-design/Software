import unittest
import numpy as np
from visualpilot.pppoker.observer.bounties import read_pko_bounties,SEATS
from visualpilot.pppoker.observer.validation import validate_latest


def row(x,y,text,score=.99):
    return ([[x-15,y-5],[x+15,y-5],[x+15,y+5],[x-15,y+5]],text,score)


def fixture_rows():
    # Manual transcription of user screenshot, not output of OCR on the original raster.
    values=[('PPODRE...',27.5,72),('mateusbit',35.1,204),('Azulma',19.4,324),
            ('atzedes ed...',22.2,168),('sacatrapoo',39.6,240),('Tainah790',23.9,72),
            ('Nantes.23',67.7,372),('Just do it',33.8,72)]
    rows=[row(270,550,'EVOLUTION PKO')]
    for (seat,(cx,cy)),(name,stack,bounty) in zip(SEATS.items(),values):
        rows.extend([row(cx*544,cy*1021,name),row(cx*544,(cy+.024)*1021,f'{stack} BB'),
                     row(cx*544,(cy-.094)*1021,str(bounty))])
    return rows


class BountyObservationTests(unittest.TestCase):
    def test_sample_association_and_coverage(self):
        result=read_pko_bounties(fixture_rows(),544,1021)
        seats={s['seat_id']:s for s in result['seats']}
        self.assertEqual(seats['right_upper']['bounty_display_value'],324)
        self.assertTrue(seats['right_upper']['hero_covers'])
        self.assertEqual(seats['right_lower']['bounty_display_value'],372)
        self.assertFalse(seats['right_lower']['hero_covers'])
        self.assertFalse(result['usable_for_strategy'])
        self.assertTrue(all(s['status']=='observed_candidate' for s in seats.values()))

    def test_ambiguous_or_absent_bounty_is_not_zero(self):
        rows=fixture_rows();rows.pop()
        result=read_pko_bounties(rows,544,1021)
        self.assertIsNone(result['seats'][-1]['bounty_display_value'])
        rows=fixture_rows();rows.append(rows[-1])
        self.assertIsNone(read_pko_bounties(rows,544,1021)['seats'][-1]['bounty_display_value'])
        self.assertEqual(read_pko_bounties(rows[1:],544,1021)['status'],'unknown')

    def test_stale_pko_cleared_without_clearing_unchanged_cards(self):
        before=np.zeros((100,100,3),dtype=np.uint8);after=before.copy();after[10:20,10:20]=255
        reading=dict(hero=['As','Kd'],pko={'seats':[1]},evidence_size=[100,100],evidence={'pko':[[10,10,10,10]]})
        result=validate_latest(reading,before,after)
        self.assertEqual(result['pko']['seats'],[]);self.assertEqual(result['hero'],['As','Kd'])
        resized=validate_latest(reading,before,np.zeros((200,100,3),dtype=np.uint8))
        self.assertEqual(resized['pko']['seats'],[])
