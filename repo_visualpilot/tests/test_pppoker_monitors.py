import threading
import unittest
import numpy as np
from pathlib import Path
from PIL import Image
from visualpilot.pppoker.core import Region
from visualpilot.pppoker.discovery import scan_monitors

class MultiMonitorTests(unittest.TestCase):
    def run_scan(self,fail_first=False,found_first=False):
        visits=[]
        class Capture:
            def monitors(self): return [Region(0,0,100,100),Region(-200,40,200,100)]
            def grab(self,region):
                visits.append(region.left)
                if fail_first and region.left==0: raise OSError('Falha simulada')
                return np.full((2,2,3),1 if region.left==0 else 2,dtype=np.uint8)
        def detector(rgb,diagnostics):
            diagnostics['best_match']=.95
            return [] if rgb[0,0,0]==1 and not found_first else [{'box':[10,20,30,40],'score':.95}]
        reports,found=scan_monitors(Capture(),threading.Event(),detector)
        return visits,reports,found
    def test_no_table_first_visits_second_and_translates_coordinates(self):
        visits,reports,found=self.run_scan()
        self.assertEqual(visits,[0,-200])
        self.assertEqual([r['tables'] for r in reports],[0,1])
        self.assertEqual(found[0]['box'],[-190,60,30,40])
    def test_first_failure_does_not_abort_second(self):
        visits,reports,found=self.run_scan(fail_first=True)
        self.assertEqual(visits,[0,-200]);self.assertEqual(reports[0]['state'],'error')
        self.assertEqual(found[0]['monitor'],2)
    def test_both_displays_even_when_first_has_table(self):
        _,reports,found=self.run_scan(found_first=True)
        self.assertEqual(len(found),2)
    def test_stop_prevents_capture(self):
        stop=threading.Event();stop.set()
        class Capture:
            def monitors(self): return [Region(0,0,100,100)]
            def grab(self,r): raise AssertionError('Não deveria capturar')
        self.assertEqual(scan_monitors(Capture(),stop),([],[]))

    def test_three_real_tables_on_each_of_two_monitors(self):
        root=Path(__file__).parent/'fixtures/actions'
        sources=[Image.open(root/name).convert('RGB') for name in ('left_99.png','right_99.png')]
        width,height=sources[0].size
        monitors=[]
        for offset in (0,1):
            canvas=Image.new('RGB',(width*3,height))
            for column in range(3):
                canvas.paste(sources[(column+offset)%2],(column*width,0))
            monitors.append(np.array(canvas))
        regions=[Region(0,0,width*3,height),Region(-width*3,0,width*3,height)]
        class Capture:
            def monitors(self):return regions
            def grab(self,region):return monitors[regions.index(region)].copy()
        reports,found=scan_monitors(Capture(),threading.Event())
        self.assertEqual([report['tables'] for report in reports],[3,3])
        self.assertEqual(len(found),6)
        self.assertEqual({item['monitor'] for item in found},{1,2})
        self.assertTrue(all(item['box'][0]>=0 for item in found if item['monitor']==1))
        self.assertTrue(all(item['box'][0]<0 for item in found if item['monitor']==2))
