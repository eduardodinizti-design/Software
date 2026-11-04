import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from visualpilot.pppoker.discovery import detect_tables, table_anchor_visible

class DiscoveryTests(unittest.TestCase):
    def read(self,name):
        with Image.open(Path(__file__).parent/'fixtures'/name) as im:
            return np.array(im.convert('RGB'))
    def test_one_table_without_nested_false_detection(self):
        found=detect_tables(self.read('table_one.png'))
        self.assertEqual(len(found),1)
        x,y,w,h=found[0]['box']
        self.assertLess(abs(x-140),25)
        self.assertLess(abs(w-540),25)
    def test_two_tables(self):
        found=detect_tables(self.read('table_two.png'))
        self.assertEqual(len(found),2)
        self.assertGreater(found[1]['box'][0],found[0]['box'][0]+100)
    def test_login_is_not_table(self):
        self.assertEqual(detect_tables(self.read('no_table.png')),[])
    def test_blank_desktop(self):
        self.assertEqual(detect_tables(np.zeros((1080,1920,3),dtype=np.uint8)),[])

    def test_visual_capture_guard_rejects_disappeared_table(self):
        rgb = self.read('table_one.png')
        x, y, w, h = detect_tables(rgb)[0]['box']
        self.assertTrue(table_anchor_visible(rgb[y:y+h, x:x+w]))
        self.assertFalse(table_anchor_visible(np.zeros((h, w, 3), dtype=np.uint8)))
        self.assertFalse(table_anchor_visible(None))
        self.assertFalse(table_anchor_visible(np.zeros((10, 10, 3), dtype=np.uint8)))

    def test_eight_copies_of_real_table(self):
        source = Image.fromarray(self.read('table_one.png'))
        x, y, w, h = detect_tables(np.array(source))[0]['box']
        table = source.crop((x, y, x+w, y+h))
        table.thumbnail((280, 500))
        canvas = Image.new('RGB', (table.width*4, table.height*2))
        for i in range(8):
            canvas.paste(table, ((i%4)*table.width, (i//4)*table.height))
        self.assertEqual(len(detect_tables(np.array(canvas))), 8)


    def test_twelve_copies_on_one_monitor(self):
        source=Image.fromarray(self.read('table_one.png'))
        x,y,w,h=detect_tables(np.array(source))[0]['box']
        table=source.crop((x,y,x+w,y+h));table.thumbnail((280,500))
        canvas=Image.new('RGB',(table.width*4,table.height*3))
        for i in range(12):canvas.paste(table,((i%4)*table.width,(i//4)*table.height))
        self.assertEqual(len(detect_tables(np.array(canvas))),12)


class ReferenceLoadingTests(unittest.TestCase):
    def test_unicode_path(self):
        import tempfile
        from visualpilot.pppoker.discovery import load_reference
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'Área de trabalho João 日本'
            path.mkdir()
            target=path/'referência.png'
            Image.fromarray(load_reference()).save(target)
            np.testing.assert_array_equal(load_reference(target),load_reference())

    def test_missing_empty_corrupt_and_wrong_size(self):
        import tempfile
        from visualpilot.pppoker.discovery import load_reference
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'ppp_chat.png'
            with self.assertRaisesRegex(ValueError,'abrir a referência'): load_reference(path)
            path.write_bytes(b'')
            with self.assertRaisesRegex(ValueError,'vazia'): load_reference(path)
            path.write_bytes(b'not an image')
            with self.assertRaisesRegex(ValueError,'inválida|corrompida'): load_reference(path)
            Image.new('RGB',(10,10)).save(path)
            with self.assertRaisesRegex(ValueError,'90'): load_reference(path)

    def test_invalid_capture(self):
        for image in (None,np.zeros((0,10,3),dtype=np.uint8),np.zeros((10,10),dtype=np.uint8)):
            with self.assertRaisesRegex(ValueError,'captura'): detect_tables(image)
