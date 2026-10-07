import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import requests
from PIL import Image
import server
import image_quality
from local_sort import LocalSorter, LocalSortError


class OriginalImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(server, 'DATA', self.root), patch.object(server, 'DOWNLOAD', self.root)]
        for patcher in self.patches:
            patcher.start()
        server.initialize_database()

    def tearDown(self):
        for patcher in self.patches:
            patcher.stop()
        self.temp.cleanup()

    def test_jpeg_is_served_byte_for_byte_with_native_dimensions(self):
        path = self.root/'original.jpg'
        Image.new('RGB', (2400, 1600), (105, 45, 190)).save(path, 'JPEG', quality=97)
        original = path.read_bytes()
        server.add_media(path, 'native-jpeg', 'My original photo')
        with server.database() as db:
            row = db.execute('SELECT * FROM media').fetchone()
            self.assertEqual(row['preview'], 'original.jpg')
            info = db.execute('SELECT * FROM image_info').fetchone()
            self.assertEqual((info['width'],info['height']), (2400,1600))
            self.assertEqual(info['orientation'], 'landscape')
            self.assertEqual(info['original_sha256'], hashlib.sha256(original).hexdigest())
        http = server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread = threading.Thread(target=http.serve_forever,daemon=True)
        thread.start()
        try:
            response = requests.get(f'http://127.0.0.1:{http.server_port}/Download/original.jpg')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.content,original)
            self.assertEqual(response.headers['Content-Type'],'image/jpeg')
            public=requests.get(f'http://127.0.0.1:{http.server_port}/api/media').json()['media'][0]
            self.assertEqual((public['width'],public['height']), (2400,1600))
        finally:
            http.shutdown();http.server_close();thread.join()

    def test_exif_rotation_reports_display_dimensions_without_reencoding(self):
        path=self.root/'rotated.jpg'
        image=Image.new('RGB',(120,240),'purple')
        exif=Image.Exif();exif[274]=6
        image.save(path,'JPEG',exif=exif)
        original=path.read_bytes()
        info=image_quality.inspect(path)
        self.assertEqual((info['width'],info['height']),(240,120))
        self.assertEqual(info['orientation'],'landscape')
        self.assertEqual(path.read_bytes(),original)

    def test_transparent_png_and_animated_gif_keep_original_bytes(self):
        png=self.root/'alpha.png';Image.new('RGBA',(180,420),(180,20,230,70)).save(png)
        gif=self.root/'moving.gif';Image.new('RGB',(150,150),'purple').save(gif,save_all=True,append_images=[Image.new('RGB',(150,150),'white')],duration=120,loop=0)
        for path,shape in [(png,'portrait'),(gif,'square')]:
            original=path.read_bytes();info=image_quality.inspect(path)
            self.assertEqual(info['display_filename'],path.name)
            self.assertEqual(info['orientation'],shape)
            self.assertEqual(path.read_bytes(),original)
        with Image.open(gif) as image:
            self.assertEqual(image.n_frames,2)

    def test_existing_lossy_preview_is_replaced_by_original_not_overwritten(self):
        original=self.root/'old.jpg';Image.new('RGB',(1900,1100),'purple').save(original,quality=95)
        preview=self.root/'old.preview.jpg';Image.new('RGB',(100,100),'purple').save(preview,quality=10)
        contents=original.read_bytes()
        with server.database() as db:
            db.execute('INSERT INTO media VALUES (?,?,?,?,?,?,?,?,?)',('old','old.jpg','old.preview.jpg','image','Old photo','all','telegram','',0))
            self.assertEqual(image_quality.migrate(db,self.root),1)
            self.assertEqual(image_quality.migrate(db,self.root),0)
            self.assertEqual(db.execute('SELECT preview FROM media').fetchone()[0],'old.jpg')
        self.assertEqual(original.read_bytes(),contents)
        self.assertTrue(preview.exists())

    def test_tiff_fallback_is_full_size_and_lossless(self):
        original=self.root/'photo.tiff';image=Image.new('RGB',(180,360),(100,50,150));image.save(original)
        info=image_quality.inspect(original)
        self.assertEqual((info['width'],info['height']),(180,360))
        self.assertEqual(info['display_filename'],'photo.display.png')
        with Image.open(self.root/info['display_filename']) as display:
            self.assertEqual(display.size,image.size)
            self.assertEqual(display.tobytes(),image.tobytes())


class LocalMatchingTests(unittest.TestCase):
    def test_confident_matching_and_ambiguous_faces(self):
        references=[{'member':'v','embedding':[1,0,0]},{'member':'jimin','embedding':[.8,.6,0]}]
        self.assertEqual(LocalSorter.choose([1,0,0],references)[0],'v')
        self.assertIsNone(LocalSorter.choose([.95,.312,0],references)[0])
        self.assertIsNone(LocalSorter.choose([0,0,1],references)[0])
        self.assertIsNone(LocalSorter.choose([1,0,0],[{'member':'unknown','embedding':[1,0,0]}])[0])

    def test_learning_rejects_multi_face_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            engine=LocalSorter(directory)
            with patch.object(engine,'request',return_value={'detected':2,'faces':[{},{}]}):
                with self.assertRaisesRegex(LocalSortError,'exactly one'):
                    engine.add_reference(Path(directory)/'unused.jpg','v','reference')
            self.assertFalse(engine.reference_path.exists())


if __name__=='__main__':
    unittest.main()
