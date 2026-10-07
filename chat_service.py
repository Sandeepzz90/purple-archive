"""Private browser conversations, durable messages and an owner notification outbox."""
import hashlib
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque

COOKIE_NAME = 'purple_private_chat'
MAX_TEXT = 1600


class ChatError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS chat_visitors (id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, created REAL, last_seen REAL)')
    db.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, visitor_id TEXT NOT NULL,
        sender TEXT NOT NULL CHECK(sender IN ('visitor','owner')), body TEXT NOT NULL,
        created REAL NOT NULL, client_id TEXT, reply_to INTEGER,
        relay_state TEXT NOT NULL DEFAULT 'queued', telegram_message_id INTEGER UNIQUE,
        attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
        owner_event TEXT UNIQUE, UNIQUE(visitor_id,client_id))''')
    db.execute('CREATE INDEX IF NOT EXISTS chat_thread ON chat_messages(visitor_id,id)')
    db.execute('CREATE INDEX IF NOT EXISTS chat_outbox ON chat_messages(relay_state,next_attempt)')
    db.execute('CREATE TABLE IF NOT EXISTS chat_reply_prompts (telegram_message_id INTEGER PRIMARY KEY, visitor_id TEXT NOT NULL, reply_to INTEGER NOT NULL)')


class ChatService:
    def __init__(self, database):
        self.database = database
        self.relay_lock = threading.Lock()
        self.rate_lock = threading.Lock()
        self.session_rates = defaultdict(deque)

    def create_session(self, address=''):
        now = time.time()
        # An address is used only for a short-lived creation limit, never as identity.
        rate_key = hashlib.sha256(address.encode()).hexdigest()
        with self.rate_lock:
            for key in list(self.session_rates):
                if not self.session_rates[key] or self.session_rates[key][-1] < now - 60:
                    self.session_rates.pop(key, None)
            recent = self.session_rates[rate_key]
            while recent and recent[0] < now - 60:
                recent.popleft()
            if len(recent) >= 30:
                raise ChatError('Please wait a minute before starting another conversation.', 429)
            recent.append(now)
        for _ in range(4):
            token = secrets.token_urlsafe(32)
            visitor_id = 'PV-' + secrets.token_hex(5).upper()
            try:
                with self.database() as db:
                    db.execute('INSERT INTO chat_visitors VALUES (?,?,?,?)', (visitor_id, self.token_hash(token), now, now))
                return {'id': visitor_id, 'created': now}, token
            except sqlite3.IntegrityError:
                continue
        raise ChatError('Could not start your conversation. Please try again.', 503)

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def authenticate(self, token):
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            return None
        with self.database() as db:
            row = db.execute('SELECT id,created FROM chat_visitors WHERE token_hash=?', (self.token_hash(token),)).fetchone()
            if not row:
                return None
            return dict(row)

    def history(self, visitor_id, after=None, before=None):
        if after is not None and before is not None:
            raise ChatError('Choose one history cursor.')
        try:
            after = int(after) if after is not None else None
            before = int(before) if before is not None else None
            if (after is not None and not 0 <= after <= 9223372036854775807) or (before is not None and not 1 <= before <= 9223372036854775807):
                raise ValueError()
        except (TypeError, ValueError):
            raise ChatError('Invalid history cursor.') from None
        columns = 'id,sender,body,created,reply_to,relay_state,client_id'
        with self.database() as db:
            if after is not None:
                rows = db.execute(f'SELECT {columns} FROM chat_messages WHERE visitor_id=? AND id>? ORDER BY id LIMIT 60', (visitor_id, after)).fetchall()
            else:
                rows = db.execute(f'SELECT {columns} FROM chat_messages WHERE visitor_id=? ' + ('AND id<? ' if before is not None else '') + 'ORDER BY id DESC LIMIT 60', (visitor_id, before) if before is not None else (visitor_id,)).fetchall()[::-1]
            oldest = rows[0]['id'] if rows else before
            newest = rows[-1]['id'] if rows else after
            older = bool(oldest and db.execute('SELECT 1 FROM chat_messages WHERE visitor_id=? AND id<? LIMIT 1', (visitor_id, oldest)).fetchone())
            more_new = bool(newest is not None and db.execute('SELECT 1 FROM chat_messages WHERE visitor_id=? AND id>? LIMIT 1', (visitor_id, newest)).fetchone())
            deliveries = [dict(row) for row in db.execute("SELECT id,relay_state FROM chat_messages WHERE visitor_id=? AND sender='visitor' ORDER BY id DESC LIMIT 60", (visitor_id,))]
        return {'messages': [dict(row) for row in rows], 'has_older': older, 'has_newer': more_new, 'deliveries': deliveries}

    def send_visitor(self, visitor_id, text, client_id, reply_to=None):
        if not isinstance(text, str) or not text.strip():
            raise ChatError('Write a little message first.')
        text = text.strip()
        if len(text) > MAX_TEXT or '\x00' in text:
            raise ChatError(f'Keep your message within {MAX_TEXT} characters.')
        try:
            text.encode('utf-8')
        except UnicodeEncodeError:
            raise ChatError('This message contains an invalid character.') from None
        if not isinstance(client_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{12,80}', client_id):
            raise ChatError('Invalid message identifier.')
        if reply_to is not None and (not isinstance(reply_to, int) or isinstance(reply_to, bool) or not 1 <= reply_to <= 9223372036854775807):
            raise ChatError('Invalid reply reference.')
        now = time.time()
        with self.database() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT * FROM chat_messages WHERE visitor_id=? AND client_id=?', (visitor_id, client_id)).fetchone()
            if previous:
                if previous['body'] != text or previous['reply_to'] != reply_to:
                    raise ChatError('This message identifier was already used.', 409)
                return self.public_message(previous)
            count = db.execute("SELECT COUNT(*) FROM chat_messages WHERE visitor_id=? AND sender='visitor' AND created>?", (visitor_id, now - 60)).fetchone()[0]
            if count >= 10:
                raise ChatError('A little pause—please try again in a minute.', 429)
            if reply_to is not None and not db.execute('SELECT 1 FROM chat_messages WHERE id=? AND visitor_id=?', (reply_to, visitor_id)).fetchone():
                raise ChatError('That message is not in your conversation.', 400)
            cursor = db.execute("INSERT INTO chat_messages (visitor_id,sender,body,created,client_id,reply_to) VALUES (?,'visitor',?,?,?,?)", (visitor_id, text, now, client_id, reply_to))
            db.execute('UPDATE chat_visitors SET last_seen=? WHERE id=?', (now, visitor_id))
            row = db.execute('SELECT * FROM chat_messages WHERE id=?', (cursor.lastrowid,)).fetchone()
            return self.public_message(row)

    @staticmethod
    def public_message(row):
        return {key: row[key] for key in ('id', 'sender', 'body', 'created', 'reply_to', 'relay_state', 'client_id')}

    def owner_send(self, visitor_id, text, event, reply_to=None):
        visitor_id = visitor_id.upper()
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ChatError('Use /chat ID your reply (up to 4000 characters).')
        with self.database() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM chat_visitors WHERE id=?', (visitor_id,)).fetchone():
                raise ChatError('Chat ID not found. Use /chats to see recent conversations.', 404)
            existing = db.execute('SELECT id,visitor_id FROM chat_messages WHERE owner_event=?', (event,)).fetchone()
            if existing:
                if existing['visitor_id'] != visitor_id:
                    raise ChatError('This reply was already used for another chat.', 409)
                return existing['id']
            if reply_to is not None and not db.execute('SELECT 1 FROM chat_messages WHERE id=? AND visitor_id=?', (reply_to, visitor_id)).fetchone():
                raise ChatError('The quoted message belongs to a different conversation.')
            cursor = db.execute("INSERT INTO chat_messages (visitor_id,sender,body,created,reply_to,relay_state,owner_event) VALUES (?,'owner',?,?,?,'none',?)", (visitor_id, text.strip(), time.time(), reply_to, event))
            return cursor.lastrowid

    def quoted_message(self, telegram_id):
        with self.database() as db:
            row = db.execute('SELECT id,visitor_id FROM chat_messages WHERE telegram_message_id=?', (telegram_id,)).fetchone()
            if not row:
                row = db.execute('SELECT NULLIF(reply_to,0) AS id,visitor_id FROM chat_reply_prompts WHERE telegram_message_id=?', (telegram_id,)).fetchone()
            return dict(row) if row else None

    def reply_prompt(self, send, owner_id, visitor_id):
        visitor_id = visitor_id.upper()
        with self.database() as db:
            visitor = db.execute('SELECT id FROM chat_visitors WHERE id=?',(visitor_id,)).fetchone()
            row = db.execute('SELECT id FROM chat_messages WHERE visitor_id=? ORDER BY id DESC LIMIT 1', (visitor_id,)).fetchone()
        if not visitor:
            raise ChatError('Conversation not found.', 404)
        result = send('sendMessage', chat_id=owner_id, text=f'↩ Reply to {visitor_id}\n\nType your response using Reply on this message. It will appear only in this visitor’s website chat.', reply_markup={'force_reply': True, 'selective': False, 'input_field_placeholder': 'Your private reply…'})
        with self.database() as db:
            db.execute('INSERT OR REPLACE INTO chat_reply_prompts VALUES (?,?,?)', (result['message_id'], visitor_id, row['id'] if row else 0))

    def recent(self):
        with self.database() as db:
            rows = db.execute('''SELECT v.id,m.body,m.sender,MAX(COALESCE(m.created,0),v.last_seen) AS activity FROM chat_visitors v
                LEFT JOIN chat_messages m ON m.id=(SELECT MAX(id) FROM chat_messages WHERE visitor_id=v.id)
                ORDER BY activity DESC LIMIT 12''').fetchall()
        return '\n\n'.join(f'{r["id"]} · {"visitor" if r["sender"] == "visitor" else "you" if r["sender"] else "visited"}\n{r["body"][:120] if r["body"] else "No messages yet — you can say hello first."}' for r in rows) or 'No visitors yet.'

    def owner_history(self, visitor_id):
        visitor_id = visitor_id.upper()
        with self.database() as db:
            if not db.execute('SELECT 1 FROM chat_visitors WHERE id=?', (visitor_id,)).fetchone():
                raise ChatError('Chat ID not found.', 404)
            rows = db.execute('SELECT id,sender,body FROM chat_messages WHERE visitor_id=? ORDER BY id DESC LIMIT 8', (visitor_id,)).fetchall()[::-1]
        return f'Conversation {visitor_id}\n\n' + ('\n\n'.join(f'#{r["id"]} {"Visitor" if r["sender"] == "visitor" else "You"}: {r["body"][:180]}' for r in rows) or 'No messages yet.')

    def relay_next(self, send, owner_id):
        if not owner_id:
            return False
        with self.relay_lock:
            now = time.time()
            with self.database() as db:
                row = db.execute("SELECT * FROM chat_messages WHERE sender='visitor' AND relay_state='queued' AND next_attempt<=? ORDER BY id LIMIT 1", (now,)).fetchone()
            if not row:
                return False
            text = f'💬 Private website message\nChat: {row["visitor_id"]}\nMessage #{row["id"]}\n\n{row["body"]}\n\nReply to this message, or:\n/chat {row["visitor_id"]} your reply'
            try:
                result = send('sendMessage', chat_id=owner_id, text=text, reply_markup={'inline_keyboard': [[{'text': '↩ Reply privately', 'callback_data': 'reply:'+row['visitor_id']}, {'text': '☰ Conversation', 'callback_data': 'thread:'+row['visitor_id']}]]})
                telegram_id = result['message_id']
                with self.database() as db:
                    db.execute("UPDATE chat_messages SET relay_state='sent',telegram_message_id=? WHERE id=?", (telegram_id, row['id']))
            except Exception:
                # The message remains in the durable outbox during outages/restarts.
                attempts = row['attempts'] + 1
                delay = min(300, 5 * (2 ** min(attempts, 6)))
                with self.database() as db:
                    db.execute('UPDATE chat_messages SET attempts=?,next_attempt=? WHERE id=?', (attempts, time.time() + delay, row['id']))
            return True
