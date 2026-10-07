"""Durable visit alerts, private unread state and atomic one-time note opening."""
import json
import re
import threading
import time
from datetime import datetime
from personal_birthday import IST
from chat_service import ChatError


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS site_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, visitor_id TEXT NOT NULL,
        kind TEXT NOT NULL, request_id TEXT NOT NULL, page TEXT NOT NULL,
        created REAL NOT NULL, state TEXT NOT NULL DEFAULT 'queued',
        attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
        telegram_message_id INTEGER, UNIQUE(visitor_id,kind,request_id))''')
    db.execute('CREATE INDEX IF NOT EXISTS site_event_queue ON site_events(state,next_attempt)')
    db.execute('CREATE TABLE IF NOT EXISTS chat_reads (visitor_id TEXT PRIMARY KEY, through_id INTEGER NOT NULL DEFAULT 0)')
    db.execute('''CREATE TABLE IF NOT EXISTS note_receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, visitor_id TEXT NOT NULL,
        request_id TEXT NOT NULL, note_json TEXT NOT NULL, created REAL NOT NULL,
        UNIQUE(visitor_id,request_id))''')


def request_key(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{12,80}',value):
        raise ChatError('Invalid request identifier.')
    return value


def page_path(value):
    if not isinstance(value,str) or len(value)>160 or not re.fullmatch(r'/[A-Za-z0-9/_-]*',value):
        raise ChatError('Invalid page path.')
    return value


class VisitorActivity:
    def __init__(self,database):
        self.database=database
        self.lock=threading.Lock()

    def visit(self,visitor_id,request_id,page):
        request_key(request_id);page_path(page)
        now=time.time()
        with self.database() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute("SELECT id FROM site_events WHERE visitor_id=? AND kind='visit' AND request_id=?",(visitor_id,request_id)).fetchone()
            if existing:
                return {'recorded':True,'event_id':existing['id']}
            recent=db.execute("SELECT COUNT(*) FROM site_events WHERE visitor_id=? AND kind='visit' AND created>?",(visitor_id,now-60)).fetchone()[0]
            if recent>=30:
                raise ChatError('Please wait before refreshing again.',429)
            # only notify owner for the FIRST visit in 6h per visitor (no refresh spam)
            notify = db.execute("SELECT COUNT(*) FROM site_events WHERE visitor_id=? AND kind='visit' AND created>?",(visitor_id,now-21600)).fetchone()[0] == 0
            if notify:
                cursor=db.execute("INSERT INTO site_events(visitor_id,kind,request_id,page,created) VALUES (?,'visit',?,?,?)",(visitor_id,request_id,page,now))
            else:
                cursor=db.execute("INSERT INTO site_events(visitor_id,kind,request_id,page,created,state) VALUES (?,'visit',?,?,?,'silent')",(visitor_id,request_id,page,now))
            db.execute('UPDATE chat_visitors SET last_seen=? WHERE id=?',(now,visitor_id))
            return {'recorded':True,'event_id':cursor.lastrowid}

    def notifications(self,visitor_id):
        with self.database() as db:
            row=db.execute('SELECT through_id FROM chat_reads WHERE visitor_id=?',(visitor_id,)).fetchone()
            read=row['through_id'] if row else 0
            unread=db.execute("SELECT COUNT(*) AS amount,MAX(id) AS latest FROM chat_messages WHERE visitor_id=? AND sender='owner' AND id>?",(visitor_id,read)).fetchone()
        return {'visitor_id':visitor_id,'unread_count':unread['amount'],'latest_id':unread['latest'] or 0}

    def mark_read(self,visitor_id,through_id):
        if not isinstance(through_id,int) or isinstance(through_id,bool) or not 0<=through_id<=9223372036854775807:
            raise ChatError('Invalid read position.')
        with self.database() as db:
            db.execute('BEGIN IMMEDIATE')
            if through_id and not db.execute("SELECT 1 FROM chat_messages WHERE visitor_id=? AND id=? AND sender='owner'",(visitor_id,through_id)).fetchone():
                raise ChatError('That reply is not in your conversation.')
            db.execute('INSERT INTO chat_reads VALUES (?,?) ON CONFLICT(visitor_id) DO UPDATE SET through_id=MAX(chat_reads.through_id,excluded.through_id)',(visitor_id,through_id))
        return self.notifications(visitor_id)

    def open_note(self,visitor_id,request_id,page,note):
        request_key(request_id);page_path(page)
        with self.database() as db:
            db.execute('BEGIN IMMEDIATE')
            receipt=db.execute('SELECT note_json FROM note_receipts WHERE visitor_id=? AND request_id=?',(visitor_id,request_id)).fetchone()
            if receipt:
                return {'note':json.loads(receipt['note_json']),'consumed':True}
            enabled=db.execute("SELECT value FROM state WHERE key='sorry_enabled'").fetchone()
            if enabled and enabled['value']!='on':
                raise ChatError('This note is no longer available.',404)
            now=time.time()
            db.execute('INSERT INTO note_receipts(visitor_id,request_id,note_json,created) VALUES (?,?,?,?)',(visitor_id,request_id,json.dumps(note),now))
            db.execute("INSERT OR REPLACE INTO state VALUES ('sorry_enabled','off')")
            db.execute("INSERT INTO site_events(visitor_id,kind,request_id,page,created) VALUES (?,'note_open',?,?,?)",(visitor_id,request_id,page,now))
            return {'note':note,'consumed':True}

    def relay_next(self,send,owner_id):
        if not owner_id:return False
        with self.lock:
            with self.database() as db:
                row=db.execute("SELECT * FROM site_events WHERE state='queued' AND next_attempt<=? ORDER BY id LIMIT 1",(time.time(),)).fetchone()
            if not row:return False
            heading='✉ The apology note was opened' if row['kind']=='note_open' else '👋 A visitor opened your site'
            detail='\nThe note has automatically been hidden from the site. Use /sorry on to make it available again.' if row['kind']=='note_open' else ''
            opened=datetime.fromtimestamp(row['created'],IST).strftime('%d %b %Y · %H:%M IST')
            text=f'{heading}\n\nVisitor: {row["visitor_id"]}\nPage: {row["page"]}\nOpened: {opened}{detail}\n\nStart a private conversation:\n/chat {row["visitor_id"]} your message'
            keyboard={'inline_keyboard':[[{'text':'💬 Message this visitor','callback_data':'reply:'+row['visitor_id']},{'text':'View conversation','callback_data':'thread:'+row['visitor_id']}]]}
            try:
                result=send('sendMessage',chat_id=owner_id,text=text,reply_markup=keyboard)
                with self.database() as db:
                    db.execute("UPDATE site_events SET state='sent',telegram_message_id=? WHERE id=?",(result['message_id'],row['id']))
                    db.execute('INSERT OR REPLACE INTO chat_reply_prompts VALUES (?,?,0)',(result['message_id'],row['visitor_id']))
            except Exception:
                attempts=row['attempts']+1
                with self.database() as db:
                    db.execute('UPDATE site_events SET attempts=?,next_attempt=? WHERE id=?',(attempts,time.time()+min(300,5*2**min(attempts,6)),row['id']))
            return True
