import gzip
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image
import server


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(server, 'DATA', self.root), patch.object(server, 'DOWNLOAD', self.root)]
        for item in self.patches:
            item.start()
        server.initialize_database()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.temp.cleanup()

    def message(self):
        return {'from': {'id': server.OWNER}, 'chat': {'id': server.OWNER, 'type': 'private'}, 'photo': [{'file_id': 'test', 'file_unique_id': 'unique-test', 'file_size': 100}], 'caption': 'My memory #v'}

    def test_generated_captions_are_individual_and_custom_titles_survive_migration(self):
        existing = set()
        for index in range(150):
            title = server.captions.unique_caption('image-' + str(index), existing)
            self.assertNotIn(title, existing)
            self.assertFalse(server.captions.is_generic(title))
            existing.add(title)
        with server.database() as db:
            for identity, title in [('old-1', 'A little purple memory'), ('old-2', 'A little purple memory'), ('mine', 'My own caption, exactly as written')]:
                db.execute('INSERT INTO media VALUES (?,?,?,?,?,?,?,?,?)', (identity, identity+'.jpg', identity+'.jpg', 'image', title, 'all', 'telegram', '', 0))
            self.assertEqual(server.captions.migrate(db), 2)
            self.assertEqual(server.captions.migrate(db), 0)
            titles = {row['id']: row['title'] for row in db.execute('SELECT id,title FROM media')}
            self.assertNotEqual(titles['old-1'], titles['old-2'])
            self.assertEqual(titles['mine'], 'My own caption, exactly as written')

    def test_new_uncaptioned_upload_gets_stable_generated_title(self):
        image = self.root / 'blank.jpg'
        Image.new('RGB', (20, 20), 'purple').save(image)
        server.add_media(image, 'new-caption-test', 'A little purple memory')
        with server.database() as db:
            first = db.execute('SELECT title FROM media').fetchone()[0]
        self.assertFalse(server.captions.is_generic(first))
        server.add_media(image, 'new-caption-test', 'A little purple memory')
        with server.database() as db:
            self.assertEqual(db.execute('SELECT title FROM media').fetchone()[0], first)

    @patch.object(server, 'telegram')
    def test_rejects_other_users_and_group_messages(self, api):
        message = self.message()
        message['from']['id'] = -1
        server.ingest(message)
        message = self.message()
        message['chat']['type'] = 'group'
        server.ingest(message)
        api.assert_not_called()

    @patch.object(server, 'reply')
    @patch.object(server, 'telegram')
    def test_large_files_get_clear_feedback_without_download(self, api, reply):
        message = self.message()
        message['photo'][0]['file_size'] = 21 * 1024 * 1024
        server.ingest(message)
        api.assert_not_called()
        self.assertIn('20 MB', reply.call_args.args[1])

    @patch.object(server, 'reply')
    @patch.object(server.requests, 'get')
    @patch.object(server, 'telegram', return_value={'file_path': 'photos/file.jpg'})
    def test_photo_download_tag_preview_and_deduplication(self, api, get, reply):
        data = io.BytesIO()
        Image.new('RGB', (1800, 1000), 'purple').save(data, 'JPEG')
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_content.return_value = [data.getvalue()]
        get.return_value = response
        server.ingest(self.message())
        with server.database() as db:
            row = dict(db.execute('SELECT * FROM media').fetchone())
        self.assertEqual(row['member'], 'v')
        self.assertEqual(row['kind'], 'image')
        self.assertEqual((self.root / row['filename']).read_bytes(), data.getvalue())
        self.assertEqual(row['preview'], row['filename'])
        with Image.open(self.root / row['preview']) as preview:
            self.assertEqual(preview.width, 1800)
        server.ingest(self.message())
        get.assert_called_once()
        self.assertIn('Already saved', reply.call_args.args[1])

    def test_vector_animated_sticker_and_unknown_file_fallback(self):
        sticker = self.root / 'sticker.tgs'
        animation = {'v': '5.5', 'assets': [{'id': 'comp_1', 'layers': []}], 'layers': [], 'w': 512, 'h': 512, 'fr': 30, 'ip': 0, 'op': 60}
        with gzip.open(sticker, 'wt') as stream:
            json.dump(animation, stream)
        server.add_media(sticker, 'sticker-test', 'Sticker')
        document = self.root / 'document.xyz'
        document.write_bytes(b'unknown format')
        server.add_media(document, 'document-test', 'Document')
        with server.database() as db:
            rows = {row['id']: dict(row) for row in db.execute('SELECT * FROM media')}
        self.assertEqual(rows['sticker-test']['kind'], 'sticker')
        self.assertEqual(rows['document-test']['kind'], 'file')
        self.assertTrue((self.root / rows['sticker-test']['preview']).exists())

    def test_auto_routing_aliases_multiple_members_and_album_inheritance(self):
        self.assertEqual(server.route_member('Jimin at an event'), 'jimin')
        self.assertEqual(server.route_member('kim_taehyung_photo.jpg'), 'v')
        self.assertEqual(server.route_member('정국 ♡'), 'jungkook')
        self.assertEqual(server.route_member('Namjoon and Jin #rm #jin', 'album1'), 'rm,jin')
        self.assertEqual(server.route_member('A little purple memory', 'album1'), 'rm,jin')
        self.assertEqual(server.route_member('a lovely video'), 'all')
        server.set_setting('upload_member', 'suga')
        self.assertEqual(server.route_member('unlabelled.jpg'), 'suga')
        server.set_setting('upload_member', 'auto')
        self.assertEqual(server.route_member('unlabelled.jpg'), 'all')

    @patch.object(server, 'telegram', return_value={'message_id': 101})
    @patch.object(server, 'ingest')
    def test_mixed_batch_one_message_edited_with_counts_and_no_duplicate_jobs(self, ingest, api):
        for number, category in enumerate(('photo', 'sticker', 'video')):
            message = self.message()
            if category != 'photo':
                item = message.pop('photo')[0]
                message[category] = item
            update = {'update_id': number + 10, 'message': message}
            server.accept_update(update)
            server.accept_update(update)
        with server.database() as db:
            batches = db.execute('SELECT id FROM batches').fetchall()
            self.assertEqual(len(batches), 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 3)
        batch_id = batches[0]['id']
        server.publish_batch(batch_id, force=True)
        ingest.side_effect = [{'status': 'saved', 'member': 'v'}, {'status': 'duplicate'}, {'status': 'failed', 'detail': '20 MB limit'}]
        for _ in range(3):
            self.assertTrue(server.process_next_job())
        self.assertFalse(server.process_next_job())
        self.assertTrue(all(call.kwargs == {'quiet': True} for call in ingest.call_args_list))
        with server.database() as db:
            db.execute('UPDATE batches SET received=0 WHERE id=?', (batch_id,))
        server.publish_batch(batch_id, force=True)
        methods = [call.args[0] for call in api.call_args_list]
        self.assertEqual(methods, ['sendMessage', 'editMessageText'])
        text = api.call_args.kwargs['text']
        self.assertIn('Received: 3', text)
        self.assertIn('Saved: 1 · Already saved: 1 · Failed: 1', text)
        self.assertIn('1 photo', text)
        self.assertIn('1 sticker', text)
        self.assertIn('1 video', text)
        self.assertTrue(server.batch_snapshot(batch_id)['complete'])

    @patch.object(server, 'telegram')
    def test_other_users_are_silent_for_commands_text_and_media(self, api):
        for text in ('/cmds', '/api key fake-secret', 'hello'):
            message = self.message()
            message['from']['id'] = -1
            message['text'] = text
            server.accept_update({'update_id': 50, 'message': message})
        server.handle_command(-1, '/cmds')
        api.assert_not_called()
        self.assertEqual(server.setting('vision_key'), '')
        with server.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 0)

    @patch.object(server, 'reply')
    def test_api_key_is_preserved_private_and_explicit_opt_in_required(self, reply):
        server.handle_command(server.OWNER, '/api key sk-MixedCaseTEST')
        self.assertEqual(server.setting('vision_key'), 'sk-MixedCaseTEST')
        self.assertEqual(server.setting('vision_enabled', 'off'), 'off')
        server.handle_command(server.OWNER, '/api')
        self.assertNotIn('sk-MixedCaseTEST', reply.call_args.args[1])
        server.handle_command(server.OWNER, '/api on')
        self.assertEqual(server.setting('vision_enabled'), 'on')
        server.handle_command(server.OWNER, '/api clear')
        self.assertEqual(server.setting('vision_key'), '')
        self.assertEqual(server.setting('vision_enabled'), 'off')

    def test_vision_output_accepts_only_known_confident_members(self):
        content = json.dumps({'members': [{'id': 'v', 'confidence': .98}, {'id': 'jimin', 'confidence': .94}, {'id': 'rm', 'confidence': .4}, {'id': 'not-a-member', 'confidence': 1}, {'id': 'v', 'confidence': .99}]})
        self.assertEqual(server.vision.parse_members(content), ['v', 'jimin'])
        self.assertEqual(server.vision.parse_members('{"members": []}'), [])
        with self.assertRaises(server.vision.VisionError):
            server.vision.parse_members('not json')
        self.assertFalse(server.vision.valid_endpoint('http://example.com/v1/chat/completions'))
        self.assertFalse(server.vision.valid_endpoint('https://secret@example.com/chat'))
        self.assertTrue(server.vision.valid_endpoint('https://example.com/v1/chat/completions'))

    @patch.object(server.vision.requests, 'post')
    def test_vision_provider_uses_resized_image_and_private_authorization(self, post):
        image = self.root / 'vision.jpg'
        Image.new('RGB', (1600, 1600), 'purple').save(image)
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {'choices': [{'message': {'content': '{"members":[{"id":"jimin","confidence":0.95}]}'}}]}
        post.return_value = response
        self.assertEqual(server.vision.classify(image, 'private-key'), ['jimin'])
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer private-key')
        self.assertFalse(post.call_args.kwargs['allow_redirects'])
        image_url = post.call_args.kwargs['json']['messages'][0]['content'][1]['image_url']['url']
        self.assertTrue(image_url.startswith('data:image/jpeg;base64,'))
        response.status_code = 401
        with self.assertRaisesRegex(server.vision.VisionError, 'HTTP 401'):
            server.vision.classify(image, 'private-key')

    @patch.object(server, 'classify_media')
    @patch.object(server.requests, 'get')
    @patch.object(server, 'telegram', return_value={'file_path': 'photos/file.jpg'})
    def test_unlabelled_upload_vision_routes_multiple_profiles_and_failure_keeps_file(self, api, get, classify):
        data = io.BytesIO()
        Image.new('RGB', (30, 30), 'purple').save(data, 'JPEG')
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_content.return_value = [data.getvalue()]
        get.return_value = response
        server.set_setting('vision_enabled', 'on')
        server.set_setting('vision_key', 'test-only')
        message = self.message()
        message.pop('caption')
        classify.return_value = ['v', 'jimin']
        result = server.ingest(message, quiet=True)
        self.assertEqual(result['status'], 'saved')
        self.assertEqual(result['member'], 'v,jimin')
        message['photo'][0]['file_unique_id'] = 'another-image'
        classify.side_effect = server.vision.VisionError('Provider unavailable')
        result = server.ingest(message, quiet=True)
        self.assertEqual(result['status'], 'saved')
        self.assertEqual(result['member'], 'all')
        self.assertEqual(result['api_error'], 'Provider unavailable')
        with server.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM media').fetchone()[0], 2)
        self.assertEqual([call.args[0] for call in api.call_args_list], ['getFile', 'getFile'])

    @patch.object(server, 'reply')
    def test_commands_are_owner_only_and_settings_persist(self, reply):
        message = self.message()
        message.pop('photo')
        message['text'] = '/sorry off'
        message['from']['id'] = -1
        server.ingest(message)
        self.assertEqual(server.setting('sorry_enabled', 'on'), 'on')
        message['from']['id'] = server.OWNER
        server.ingest(message)
        self.assertEqual(server.setting('sorry_enabled'), 'off')
        message['text'] = '/sorry on'
        server.ingest(message)
        self.assertEqual(server.setting('sorry_enabled'), 'on')
        message['text'] = '/member jimin'
        server.ingest(message)
        self.assertEqual(server.route_member('file.jpg'), 'jimin')

    @patch.object(server, 'reply')
    def test_visibility_http_metadata_redaction_and_retagging(self, reply):
        original = self.root / 'sample.jpg'
        Image.new('RGB', (20, 20), 'purple').save(original)
        server.add_media(original, 'example', 'A frame', 'v', credit='https://example.org/private-credit')
        http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{http.server_port}'
        try:
            server.handle_command(server.OWNER, '/sorry off')
            self.assertEqual(server.requests.get(base + '/sorry').status_code, 404)
            self.assertEqual(server.requests.get(base + '/api/note').status_code, 404)
            self.assertFalse(server.requests.get(base + '/api/settings').json()['noteEnabled'])
            server.handle_command(server.OWNER, '/sorry on')
            note = server.requests.get(base + '/api/note')
            self.assertEqual(note.status_code, 404)
            self.assertEqual(note.headers['Cache-Control'], 'no-store')
            self.assertEqual(server.requests.get(base + '/sorry').status_code, 200)
            public = server.requests.get(base + '/api/media').json()['media'][0]
            self.assertNotIn('source', public)
            self.assertNotIn('credit', public)
            self.assertEqual(server.requests.get(base + '/api/status').status_code, 404)
            server.handle_command(server.OWNER, '/tag latest rm,jimin')
            public = server.requests.get(base + '/api/media').json()['media'][0]
            self.assertEqual(public['members'], ['rm', 'jimin'])
            server.handle_command(server.OWNER, '/hide latest')
            self.assertEqual(server.requests.get(base + '/api/media').json()['media'], [])
            self.assertEqual(server.requests.get(base + '/Download/sample.jpg').status_code, 404)
            server.handle_command(server.OWNER, '/show example')
            self.assertEqual(len(server.requests.get(base + '/api/media').json()['media']), 1)
        finally:
            http.shutdown()
            http.server_close()
            thread.join()

    @patch.object(server, 'reply')
    @patch.object(server.requests, 'get')
    @patch.object(server, 'telegram', return_value={'file_path': 'photos/file.jpg'})
    def test_failed_download_leaves_no_partial_file_or_gallery_entry(self, api, get, reply):
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_content.side_effect = server.requests.ConnectionError('Disconnected')
        get.return_value = response
        server.ingest(self.message())
        with server.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM media').fetchone()[0], 0)
        self.assertEqual(list(self.root.glob('*.part')), [])
        self.assertIn('Could not download', reply.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
