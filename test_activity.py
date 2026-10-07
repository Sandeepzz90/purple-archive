from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
import requests
import server
from chat_service import ChatService
from visitor_activity import VisitorActivity


class VisitorActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.patches=[patch.object(server,'DATA',self.root)]
        self.patches[0].start();server.initialize_database()
        self.chat=ChatService(server.database);self.activity=VisitorActivity(server.database)
        self.patches += [patch.object(server,'CHAT',self.chat),patch.object(server,'ACTIVITY',self.activity)]
        for item in self.patches[1:]:item.start()
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.http.server_port}';self.sessions=[]

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join()
        for session in self.sessions:session.close()
        for item in reversed(self.patches):item.stop()
        self.temp.cleanup()

    def visitor(self):
        session=requests.Session();session.headers.update({'X-Chat-Request':'1','Origin':self.base});self.sessions.append(session)
        response=session.post(self.base+'/api/chat/session',json={});self.assertEqual(response.status_code,201)
        return session,response.json()['visitor']['id']

    def post(self,session,endpoint,body):return session.post(self.base+'/api/chat/'+endpoint,json=body)

    def test_visits_are_durable_and_retry_does_not_notify_twice(self):
        client,identity=self.visitor();payload={'request_id':'visit-request-0001','page':'/korea'}
        first=self.post(client,'visit',payload);second=self.post(client,'visit',payload)
        self.assertEqual(first.json(),second.json())
        send=Mock(return_value={'message_id':500})
        self.assertTrue(self.activity.relay_next(send,server.OWNER));self.assertFalse(self.activity.relay_next(send,server.OWNER))
        send.assert_called_once();self.assertIn(identity,send.call_args.kwargs['text']);self.assertIn('/korea',send.call_args.kwargs['text'])
        self.assertIn('inline_keyboard',send.call_args.kwargs['reply_markup'])
        self.assertEqual(self.chat.quoted_message(500),{'id':None,'visitor_id':identity})
        self.assertEqual(self.post(client,'visit',{'request_id':'visit-request-0002','page':'/chat'}).status_code,200)
        with server.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM site_events').fetchone()[0],2)

    def test_owner_can_start_chat_before_visitor_sends_any_message(self):
        a,aid=self.visitor();b,bid=self.visitor()
        self.post(a,'visit',{'request_id':'visit-request-0003','page':'/'})
        self.activity.relay_next(Mock(return_value={'message_id':501}),server.OWNER)
        self.chat.reply_prompt(Mock(return_value={'message_id':502}),server.OWNER,aid)
        with patch.object(server,'reply'):
            server.accept_update({'update_id':80,'message':{'from':{'id':server.OWNER},'chat':{'id':server.OWNER,'type':'private'},'text':'A message just for you.','reply_to_message':{'message_id':502}}})
        notification=a.get(self.base+'/api/chat/notifications').json();self.assertEqual(notification['unread_count'],1)
        self.assertEqual(b.get(self.base+'/api/chat/notifications?visitor_id='+aid).json()['unread_count'],0)
        message=a.get(self.base+'/api/chat/messages').json()['messages'][0]
        self.assertEqual(message['body'],'A message just for you.');self.assertIsNone(message['reply_to'])
        self.assertEqual(self.post(b,'read',{'through_id':message['id']}).status_code,400)
        self.assertEqual(self.post(a,'read',{'through_id':message['id']}).json()['unread_count'],0)
        self.assertEqual(a.get(self.base+'/api/chat/notifications').json()['unread_count'],0)
        self.chat.owner_send(aid,'Another reply.','second-reply')
        self.assertEqual(a.get(self.base+'/api/chat/notifications').json()['unread_count'],1)

    def test_note_is_one_time_global_and_recoverable_only_by_same_request(self):
        a,aid=self.visitor();b,bid=self.visitor();server.set_setting('sorry_enabled','on')
        self.assertEqual(requests.get(self.base+'/api/note').status_code,404)
        payload={'request_id':'note-request-0001','page':'/korea'}
        first=self.post(a,'note/open',payload);self.assertEqual(first.status_code,200)
        self.assertEqual(first.json()['note']['title'],"I'm really sorry")
        self.assertEqual(first.headers['Cache-Control'],'no-store')
        self.assertEqual(server.setting('sorry_enabled'),'off')
        self.assertEqual(requests.get(self.base+'/sorry').status_code,404)
        self.assertFalse(requests.get(self.base+'/api/settings').json()['noteEnabled'])
        self.assertEqual(self.post(a,'note/open',payload).json(),first.json())
        self.assertEqual(self.post(b,'note/open',payload).status_code,404)
        self.assertEqual(self.post(a,'note/open',{'request_id':'note-request-0002','page':'/korea'}).status_code,404)
        with server.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM note_receipts').fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM site_events WHERE kind='note_open'").fetchone()[0],1)
        sender=Mock(return_value={'message_id':503});self.activity.relay_next(sender,server.OWNER)
        self.assertIn(aid,sender.call_args.kwargs['text']);self.assertIn('automatically been hidden',sender.call_args.kwargs['text'])
        server.set_setting('sorry_enabled','on')
        self.assertEqual(self.post(b,'note/open',{'request_id':'note-request-0003','page':'/korea'}).status_code,200)

    def test_concurrent_note_open_has_only_one_winner(self):
        a,_=self.visitor();b,_=self.visitor();server.set_setting('sorry_enabled','on')
        def open_note(pair):client,index=pair;return self.post(client,'note/open',{'request_id':f'concurrent-note-{index:04}','page':'/korea'}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(open_note,[(a,1),(b,2)]))
        self.assertEqual(sorted(statuses),[200,404])
        with server.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM note_receipts').fetchone()[0],1)

    def test_notification_retry_and_private_endpoint_guards(self):
        client,identity=self.visitor();self.post(client,'visit',{'request_id':'visit-retry-0001','page':'/surprise'})
        self.activity.relay_next(Mock(side_effect=RuntimeError('offline')),server.OWNER)
        with server.database() as db:
            row=db.execute('SELECT * FROM site_events').fetchone();self.assertEqual(row['state'],'queued');self.assertEqual(row['attempts'],1);db.execute('UPDATE site_events SET next_attempt=0')
        restarted=VisitorActivity(server.database);send=Mock(return_value={'message_id':504});self.assertTrue(restarted.relay_next(send,server.OWNER))
        self.assertEqual(requests.get(self.base+'/api/chat/notifications').status_code,401)
        self.assertEqual(requests.post(self.base+'/api/chat/note/open',headers={'X-Chat-Request':'1'},json={'request_id':'forged-note-0001','page':'/korea'}).status_code,401)
        bad=client.post(self.base+'/api/chat/visit',headers={'Origin':'https://other.example'},json={'request_id':'bad-origin-0001','page':'/'})
        self.assertEqual(bad.status_code,403)
        self.assertEqual(self.post(client,'visit',{'request_id':'bad-path-0001','page':'/korea?secret=oops'}).status_code,400)


if __name__=='__main__':unittest.main()
