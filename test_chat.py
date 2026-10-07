import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import requests
import server
import chat_service


class PrivateChatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data_patch = patch.object(server, 'DATA', self.root)
        self.data_patch.start()
        server.initialize_database()
        self.chat = chat_service.ChatService(server.database)
        self.chat_patch = patch.object(server, 'CHAT', self.chat)
        self.chat_patch.start()
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.http.server_port}'
        self.sessions = []

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        for session in self.sessions:
            session.close()
        self.chat_patch.stop()
        self.data_patch.stop()
        self.temp.cleanup()

    def visitor(self):
        session = requests.Session()
        session.headers.update({'X-Chat-Request': '1', 'Origin': self.base})
        self.sessions.append(session)
        response = session.post(self.base+'/api/chat/session', json={})
        self.assertEqual(response.status_code, 201)
        return session, response.json()['visitor']['id'], response

    def send(self, session, text, client_id='sample-message-0001', **extra):
        return session.post(self.base+'/api/chat/messages', json={'text': text, 'client_id': client_id, **extra})

    def history(self, session, query=''):
        response = session.get(self.base+'/api/chat/messages'+query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        return response.json()

    def test_same_ip_visitors_have_distinct_secret_sessions_and_isolated_history(self):
        a, aid, response = self.visitor()
        b, bid, _ = self.visitor()
        self.assertNotEqual(aid, bid)
        token_a = a.cookies.get(chat_service.COOKIE_NAME)
        token_b = b.cookies.get(chat_service.COOKIE_NAME)
        self.assertNotEqual(token_a, token_b)
        self.assertIn('HttpOnly', response.headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', response.headers['Set-Cookie'])
        self.assertIn('Path=/api/chat', response.headers['Set-Cookie'])
        self.assertNotIn(token_a, response.text)
        with server.database() as db:
            row = db.execute('SELECT * FROM chat_visitors WHERE id=?', (aid,)).fetchone()
            self.assertNotEqual(row['token_hash'], token_a)
        self.assertEqual(self.send(a, 'Only visitor A should see this.').status_code, 201)
        self.assertEqual(self.history(b)['messages'], [])
        self.assertEqual(self.send(b, 'Only visitor B should see this.').status_code, 201)
        self.assertEqual([m['body'] for m in self.history(a, '?visitor_id='+bid)['messages']], ['Only visitor A should see this.'])
        self.assertEqual([m['body'] for m in self.history(b, '?id='+aid)['messages']], ['Only visitor B should see this.'])
        unauth = requests.get(self.base+'/api/chat/messages?visitor_id='+aid)
        self.assertEqual(unauth.status_code, 401)
        forged = requests.get(self.base+'/api/chat/messages', headers={'Cookie': chat_service.COOKIE_NAME+'='+aid})
        self.assertEqual(forged.status_code, 401)

    def test_session_reuse_and_persistence_without_ip_identity(self):
        session, visitor_id, _ = self.visitor()
        token = session.cookies.get(chat_service.COOKIE_NAME)
        same = session.post(self.base+'/api/chat/session', json={})
        self.assertEqual(same.status_code, 200)
        self.assertEqual(same.json()['visitor']['id'], visitor_id)
        self.send(session, 'Keep this after restarting.')
        restarted = chat_service.ChatService(server.database)
        self.assertEqual(restarted.authenticate(token)['id'], visitor_id)
        self.assertEqual(restarted.history(visitor_id)['messages'][0]['body'], 'Keep this after restarting.')

    def test_idempotent_submission_and_cross_thread_quotes(self):
        a, aid, _ = self.visitor()
        b, bid, _ = self.visitor()
        first = self.send(a, 'Hello once.').json()['message']
        second = self.send(a, 'Hello once.').json()['message']
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(self.history(a)['messages']), 1)
        self.assertEqual(self.send(a, 'Changed body, same request ID.').status_code, 409)
        self.assertEqual(self.send(b, 'Trying a foreign quote.', reply_to=first['id']).status_code, 400)
        self.assertEqual(self.send(b, 'Own message.', visitor_id=aid).status_code, 201)
        self.assertEqual(len(self.history(a)['messages']), 1)

    def test_owner_command_and_native_reply_only_reach_the_target_visitor(self):
        a, aid, _ = self.visitor()
        b, bid, _ = self.visitor()
        original = self.send(a, 'Hello from A.').json()['message']
        sender = Mock(return_value={'message_id': 8001})
        self.assertTrue(self.chat.relay_next(sender, server.OWNER))
        self.assertIn(aid, sender.call_args.kwargs['text'])
        self.assertEqual(sender.call_args.kwargs['chat_id'], server.OWNER)
        self.assertEqual(self.history(a)['deliveries'][0]['relay_state'], 'sent')
        with patch.object(server, 'reply'):
            server.accept_update({'update_id': 101, 'message': {'from': {'id': server.OWNER}, 'chat': {'id': server.OWNER, 'type': 'private'}, 'text': f'/chat {aid} Our words stay exactly as written.'}})
            server.accept_update({'update_id': 102, 'message': {'from': {'id': server.OWNER}, 'chat': {'id': server.OWNER, 'type': 'private'}, 'text': 'A native reply.', 'reply_to_message': {'message_id': 8001}}})
            # Replayed bot updates must not duplicate a reply.
            server.accept_update({'update_id': 102, 'message': {'from': {'id': server.OWNER}, 'chat': {'id': server.OWNER, 'type': 'private'}, 'text': 'A native reply.', 'reply_to_message': {'message_id': 8001}}})
        rows = self.history(a)['messages']
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[-1]['reply_to'], original['id'])
        self.assertEqual(rows[1]['body'], 'Our words stay exactly as written.')
        self.assertEqual(self.history(b)['messages'], [])
        with patch.object(server, 'reply') as reply:
            server.accept_update({'update_id': 103, 'message': {'from': {'id': -1}, 'chat': {'id': -1, 'type': 'private'}, 'text': f'/chat {aid} Intruder'}})
            reply.assert_not_called()
        self.assertEqual(len(self.history(a)['messages']), 3)

    def test_conflicting_owner_quote_is_rejected_and_owner_quoted_text_can_be_forwarded(self):
        a, aid, _ = self.visitor()
        b, bid, _ = self.visitor()
        self.send(a, 'A visitor message.')
        self.chat.relay_next(Mock(return_value={'message_id': 8002}), server.OWNER)
        with patch.object(server, 'reply') as reply:
            server.handle_command(server.OWNER, f'/chat {bid} Wrong thread', {'reply_to_message': {'message_id': 8002}}, 201)
            self.assertIn('another visitor', reply.call_args.args[1])
            server.handle_command(server.OWNER, f'/chat {bid}', {'reply_to_message': {'message_id': 9900, 'from': {'id': server.OWNER}, 'text': 'Forward this owner reply.'}}, 202)
        self.assertEqual(self.history(b)['messages'][0]['body'], 'Forward this owner reply.')
        self.assertEqual(len(self.history(a)['messages']), 1)

    def test_outbox_retry_persists_and_never_drops_failed_notifications(self):
        session, visitor_id, _ = self.visitor()
        self.send(session, 'Please keep me during an outage.')
        self.chat.relay_next(Mock(side_effect=RuntimeError('offline')), server.OWNER)
        with server.database() as db:
            row = db.execute('SELECT * FROM chat_messages').fetchone()
            self.assertEqual(row['relay_state'], 'queued')
            self.assertEqual(row['attempts'], 1)
            self.assertGreater(row['next_attempt'], row['created'])
            db.execute('UPDATE chat_messages SET next_attempt=0')
        restarted = chat_service.ChatService(server.database)
        send = Mock(return_value={'message_id': 9001})
        self.assertTrue(restarted.relay_next(send, server.OWNER))
        self.assertFalse(restarted.relay_next(send, server.OWNER))
        send.assert_called_once()
        self.assertEqual(restarted.history(visitor_id)['messages'][0]['relay_state'], 'sent')

    def test_paginated_history_and_polling_preserve_every_message(self):
        session, visitor_id, _ = self.visitor()
        for number in range(135):
            self.chat.owner_send(visitor_id, f'Message {number}', f'event-{number}')
        latest = self.history(session)
        self.assertEqual(len(latest['messages']), 60)
        self.assertEqual(latest['messages'][0]['body'], 'Message 75')
        self.assertTrue(latest['has_older'])
        older = self.history(session, '?before='+str(latest['messages'][0]['id']))
        oldest = self.history(session, '?before='+str(older['messages'][0]['id']))
        bodies = [m['body'] for m in oldest['messages']+older['messages']+latest['messages']]
        self.assertEqual(bodies, [f'Message {i}' for i in range(135)])
        self.chat.owner_send(visitor_id, 'The new reply.', 'event-new')
        new = self.history(session, '?after='+str(latest['messages'][-1]['id']))
        self.assertEqual([m['body'] for m in new['messages']], ['The new reply.'])

    def test_origin_content_limits_and_message_throttling(self):
        session, visitor_id, _ = self.visitor()
        response = session.post(self.base+'/api/chat/messages', json={'text':'cross-site','client_id':'foreign-00000001'}, headers={'Origin':'https://another.example'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(requests.post(self.base+'/api/chat/session', json={}).status_code, 403)
        self.assertEqual(self.send(session, '').status_code, 400)
        self.assertEqual(self.send(session, 'x'*1601).status_code, 400)
        self.assertEqual(self.send(session, '\ud800').status_code, 400)
        self.assertEqual(self.send(session, 'A quote', reply_to=10**30).status_code, 400)
        self.assertEqual(session.get(self.base+'/api/chat/messages?after='+str(10**30)).status_code, 400)
        self.assertEqual(session.post(self.base+'/api/chat/messages', json=['invalid']).status_code, 400)
        for number in range(10):
            self.assertEqual(self.send(session, 'A little message', f'unique-message-{number:04}').status_code, 201)
        self.assertEqual(self.send(session, 'Too many', 'unique-message-0011').status_code, 429)
        self.assertEqual(len(self.history(session)['messages']), 10)

    def test_owner_buttons_are_guarded_and_reply_prompt_keeps_thread_context(self):
        session, visitor_id, _ = self.visitor()
        original = self.send(session, 'A message for the owner.').json()['message']
        callback = {'id': 'callback-1', 'from': {'id': -1}, 'message': {'message_id': 9000, 'chat': {'id': -1, 'type': 'private'}}, 'data': 'note:off'}
        with patch.object(server, 'telegram', return_value={'message_id': 9002}) as api:
            server.accept_update({'callback_query': callback, 'update_id': 301})
            api.assert_not_called()
            self.assertEqual(server.setting('sorry_enabled', 'on'), 'on')
            callback['from']['id'] = server.OWNER
            callback['message']['chat']['id'] = server.OWNER
            server.accept_update({'callback_query': callback, 'update_id': 302})
            self.assertEqual(server.setting('sorry_enabled'), 'off')
            self.assertEqual(api.call_args.args[0], 'editMessageText')
            self.assertIn('inline_keyboard', api.call_args.kwargs['reply_markup'])
            callback['data'] = 'reply:'+visitor_id
            server.accept_update({'callback_query': callback, 'update_id': 303})
            self.assertTrue(api.call_args.kwargs['reply_markup']['force_reply'])
            self.assertEqual(self.chat.quoted_message(9002)['visitor_id'], visitor_id)
            with patch.object(server, 'reply'):
                server.accept_update({'update_id': 304, 'message': {'from': {'id': server.OWNER}, 'chat': {'id': server.OWNER, 'type': 'private'}, 'text': 'A reply from the button flow.', 'reply_to_message': {'message_id': 9002}}})
        history = self.history(session)['messages']
        self.assertEqual(history[-1]['body'], 'A reply from the button flow.')
        self.assertEqual(history[-1]['reply_to'], original['id'])

    def test_reading_pages_and_all_release_routes_are_available(self):
        paths = sorted(server.READING_PAGES)+['/music/'+slug for slug in server.RELEASE_SLUGS]
        for path in paths:
            response = requests.get(self.base+path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn('/journey.js', response.text)
        self.assertEqual(requests.get(self.base+'/music/not-a-release').status_code, 404)


if __name__ == '__main__':
    unittest.main()
