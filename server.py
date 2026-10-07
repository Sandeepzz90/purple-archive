"""Local BTS fan gallery and owner-only Telegram media importer."""
import gzip
import html
from contextlib import contextmanager
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie, CookieError
from urllib.parse import unquote, urlsplit, parse_qs

import requests
from PIL import Image, ImageOps
import vision
import captions
import chat_service
import image_quality
import personal_birthday
import birthday_names
import visitor_activity
import korea_assets
from local_sort import LocalSorter, LocalSortError

ROOT = Path(__file__).resolve().parent
DOWNLOAD = ROOT / 'Download'
DATA = ROOT / 'data'
for directory in (DOWNLOAD, DATA):
    directory.mkdir(exist_ok=True)
if (ROOT / '.env').exists():
    for line in (ROOT / '.env').read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            os.environ.setdefault(key, value)
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
OWNER = int(os.getenv('TELEGRAM_OWNER_ID', '0'))
BOT_STATUS = {'connected': False, 'username': None, 'message': 'Connecting'}
READING_PAGES = {'/story','/music','/eras','/discover','/birthdays','/members','/surprise','/korea','/chat'}
RELEASE_SLUGS = {'2-cool-4-skool','o-rul8-2','skool-luv-affair','dark-and-wild','hyyh-part-1','hyyh-part-2','young-forever','wings','you-never-walk-alone','love-yourself-her','love-yourself-tear','love-yourself-answer','map-of-the-soul-persona','map-of-the-soul-7','dynamite','be','butter','proof'}


@contextmanager
def database():
    connection = sqlite3.connect(DATA / 'gallery.sqlite', timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database():
    with database() as db:
        db.execute('CREATE TABLE IF NOT EXISTS media (id TEXT PRIMARY KEY, filename TEXT, preview TEXT, kind TEXT, title TEXT, member TEXT, source TEXT, credit TEXT, created REAL)')
        db.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS batches (id TEXT PRIMARY KEY, chat_id INTEGER, message_id INTEGER, received REAL, last_edit REAL DEFAULT 0, closed INTEGER DEFAULT 0, last_text TEXT DEFAULT "")')
        db.execute('CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, batch TEXT, message TEXT, category TEXT, status TEXT DEFAULT "queued", result TEXT DEFAULT "{}", created REAL)')
        db.execute('CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status,created)')
        chat_service.initialize(db)
        image_quality.initialize(db)
        visitor_activity.initialize(db)
    os.chmod(DATA, 0o700)
    os.chmod(DATA / 'gallery.sqlite', 0o600)


initialize_database()
CHAT = chat_service.ChatService(database)
ACTIVITY = visitor_activity.VisitorActivity(database)
LOCAL_SORT = LocalSorter(DATA)


MEMBERS = {
    'rm': ('rm', 'namjoon', 'nam joon', '김남준', '남준'),
    'jin': ('jin', 'seokjin', 'seok jin', '김석진', '석진'),
    'suga': ('suga', 'yoongi', 'yoon gi', 'agust d', '민윤기', '슈가', '윤기'),
    'jhope': ('jhope', 'j hope', 'hoseok', 'ho seok', 'hobi', '정호석', '제이홉', '호석'),
    'jimin': ('jimin', 'ji min', '박지민', '지민'),
    'v': ('v', 'taehyung', 'tae hyung', 'tae', '김태형', '태형', '뷔'),
    'jungkook': ('jungkook', 'jung kook', 'jeongguk', 'jk', '전정국', '정국'),
}


def setting(key, default=''):
    with database() as db:
        row = db.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
        return row[0] if row else default


def set_setting(key, value):
    with database() as db:
        db.execute('INSERT OR REPLACE INTO state VALUES (?,?)', (key, value))


def detect_members(text):
    normalized = re.sub(r'[_\-]+', ' ', text.lower())
    return [member for member, aliases in MEMBERS.items() if any(re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', normalized) for alias in aliases)]


def route_member(text, group=''):
    selected = setting('upload_member', 'auto')
    matches = detect_members(text) if selected == 'auto' else []
    member = ','.join(matches) if matches else selected if selected != 'auto' else 'all'
    if group:
        if matches or selected != 'auto':
            set_setting('album:' + group, member)
        else:
            member = setting('album:' + group, member)
    return member


HELP = '''Purple Archive · owner-only controls 💜
/cmds — all private commands
/panel — your button-based control room
/name Name — set the birthday person (girl or boy)
/name Name | Korean spelling — optional Korean name
/surprise today — preview the October 10 celebration today
/surprise auto — October 10 only (ends the temporary preview)
/surprise off — disable the automatic personal celebration
/chats — recent private website conversations
/chat ID your message — reply only to that visitor
/chatlog ID — recent messages in that conversation
/sorry on — show the note
/sorry off — remove its link and disable the note URL
/member auto — sort by caption / filename (English or Korean)
/member rm — send upcoming uploads to RM (also jin, suga, jhope, jimin, v, jungkook, all)
/tag latest jimin — move your latest upload to a member
/tag latest10 jimin — tag the last 10 uploads at once (any number up to 50)
/tag FILE_ID rm,jin — put an upload in multiple profiles
/fetch jimin — find good public photos and approve them here
/recent — list your 10 latest uploads and their IDs
/hide latest — hide your last upload (original kept locally)
/show FILE_ID — restore a hidden upload
/status — check note, upload mode and gallery count
/stats — total images, videos, stickers and uploads
/progress — update the current batch summary
/api — private vision API setup and status
/api key YOUR_KEY — save a provider key privately
/api url HTTPS_CHAT_COMPLETIONS_URL — compatible endpoint
/api model MODEL_NAME — vision-capable model
/api on or off — enable or disable image-based sorting
/api test — check sorting using one saved image
/api clear — remove the key and disable vision
/sort pending — classify existing unassigned photos
/local — local open-source recognition status
/local on or off — control offline member matching
/sort local — sort earlier unassigned photos locally
/learn latest v — teach a clear single-face reference
/help — same as /cmds

Send an album or many photos, stickers and videos together. One summary is edited as the batch progresses; there is no per-file reply. Originals stay in Download. Standard download limit: 20 MB per file. For original image quality, send as File/Document: normal photo uploads can be compressed before the bot receives them.

In auto mode, captions and filenames take priority, then local OpenCV matching if enabled. Uncertain photos stay in All seven; /tag corrects a result and /learn improves references. Optional /api on sends unmatched photos to YOUR configured external provider. A chosen /member overrides automatic sorting.'''

SORT_LOCK = threading.Lock()


def owner_panel(view='home', message_id=None):
    """Only invoked after owner authentication; callbacks never accept arbitrary commands."""
    note_on = setting('sorry_enabled', 'on') == 'on'
    keyboard = [[{'text': '💬 Conversations', 'callback_data': 'panel:chats'}, {'text': '▦ Library & queue', 'callback_data': 'panel:stats'}],
                [{'text': ('♡ Note is ON · hide' if note_on else '♡ Note is OFF · show'), 'callback_data': 'note:' + ('off' if note_on else 'on')}, {'text': '✦ Upload guide', 'callback_data': 'panel:upload'}],
                [{'text': '◉ Local image matching', 'callback_data': 'panel:local'}, {'text': '⚙ Optional vision API', 'callback_data': 'panel:vision'}],
                [{'text': '🎂 October 10 surprise', 'callback_data': 'panel:surprise'}, {'text': '☰ All commands', 'callback_data': 'panel:cmds'}]]
    title='✦ PURPLE CONTROL ROOM'
    text=f'<b>{title}</b>\n<i>Your private corner behind the scenes.</i>\n\nChoose a room below. Every control here is owner-only.\n\n<b>Quick reply</b>\n<code>/chat PV-ID your message</code>'
    if view=='chats':
        text='<b>💬 PRIVATE CONVERSATIONS</b>\n\n'+html.escape(CHAT.recent())
        with database() as db:
            chats=db.execute('SELECT id AS visitor_id FROM chat_visitors ORDER BY MAX(last_seen,COALESCE((SELECT MAX(created) FROM chat_messages WHERE visitor_id=chat_visitors.id),0)) DESC LIMIT 6').fetchall()
        keyboard=[[{'text':'Open '+row['visitor_id'],'callback_data':'thread:'+row['visitor_id']}] for row in chats]+[[{'text':'← Control room','callback_data':'panel:home'}]]
    elif view=='stats':
        text='<b>▦ YOUR LOCAL LIBRARY</b>\n\n'+html.escape(gallery_stats())+'\n\n<i>Uploads are saved locally. A batch uses one updating progress card.</i>'
    elif view=='upload':
        text='<b>✦ ADD A LITTLE MEMORY</b>\n\nSend photos, stickers or videos together. One progress card tracks the batch.\n\n<b>Choose an album</b>\n<code>/member auto</code> — captions & filenames\n<code>/member jimin</code> — upcoming uploads\n<code>/tag latest v</code> — correct the last item\n\n<b>20 MB per file</b> through the standard download API.'
    elif view=='vision':
        text='<b>⚙ PRIVATE VISION SETUP</b>\n\n'+html.escape(vision_status())+'\n\n<code>/api key YOUR_KEY</code>\n<code>/api model MODEL</code>\n<code>/api url HTTPS_ENDPOINT</code>\n<code>/api on</code>\n\nEnabling vision sends unlabelled photos to your configured provider. Keys are never shown here.'
    elif view=='local':
        text='<b>◉ LOCAL IMAGE MATCHING</b>\n\n'+html.escape(local_sort_status())+'\n\n<code>/sort local</code> — classify earlier uploads\n<code>/learn latest v</code> — add a clear labelled reference\n<code>/tag latest jimin</code> — correct a result\n\nDetection uses OpenCV YuNet and SFace on this device. Original image files stay untouched.'
    elif view=='surprise':
        context = personal_birthday.context(setting('surprise_mode','auto'),setting('surprise_preview_date'))
        recipient=birthday_names.current(setting)
        text='<b>🎂 '+html.escape(recipient['name'])+' · '+html.escape(recipient['koreanName'])+'</b>\n\nAutomatic date: <b>10 October · midnight IST</b>\nToday: '+html.escape(context['today'])+'\nCurrent display: '+html.escape(context['occasion'])+'\n\nChange name: <code>/name Name</code>\nPreview: http://localhost:8000/surprise\nKorean world: http://localhost:8000/korea\n\nThe opening plays once per browser, then only on Replay. /sorry on prepares the one-time Korean note gift; it hides after opening and sends you the visitor ID.'
        keyboard=[[{'text':'✦ Preview today','callback_data':'surprise:today'},{'text':'10 Oct only','callback_data':'surprise:auto'}],[{'text':'Disable automatic surprise','callback_data':'surprise:off'},{'text':'← Control room','callback_data':'panel:home'}]]
    elif view=='cmds':
        text='<b>☰ OWNER COMMANDS</b>\n\n'+html.escape(HELP)
    elif view.startswith('thread:'):
        visitor=view.split(':',1)[1]
        text='<b>💬 CONVERSATION</b>\n\n'+html.escape(CHAT.owner_history(visitor))
        keyboard=[[{'text':'↩ Write a private reply','callback_data':'reply:'+visitor}],[{'text':'↻ Refresh','callback_data':'thread:'+visitor},{'text':'← Conversations','callback_data':'panel:chats'}]]
    params={'chat_id':OWNER,'text':text,'parse_mode':'HTML','reply_markup':{'inline_keyboard':keyboard}}
    if message_id:
        params['message_id']=message_id
        return telegram('editMessageText',**params)
    return telegram('sendMessage',**params)


def owner_callback(query):
    message=query.get('message',{})
    if query.get('from',{}).get('id')!=OWNER or message.get('chat',{}).get('id')!=OWNER or message.get('chat',{}).get('type')!='private':
        return
    data=query.get('data','')
    try:
        telegram('answerCallbackQuery',callback_query_id=query['id'])
        if data in ('panel:home','panel:chats','panel:stats','panel:upload','panel:vision','panel:local','panel:surprise','panel:cmds'):
            owner_panel(data.split(':')[1],message.get('message_id'))
        elif data in ('note:on','note:off'):
            set_setting('sorry_enabled',data.split(':')[1])
            owner_panel('home',message.get('message_id'))
        elif data in ('surprise:today','surprise:auto','surprise:off'):
            configure_surprise(data.split(':')[1])
            owner_panel('surprise',message.get('message_id'))
        elif re.fullmatch(r'thread:PV-[A-F0-9]{10}',data):
            owner_panel(data,message.get('message_id'))
        elif re.fullmatch(r'reply:PV-[A-F0-9]{10}',data):
            CHAT.reply_prompt(telegram,OWNER,data.split(':')[1])
        elif data.startswith(('fetchadd:','fetchskip:')):
            result = approve_candidate(data.split(':',1)[1], data.startswith('fetchadd'))
            try:
                telegram('editMessageCaption',chat_id=OWNER,message_id=message.get('message_id'),caption=(message.get('caption','') or '')[:180]+'\n\n→ '+result)
            except TelegramError:
                reply(OWNER, result)
    except (TelegramError,chat_service.ChatError,KeyError):
        pass


def gallery_stats():
    with database() as db:
        total = db.execute('SELECT COUNT(*) FROM media').fetchone()[0]
        uploaded = db.execute("SELECT COUNT(*) FROM media WHERE source='telegram'").fetchone()[0]
        kinds = {row['kind']: row['n'] for row in db.execute('SELECT kind,COUNT(*) AS n FROM media GROUP BY kind')}
        stickers = db.execute("SELECT COUNT(*) FROM media WHERE kind='sticker' OR id IN (SELECT substr(key,10) FROM state WHERE key LIKE 'category:%' AND value='sticker')").fetchone()[0]
        queued = db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','processing')").fetchone()[0]
    return f'Total stored: {total}\nYour uploads: {uploaded}\nImages / GIFs: {kinds.get("image",0)} · Videos: {kinds.get("video",0)}\nStickers: {stickers} (may also count as images/videos)\nAudio: {kinds.get("audio",0)} · Other: {kinds.get("file",0)}\nQueue: {queued}'


def vision_status():
    return f'Vision: {setting("vision_enabled", "off")}\nKey: {"configured" if setting("vision_key") else "not configured"}\nModel: {setting("vision_model", vision.DEFAULT_MODEL)}\nEndpoint: {setting("vision_url", vision.DEFAULT_URL)}'


def classify_media(path):
    return vision.classify(path, setting('vision_key'), setting('vision_url', vision.DEFAULT_URL), setting('vision_model', vision.DEFAULT_MODEL))


def local_sort_status():
    status = LOCAL_SORT.status()
    refs = ' · '.join(f'{name}: {count}' for name,count in status['references'].items())
    return f'OpenCV YuNet + SFace · offline\nEnabled: {setting("local_sort_enabled", "off")}\nReady: {"yes" if status["ready"] else "references/models needed"}\nReferences: {refs}\nUncertain faces remain in All seven. /learn latest MEMBER adds a clear reference.'


def sort_local_pending(chat):
    if not SORT_LOCK.acquire(blocking=False):
        reply(chat, 'A sorting pass is already running.')
        return
    try:
        with database() as db:
            rows = [dict(row) for row in db.execute("SELECT id,filename FROM media WHERE source='telegram' AND kind='image' AND member='all' AND id NOT IN (SELECT substr(key,8) FROM state WHERE key LIKE 'hidden:%' AND value='on') ORDER BY created")]
        notification = telegram('sendMessage', chat_id=chat, text=f'Offline sorting · {len(rows)} photos\nMatching locally; original files stay untouched.')
        matched = errors = checked = 0
        last_update = 0
        for row in rows:
            if setting('local_sort_enabled','off') != 'on':
                break
            try:
                result = LOCAL_SORT.classify(DOWNLOAD / row['filename'])
                if result['members']:
                    with database() as db:
                        cursor=db.execute("UPDATE media SET member=? WHERE id=? AND member='all'", (','.join(result['members']),row['id']))
                        matched += cursor.rowcount
                set_setting('local-result:'+row['id'],json.dumps(result))
            except LocalSortError:
                errors += 1
            checked += 1
            if time.time()-last_update > 6:
                try:
                    telegram('editMessageText',chat_id=chat,message_id=notification['message_id'],text=f'Offline sorting · {checked}/{len(rows)}\nMatched: {matched} · Uncertain: {checked-matched-errors} · Errors: {errors}\nOriginal images are unchanged.')
                except TelegramError:
                    pass
                last_update=time.time()
        telegram('editMessageText',chat_id=chat,message_id=notification['message_id'],text=f'Local sorting complete 💜\nChecked: {checked}/{len(rows)}\nMatched: {matched} · Uncertain: {checked-matched-errors} · Errors: {errors}\nUse /tag to correct a result, or /learn latest MEMBER to improve references.')
    except TelegramError:
        pass
    finally:
        SORT_LOCK.release()


def rescan_pending(chat):
    if not SORT_LOCK.acquire(blocking=False):
        reply(chat, 'A sorting pass is already running.')
        return
    message_id = None
    try:
        with database() as db:
            rows = db.execute("SELECT id,preview FROM media WHERE member='all' AND kind='image' AND source='telegram' AND id NOT IN (SELECT substr(key,8) FROM state WHERE key LIKE 'hidden:%' AND value='on') ORDER BY created").fetchall()
        result = telegram('sendMessage', chat_id=chat, text=f'Sorting {len(rows)} unassigned photos… 💜\nOne progress message, updated as we go.')
        message_id = result['message_id']
        matched = errors = processed = 0
        last_edit = 0
        for row in rows:
            if setting('vision_enabled', 'off') != 'on':
                break
            try:
                tags = classify_media(DOWNLOAD / row['preview'])
                if tags:
                    with database() as db:
                        cursor = db.execute("UPDATE media SET member=? WHERE id=? AND member='all'", (','.join(tags), row['id']))
                        matched += cursor.rowcount
            except vision.VisionError:
                errors += 1
            processed += 1
            if time.time() - last_edit > 5:
                try:
                    telegram('editMessageText', chat_id=chat, message_id=message_id, text=f'Sorting: {processed}/{len(rows)}\nMatched: {matched} · Uncertain: {processed-matched-errors} · Errors: {errors}')
                except TelegramError:
                    pass
                last_edit = time.time()
        telegram('editMessageText', chat_id=chat, message_id=message_id, text=f'Sorting finished 💜\nChecked: {processed}/{len(rows)}\nMatched: {matched} · Uncertain: {processed-matched-errors} · Errors: {errors}\nUncertain photos stay in All seven. /tag can correct a result.')
    except TelegramError:
        pass
    finally:
        SORT_LOCK.release()


def api_command(chat, parts):
    args = parts[1:]
    action = args[0].lower() if args else 'status'
    if action == 'key' and len(args) == 2:
        set_setting('vision_key', args[1])
        reply(chat, 'Key saved privately. It is never exposed on the site or repeated here. Set /api model and /api url if needed, then /api on.')
    elif action == 'url' and len(args) == 2:
        if vision.valid_endpoint(args[1]):
            set_setting('vision_url', args[1])
            reply(chat, 'HTTPS chat-completions endpoint saved.')
        else:
            reply(chat, 'Use a full HTTPS chat-completions endpoint without credentials, query parameters or fragments.')
    elif action == 'model' and len(args) == 2:
        set_setting('vision_model', args[1])
        reply(chat, 'Vision model saved.')
    elif action in ('on', 'off') and len(args) == 1:
        if action == 'on' and not setting('vision_key'):
            reply(chat, 'First configure /api key YOUR_KEY. Optional: /api url ENDPOINT and /api model MODEL. Then /api on sends unlabelled photos to your provider for member sorting.')
        else:
            set_setting('vision_enabled', action)
            reply(chat, 'Vision sorting ' + action + '. ' + ('Unlabelled photos in auto mode will be sent to your configured provider. To sort earlier uploads: /sort pending.' if action == 'on' else 'Caption/filename sorting still works.'))
    elif action == 'clear':
        set_setting('vision_enabled', 'off')
        set_setting('vision_key', '')
        reply(chat, 'Key removed and vision disabled.')
    elif action == 'test':
        if not setting('vision_key'):
            reply(chat, 'Configure /api key first.')
            return
        def test():
            with database() as db:
                row = db.execute("SELECT preview FROM media WHERE kind='image' ORDER BY created DESC LIMIT 1").fetchone()
            if not row:
                reply(chat, 'Upload a photo first.')
                return
            try:
                result = classify_media(DOWNLOAD / row['preview'])
                reply(chat, 'Provider connected. Latest photo: ' + (', '.join(result) if result else 'uncertain; left unassigned') + '. No album was changed.')
            except vision.VisionError as error:
                reply(chat, str(error))
        threading.Thread(target=test, daemon=True).start()
    else:
        reply(chat, vision_status() + '\n\nUse /api key KEY, /api model MODEL, /api url HTTPS_ENDPOINT, /api on, /api off, /api test or /api clear. A vision-capable OpenAI-compatible service is required. Enabling it sends unlabelled photos to that provider.')


def handle_command(chat, text, message=None, update_id=None):
    if chat != OWNER:
        return False
    parts = text.strip().split()
    if not parts or not parts[0].startswith('/'):
        return False
    command = parts[0].split('@')[0].lower()
    args = [arg.lower() for arg in parts[1:]]
    if command in ('/start', '/panel', '/help', '/cmds'):
        try:
            owner_panel('cmds' if command in ('/help','/cmds') else 'home')
        except TelegramError:
            reply(chat, HELP)
    elif command == '/chats':
        try:
            owner_panel('chats')
        except TelegramError:
            reply(chat, CHAT.recent())
    elif command == '/chatlog':
        try:
            if len(parts) != 2:
                raise chat_service.ChatError('Use /chatlog ID.')
            reply(chat, CHAT.owner_history(parts[1]))
        except chat_service.ChatError as error:
            reply(chat, str(error))
    elif command == '/chat':
        try:
            pieces = text.strip().split(None, 2)
            if len(pieces) < 2:
                raise chat_service.ChatError('Use /chat PV-ID your reply, or reply directly to a website message notification.')
            quoted = (message or {}).get('reply_to_message', {})
            mapped = CHAT.quoted_message(quoted.get('message_id', 0))
            body = pieces[2] if len(pieces) == 3 else quoted.get('text', '') if quoted.get('from', {}).get('id') == OWNER else ''
            target = pieces[1].upper()
            if mapped and mapped['visitor_id'] != target:
                raise chat_service.ChatError('The quoted message is from another visitor. Use the matching chat ID, or send a fresh /chat command.')
            event = f'update:{update_id}' if update_id is not None else 'manual:' + uuid.uuid4().hex
            CHAT.owner_send(target, body, event, mapped['id'] if mapped else None)
            reply(chat, f'Reply saved for {target} 💜 Only that browser conversation can see it.')
        except chat_service.ChatError as error:
            reply(chat, str(error))
    elif command == '/api':
        api_command(chat, parts)
    elif command == '/name':
        raw=text.strip().split(None,1)
        if len(raw)==1:
            recipient=birthday_names.current(setting)
            reply(chat,f'Birthday name: {recipient["name"]}\nKorean display: {recipient["koreanName"]}\n\nUse /name Name\nOptional: /name Name | Korean spelling\nThe custom apology paragraphs are not rewritten.')
        else:
            try:
                recipient=birthday_names.parse(raw[1])
                with database() as db:
                    db.executemany('INSERT OR REPLACE INTO state VALUES (?,?)',[('birthday_name',recipient['name']),('birthday_name_korean',recipient['koreanName'])])
                reply(chat,f'Birthday name updated 💜\n{recipient["name"]} · {recipient["koreanName"]}\nThe birthday, Korea world and card labels update automatically. Refresh to redraw an already-open scratch card.')
            except ValueError as error:
                reply(chat,str(error))
    elif command == '/surprise':
        if args and args[0] in ('today','auto','off') and len(args)==1:
            configure_surprise(args[0])
        try:
            owner_panel('surprise')
        except TelegramError:
            reply(chat,'Use /surprise today, /surprise auto or /surprise off. Preview anytime at http://localhost:8000/surprise. The automatic date is 10 October in IST.')
    elif command == '/local':
        if args in (['on'],['off']):
            if args==['on'] and not LOCAL_SORT.status()['ready']:
                reply(chat,'The local engine needs models and reference photos first. '+local_sort_status())
            else:
                set_setting('local_sort_enabled',args[0])
                reply(chat,local_sort_status())
        else:
            reply(chat,local_sort_status())
    elif command == '/learn':
        if len(args)!=2 or args[1] not in MEMBERS:
            reply(chat,'Use /learn latest v or /learn FILE_ID jimin. The image must contain one clear face.')
        else:
            with database() as db:
                row=db.execute("SELECT id,filename FROM media WHERE source='telegram' AND kind='image' ORDER BY created DESC LIMIT 1").fetchone() if args[0]=='latest' else db.execute("SELECT id,filename FROM media WHERE id=? AND kind='image'",(args[0],)).fetchone()
            try:
                if not row:
                    raise LocalSortError('No matching image found.')
                LOCAL_SORT.add_reference(DOWNLOAD/row['filename'],args[1],row['id'])
                with database() as db:
                    db.execute('UPDATE media SET member=? WHERE id=?',(args[1],row['id']))
                reply(chat,'Reference learned locally 💜 '+args[1]+'\nFuture images can now match this face. Originals were not modified.')
            except LocalSortError as error:
                reply(chat,str(error))
    elif command == '/sort':
        if args == ['local']:
            if not LOCAL_SORT.status()['ready']:
                reply(chat,local_sort_status())
            else:
                set_setting('local_sort_enabled','on')
                threading.Thread(target=sort_local_pending,args=(chat,),daemon=True).start()
        elif args != ['pending']:
            reply(chat, 'Use /sort local for offline matching, or /sort pending for your configured external provider.')
        elif setting('vision_enabled', 'off') != 'on' or not setting('vision_key'):
            reply(chat, 'Configure your vision provider with /api first, then /api on.')
        else:
            threading.Thread(target=rescan_pending, args=(chat,), daemon=True).start()
    elif command == '/fetch':
        if not args or args[0] not in ('all', *MEMBERS):
            reply(chat, 'Use /fetch jimin (or rm, jin, suga, jhope, jimin, v, jungkook, all) — finds good-quality public photos and sends them for your approval.')
        else:
            member = args[0]
            count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 3
            count = min(count, 6)
            reply(chat, f'Searching fresh photos for {member}… 💜')
            threading.Thread(target=fetch_and_suggest, args=(member, count), daemon=True).start()
    elif command == '/stats':
        reply(chat, gallery_stats())
    elif command == '/progress':
        with database() as db:
            row = db.execute('SELECT id FROM batches WHERE chat_id=? ORDER BY received DESC LIMIT 1', (chat,)).fetchone()
        if row:
            publish_batch(row['id'], force=True)
        else:
            reply(chat, 'No upload batch yet. Send multiple photos, videos or stickers to begin.')
    elif command == '/sorry':
        if args not in (['on'], ['off']):
            reply(chat, 'Use /sorry on or /sorry off.')
        else:
            set_setting('sorry_enabled', args[0])
            reply(chat, 'One-time note gift enabled in /korea 💜 The first open hides it and sends you the visitor ID.' if args[0] == 'on' else 'Note hidden. The gift and direct note access are unavailable.')
    elif command == '/member':
        if len(args) != 1 or args[0] not in ('auto', 'all', *MEMBERS):
            reply(chat, 'Use /member auto, all, rm, jin, suga, jhope, jimin, v or jungkook.')
        else:
            set_setting('upload_member', args[0])
            reply(chat, 'Upload destination: ' + args[0] + '. New uploads will appear in the matching profiles automatically 💜')
    elif command == '/status':
        reply(chat, f'Connected 💜\nNote: {setting("sorry_enabled", "on")}\nUpload mode: {setting("upload_member", "auto")}\nVision: {setting("vision_enabled", "off")}\n{gallery_stats()}\nLocal site: http://localhost:8000')
    elif command == '/recent':
        with database() as db:
            rows = db.execute("SELECT id,title,member FROM media WHERE source='telegram' ORDER BY created DESC LIMIT 10").fetchall()
        reply(chat, '\n\n'.join(f'{r["id"]}\n{r["title"][:60]} → {r["member"]}' for r in rows) or 'No uploads yet.')
    elif command in ('/tag', '/hide', '/show'):
        if not args or (command == '/tag' and len(args) != 2) or (command != '/tag' and len(args) != 1):
            reply(chat, 'Use /tag latest jimin, /tag latest10 jimin (last 10 at once), /hide latest, or /show FILE_ID. Use /recent to see IDs.')
            return True
        count = 1
        target = args[0]
        if target.startswith('latest') and target[6:].isdigit():
            count = min(int(target[6:]), 50)
            target = 'latest'
        with database() as db:
            rows = db.execute("SELECT id FROM media WHERE source='telegram' ORDER BY created DESC LIMIT ?", (count,)).fetchall() if target == 'latest' else [db.execute("SELECT id FROM media WHERE id=? AND source='telegram'", (target,)).fetchone()]
        rows = [r for r in rows if r]
        if not rows:
            reply(chat, 'Upload not found. Use /recent to see your upload IDs.')
        elif command == '/tag':
            tags = list(dict.fromkeys(args[1].split(',')))
            if any(tag not in ('all', *MEMBERS) for tag in tags):
                reply(chat, 'Unknown member. Choose rm, jin, suga, jhope, jimin, v, jungkook or all.')
            else:
                with database() as db:
                    for row in rows:
                        db.execute('UPDATE media SET member=? WHERE id=?', (','.join(tags), row['id']))
                if len(rows) == 1:
                    reply(chat, 'Updated 💜 This memory now appears in: ' + ', '.join(tags))
                else:
                    reply(chat, f'Updated 💜 {len(rows)} memories now appear in: ' + ', '.join(tags))
        else:
            for row in rows:
                set_setting('hidden:' + row['id'], 'on' if command == '/hide' else 'off')
            reply(chat, (f'Hidden {len(rows)} from the site. Originals kept in Download.' if command == '/hide' else f'Restored {len(rows)} to the site 💜') if len(rows) > 1 else ('Hidden from the site. Original kept in Download.' if command == '/hide' else 'Restored to the site 💜'))
    else:
        reply(chat, 'Unknown command. Send /help for your private controls.')
    return True


def fetch_and_suggest(member, count):
    """Fetch candidate photos and send them to the owner with Approve buttons."""
    try:
        import fetch_photos
        candidates = fetch_photos.search(member, count)
    except Exception as error:
        reply(OWNER, f'Photo search failed: {type(error).__name__}')
        return
    if not candidates:
        reply(OWNER, f'No new photos found for {member} right now. Try again later or another member.')
        return
    with database() as db:
        known = {row[0] for row in db.execute("SELECT id FROM media").fetchall()}
    fresh = [c for c in candidates if c['id'] not in known]
    if not fresh:
        reply(OWNER, f'All found photos for {member} are already in the library 💜')
        return
    sent = 0
    for item in fresh:
        try:
            image = fetch_photos.requests.get(item['url'], timeout=60)
            image.raise_for_status()
            content_type = image.headers.get('content-type', '')
            if 'image' not in content_type:
                continue
            if len(image.content) < 10000:  # skip tiny/broken images
                continue
            telegram('sendPhoto', chat_id=OWNER, photo=image.content,
                     caption=f"📸 Candidate for {member}\nSource: {item['filename'][:60]}",
                     reply_markup={'inline_keyboard': [[
                         {'text': '✅ Add to site', 'callback_data': 'fetchadd:' + item['id']},
                         {'text': '❌ Skip', 'callback_data': 'fetchskip:' + item['id']},
                     ]]})
            with database() as db:
                db.execute('INSERT OR REPLACE INTO state VALUES (?,?)', ('cand:' + item['id'], member + '|' + item['url']))
            sent += 1
        except Exception as error:
            print(f'fetch candidate failed: {item["url"][:80]} -> {type(error).__name__}', flush=True)
            continue
    if sent:
        reply(OWNER, f'Sent {sent} candidates for {member}. Approve to publish 💜')
    else:
        reply(OWNER, f'Found {len(fresh)} photos for {member} but none could be downloaded right now (sources busy). Try again in a minute, or /fetch another member.')


def approve_candidate(identity, approve):
    with database() as db:
        row = db.execute('SELECT value FROM state WHERE key=?', ('cand:' + identity,)).fetchone()
        db.execute('DELETE FROM state WHERE key=?', ('cand:' + identity,))
    if not row:
        return 'This candidate expired. Use /fetch again.'
    member, url = row[0].split('|', 1)
    if not approve:
        return 'Skipped. Send /fetch member for more options.'
    import fetch_photos
    try:
        image = fetch_photos.requests.get(url, timeout=60)
        image.raise_for_status()
        target = DOWNLOAD / (identity + '.jpg')
        target.write_bytes(image.content)
        add_media(target, identity, 'A little more than a photograph · freshly found', member, 'wikimedia')
        return f'Added to {member} 💜 Live on the site now.'
    except Exception as error:
        return f'Download failed: {type(error).__name__}. Try again with /fetch.'


def configure_surprise(action):
    if action == 'today':
        set_setting('surprise_mode','auto')
        set_setting('surprise_preview_date',personal_birthday.today())
    elif action == 'auto':
        set_setting('surprise_mode','auto')
        set_setting('surprise_preview_date','')
    elif action == 'off':
        set_setting('surprise_mode','off')


def add_media(path, identity, title, member='all', source='telegram', credit=''):
    """Keep original downloads; make browser-friendly local previews where possible."""
    ext = path.suffix.lower()
    preview = path.name
    kind = 'file'
    image_metadata = None
    if ext == '.tgs':
        try:
            with gzip.open(path, 'rt') as stream:
                animation = json.load(stream)
            # Telegram stickers should contain vector assets, never remote resources.
            if any(asset.get('p') or asset.get('u') for asset in animation.get('assets', [])):
                raise ValueError('External sticker assets are not supported')
            target = path.with_suffix('.animation.json')
            target.write_text(json.dumps(animation))
            preview, kind = target.name, 'sticker'
        except (OSError, ValueError):
            pass
    else:
        image_metadata = image_quality.inspect(path)
        if image_metadata:
            preview,kind=image_metadata['display_filename'],'image'
        else:
            if ext in ('.mp4', '.webm', '.mov', '.mkv', '.avi', '.m4v', '.mpeg', '.mpg', '.3gp'):
                target = path.with_suffix('.browser.mp4')
                try:
                    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(path), '-vf', r'scale=min(1280\,iw):-2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', str(target)], check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    preview, kind = target.name, 'video'
                except (OSError, subprocess.SubprocessError):
                    if ext in ('.mp4', '.webm'):
                        kind = 'video'
            elif ext in ('.mp3', '.ogg', '.wav', '.m4a', '.flac', '.oga'):
                kind = 'audio'
    with database() as db:
        if captions.is_generic(title):
            db.execute('BEGIN IMMEDIATE')
            existing = {row[0] for row in db.execute('SELECT title FROM media')}
            title = captions.unique_caption(identity, existing)
        db.execute('INSERT OR IGNORE INTO media VALUES (?,?,?,?,?,?,?,?,?)', (identity, path.name, preview, kind, title[:500], member, source, credit, time.time()))
        if image_metadata:
            image_quality.store(db,identity,image_metadata)


class TelegramError(Exception):
    pass


def telegram(method, **params):
    try:
        files = None
        data = {}
        for key, value in params.items():
            if isinstance(value, bytes):
                files = files or {}
                files[key] = ('photo.jpg', value, 'image/jpeg')
            else:
                data[key] = value
        if files:
            response = requests.post(f'https://api.telegram.org/bot{TOKEN}/{method}', data=data, files=files, timeout=90)
        else:
            response = requests.post(f'https://api.telegram.org/bot{TOKEN}/{method}', json=params, timeout=45)
        result = response.json()
    except (requests.RequestException, ValueError):
        raise TelegramError('Telegram network unavailable') from None
    if not result.get('ok'):
        raise TelegramError(result.get('description', 'Telegram request failed'))
    return result['result']


def reply(chat_id, text):
    try:
        telegram('sendMessage', chat_id=chat_id, text=text)
    except TelegramError:
        pass


def media_item(message):
    for category in ('photo', 'video', 'animation', 'sticker', 'document', 'audio', 'voice', 'video_note'):
        if message.get(category):
            return category, message[category][-1] if category == 'photo' else message[category]
    return '', None


def ingest(message, quiet=False):
    if message.get('from', {}).get('id') != OWNER or message.get('chat', {}).get('type') != 'private':
        return
    chat = message['chat']['id']
    if handle_command(chat, message.get('text', '')):
        return
    def finish(status, text, **extra):
        if not quiet:
            reply(chat, text)
        return {'status': status, 'detail': text, **extra}
    category, item = media_item(message)
    if not item:
        return
    if item.get('file_size', 0) > 20 * 1024 * 1024:
        return finish('failed', 'Larger than the 20 MB download limit. Please send a smaller version.')
    identity = hashlib.sha256(item['file_unique_id'].encode()).hexdigest()[:24]
    with database() as db:
        if db.execute('SELECT 1 FROM media WHERE id=?', (identity,)).fetchone():
            return finish('duplicate', 'Already saved in your world 💜')
    try:
        info = telegram('getFile', file_id=item['file_id'])
        remote = info['file_path']
        ext = Path(item.get('file_name', remote)).suffix.lower()
        if category == 'sticker':
            ext = '.tgs' if item.get('is_animated') else '.webm' if item.get('is_video') else '.webp'
        if not re.fullmatch(r'\.[a-z0-9]{1,10}', ext):
            ext = '.bin'
        target = DOWNLOAD / (identity + ext)
        partial = target.with_suffix(ext + '.part')
        try:
            with requests.get(f'https://api.telegram.org/file/bot{TOKEN}/{remote}', stream=True, timeout=60) as response:
                response.raise_for_status()
                size = 0
                with partial.open('wb') as stream:
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > 20 * 1024 * 1024:
                            raise ValueError('Too large')
                        stream.write(chunk)
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        title = message.get('caption') or item.get('file_name') or ('A little purple memory' if category != 'sticker' else 'A little sticker love')
        member = message.get('_destination') or route_member(title + ' ' + item.get('file_name', ''), str(message.get('media_group_id', '')))
        auto = message.get('_auto', setting('upload_member', 'auto') == 'auto')
        api_error = ''
        if member == 'all' and auto and setting('local_sort_enabled','off')=='on' and target.suffix.lower() in ('.jpg','.jpeg','.png','.webp','.avif','.bmp'):
            try:
                result=LOCAL_SORT.classify(target)
                if result['members']:
                    member=','.join(result['members'])
                set_setting('local-result:'+identity,json.dumps(result))
            except LocalSortError:
                pass
        if member == 'all' and auto and setting('vision_enabled', 'off') == 'on' and target.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif', '.heic', '.heif'):
            try:
                detected = classify_media(target)
                if detected:
                    member = ','.join(detected)
            except vision.VisionError as error:
                api_error = str(error)
        clean_title = re.sub(r'#\w+', '', title).strip() or 'A little purple memory'
        add_media(target, identity, clean_title, member)
        set_setting('category:' + identity, category)
        return finish('saved', f'Saved 💜 Album: {member}\nID: {identity}', member=member, api_error=api_error)
    except (TelegramError, requests.RequestException, OSError, ValueError, KeyError):
        return finish('failed', 'Could not download this file. Please resend it.')


BATCH_LOCK = threading.Lock()
BATCH_WINDOW = 8


def accept_update(update):
    """Acknowledge updates only after they are durably queued; never reply to outsiders."""
    if 'callback_query' in update:
        owner_callback(update['callback_query'])
        return
    message = update.get('message', {})
    if message.get('from', {}).get('id') != OWNER or message.get('chat', {}).get('type') != 'private':
        return
    if message.get('text', '').startswith('/'):
        handle_command(OWNER, message['text'], message, update['update_id'])
        return
    quoted = CHAT.quoted_message(message.get('reply_to_message', {}).get('message_id', 0))
    if quoted and message.get('text'):
        try:
            CHAT.owner_send(quoted['visitor_id'], message['text'], f'update:{update["update_id"]}', quoted['id'])
            reply(OWNER, f'Reply saved for {quoted["visitor_id"]} 💜')
        except chat_service.ChatError as error:
            reply(OWNER, str(error))
        return
    category, item = media_item(message)
    if not item:
        return
    now = time.time()
    text = message.get('caption', '') + ' ' + item.get('file_name', '')
    message = dict(message)
    message['_destination'] = route_member(text, str(message.get('media_group_id', '')))
    message['_auto'] = setting('upload_member', 'auto') == 'auto'
    with database() as db:
        if db.execute('SELECT 1 FROM jobs WHERE id=?', (update['update_id'],)).fetchone():
            return
        batch = db.execute('SELECT id FROM batches WHERE chat_id=? AND closed=0 AND received>? ORDER BY received DESC LIMIT 1', (OWNER, now - BATCH_WINDOW)).fetchone()
        batch_id = batch['id'] if batch else uuid.uuid4().hex[:16]
        if not batch:
            db.execute('INSERT INTO batches (id,chat_id,received) VALUES (?,?,?)', (batch_id, OWNER, now))
        else:
            db.execute('UPDATE batches SET received=? WHERE id=?', (now, batch_id))
        db.execute('INSERT INTO jobs (id,batch,message,category,created) VALUES (?,?,?,?,?)', (update['update_id'], batch_id, json.dumps(message), category, now))


def process_next_job():
    with database() as db:
        row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
        if not row:
            return False
        db.execute("UPDATE jobs SET status='processing' WHERE id=?", (row['id'],))
    try:
        message = json.loads(row['message'])
        result = ingest(message, quiet=True) or {'status': 'failed', 'detail': 'Unsupported message'}
        # A retry never publishes a per-file reply, and originals are deduplicated.
        if result['status'] == 'failed' and '20 MB' not in result.get('detail', ''):
            time.sleep(1)
            result = ingest(message, quiet=True) or result
    except Exception:
        result = {'status': 'failed', 'detail': 'Could not process this file. Please resend it.'}
    with database() as db:
        db.execute("UPDATE jobs SET status='done',result=? WHERE id=?", (json.dumps(result), row['id']))
    return True


def batch_snapshot(batch_id, now=None):
    now = time.time() if now is None else now
    with database() as db:
        batch = db.execute('SELECT * FROM batches WHERE id=?', (batch_id,)).fetchone()
        rows = db.execute('SELECT category,status,result FROM jobs WHERE batch=? ORDER BY id', (batch_id,)).fetchall()
    if not batch:
        return None
    total = len(rows)
    done = [json.loads(row['result']) for row in rows if row['status'] == 'done']
    counts = {key: sum(r.get('status') == key for r in done) for key in ('saved', 'duplicate', 'failed')}
    sorted_count = sum(r.get('status') == 'saved' and r.get('member', 'all') != 'all' for r in done)
    api_errors = sum(bool(r.get('api_error')) for r in done)
    complete = len(done) == total and now - batch['received'] >= BATCH_WINDOW
    percent = round(100 * len(done) / total) if total else 0
    bar = '█' * (percent // 10) + '░' * (10 - percent // 10)
    category_counts = {category: sum(row['category'] == category for row in rows) for category in set(row['category'] for row in rows)}
    labels = ' · '.join(f'{n} {category}' for category, n in sorted(category_counts.items()))
    text = (f'{"Batch complete" if complete else "Collecting & saving"} 💜\n{bar} {percent}%\n'
            f'Received: {total} · Processed: {len(done)}/{total}\n{labels}\n'
            f'Saved: {counts["saved"]} · Already saved: {counts["duplicate"]} · Failed: {counts["failed"]}\n'
            f'In member profiles: {sorted_count} · All seven: {counts["saved"]-sorted_count}\n')
    if api_errors:
        text += f'Vision unavailable for {api_errors}; files still saved. Check /api.\n'
    if counts['failed']:
        reasons = list(dict.fromkeys(r.get('detail', 'Failed') for r in done if r.get('status') == 'failed'))[:2]
        text += '\n'.join(reasons) + '\n'
    text += '\n' + gallery_stats()
    if complete:
        text += '\n\nReady on the site. /cmds for private controls.'
    return {'batch': dict(batch), 'text': text, 'complete': complete, 'total': total, 'processed': len(done), **counts}


def publish_batch(batch_id, force=False):
    with BATCH_LOCK:
        snapshot = batch_snapshot(batch_id)
        if not snapshot:
            return
        batch, text = snapshot['batch'], snapshot['text']
        now = time.time()
        if not force and (now - batch['last_edit'] < 4 or (not batch['message_id'] and now - batch['received'] < 1.5)):
            return
        if text == batch['last_text']:
            return
        try:
            if batch['message_id']:
                telegram('editMessageText', chat_id=batch['chat_id'], message_id=batch['message_id'], text=text)
                message_id = batch['message_id']
            else:
                result = telegram('sendMessage', chat_id=batch['chat_id'], text=text, disable_notification=True)
                message_id = result['message_id']
            with database() as db:
                db.execute('UPDATE batches SET message_id=?,last_edit=?,last_text=?,closed=? WHERE id=?', (message_id, now, text, int(snapshot['complete']), batch_id))
        except (TelegramError, KeyError):
            with database() as db:
                db.execute('UPDATE batches SET last_edit=? WHERE id=?', (now, batch_id))


def upload_worker():
    while True:
        try:
            if not process_next_job():
                time.sleep(.5)
        except Exception:
            time.sleep(2)


def progress_worker():
    while True:
        try:
            with database() as db:
                rows = db.execute('SELECT id FROM batches WHERE closed=0').fetchall()
            for row in rows:
                publish_batch(row['id'])
        except Exception:
            pass
        time.sleep(1)


def chat_worker():
    while True:
        try:
            sent=False
            if TOKEN and OWNER:
                sent=CHAT.relay_next(telegram, OWNER)
                sent=ACTIVITY.relay_next(telegram,OWNER) or sent
            if sent:
                time.sleep(.35)
            else:
                time.sleep(1)
        except Exception:
            time.sleep(3)


def bot_loop():
    if not TOKEN or not OWNER:
        BOT_STATUS.update(message='Bot not configured')
        return
    while True:
        try:
            me = telegram('getMe')
            webhook = telegram('getWebhookInfo')
            if webhook.get('url'):
                BOT_STATUS.update(connected=False, message='Bot has an existing webhook; polling not started')
                return
            BOT_STATUS.update(connected=True, username=me['username'], message='Ready for uploads')
            try:
                telegram('deleteMyCommands', scope={'type': 'default'})
                telegram('setMyCommands', scope={'type': 'chat', 'chat_id': OWNER}, commands=[{'command': name, 'description': description} for name, description in [('panel','Your private control room'),('cmds','All owner-only commands'),('name','Name — birthday person’s display name'),('surprise','today, auto or off — October 10 celebration'),('chats','Recent private website conversations'),('chat','ID message — reply privately to a visitor'),('chatlog','ID — view recent conversation history'),('sorry','on or off — control the note'),('member','auto or a member name — choose upload album'),('local','Offline OpenCV image matching'),('learn','latest MEMBER — teach a reference face'),('api','Optional external vision API'),('sort','local or pending — classify earlier photos'),('stats','Total files and upload counts'),('progress','Update the batch progress message'),('tag','latest jimin — change an upload album'),('recent','Your latest upload IDs'),('hide','latest — hide an upload'),('show','FILE_ID — restore an upload'),('status','Current settings')]])
            except TelegramError:
                pass
            with database() as db:
                row = db.execute("SELECT value FROM state WHERE key='offset'").fetchone()
                offset = int(row[0]) if row else 0
            while True:
                updates = telegram('getUpdates', offset=offset, timeout=30, allowed_updates=['message','callback_query'])
                for update in updates:
                    accept_update(update)
                    offset = update['update_id'] + 1
                    with database() as db:
                        db.execute("INSERT OR REPLACE INTO state VALUES ('offset',?)", (str(offset),))
        except TelegramError as error:
            BOT_STATUS.update(connected=False, message=str(error))
            time.sleep(10)
        except Exception:
            BOT_STATUS.update(connected=False, message='Importer retrying')
            time.sleep(10)


class Handler(BaseHTTPRequestHandler):
    def chat_identity(self):
        try:
            cookie = SimpleCookie()
            cookie.load(self.headers.get('Cookie', ''))
            value = cookie.get(chat_service.COOKIE_NAME)
            return CHAT.authenticate(value.value) if value else None
        except (CookieError, ValueError):
            return None

    def do_POST(self):
        path = unquote(urlsplit(self.path).path)
        if path not in ('/api/chat/session','/api/chat/messages','/api/chat/visit','/api/chat/read','/api/chat/note/open'):
            return self.send_error(404)
        try:
            origin = self.headers.get('Origin')
            if self.headers.get('X-Chat-Request') != '1' or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                raise chat_service.ChatError('This request must come from your chat window.', 403)
            if origin and (urlsplit(origin).scheme not in ('http', 'https') or urlsplit(origin).netloc != self.headers.get('Host')):
                raise chat_service.ChatError('Cross-site chat requests are not allowed.', 403)
            if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
                raise chat_service.ChatError('Send a JSON chat request.', 415)
            try:
                length = int(self.headers.get('Content-Length', '-1'))
            except ValueError:
                length = -1
            if length < 0 or length > 24000:
                raise chat_service.ChatError('The request is too large or has an invalid length.', 413)
            try:
                payload = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError):
                raise chat_service.ChatError('Invalid JSON.') from None
            if not isinstance(payload, dict):
                raise chat_service.ChatError('Invalid chat request.')
            identity = self.chat_identity()
            if path == '/api/chat/session':
                if identity:
                    return self.json_response({'active': True, 'visitor': identity})
                identity, token = CHAT.create_session(self.client_address[0])
                secure = '; Secure' if os.getenv('CHAT_COOKIE_SECURE') == '1' else ''
                cookie = f'{chat_service.COOKIE_NAME}={token}; Path=/api/chat; Max-Age=31536000; HttpOnly; SameSite=Strict{secure}'
                return self.json_response({'active': True, 'visitor': identity}, status=201, headers={'Set-Cookie': cookie})
            if not identity:
                raise chat_service.ChatError('Your private session is unavailable. Reconnect to continue.', 401)
            if path=='/api/chat/visit':
                return self.json_response(ACTIVITY.visit(identity['id'],payload.get('request_id'),payload.get('page','/')))
            if path=='/api/chat/read':
                return self.json_response(ACTIVITY.mark_read(identity['id'],payload.get('through_id')))
            if path=='/api/chat/note/open':
                note=json.loads((ROOT/'note.json').read_text())
                return self.json_response(ACTIVITY.open_note(identity['id'],payload.get('request_id'),payload.get('page','/korea'),note))
            result = CHAT.send_visitor(identity['id'], payload.get('text'), payload.get('client_id'), payload.get('reply_to'))
            return self.json_response({'message': result, 'visitor_id': identity['id']}, status=201)
        except chat_service.ChatError as error:
            return self.json_response({'error': str(error)}, status=error.status)

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        path = unquote(urlsplit(self.path).path)
        if path == '/api/chat/session':
            identity = self.chat_identity()
            return self.json_response({'active': bool(identity), 'visitor': identity}, head)
        if path == '/api/chat/notifications':
            identity=self.chat_identity()
            if not identity:return self.json_response({'error':'Private session required.'},head,status=401)
            return self.json_response(ACTIVITY.notifications(identity['id']),head)
        if path == '/api/chat/messages':
            identity = self.chat_identity()
            if not identity:
                return self.json_response({'error': 'Private session required.'}, head, status=401)
            params = parse_qs(urlsplit(self.path).query)
            try:
                result = CHAT.history(identity['id'], params.get('after', [None])[0], params.get('before', [None])[0])
                result['visitor_id'] = identity['id']
                return self.json_response(result, head)
            except chat_service.ChatError as error:
                return self.json_response({'error': str(error)}, head, status=error.status)
        if path == '/api/media':
            with database() as db:
                media = [dict(row) for row in db.execute("SELECT m.id,m.filename,m.preview,m.kind,m.title,m.member,m.created,COALESCE((SELECT value FROM state WHERE key='category:' || m.id),'') AS category,i.width,i.height,i.orientation,i.original_bytes FROM media m LEFT JOIN image_info i ON i.media_id=m.id WHERE m.id NOT IN (SELECT substr(key,8) FROM state WHERE key LIKE 'hidden:%' AND value='on') ORDER BY m.created DESC")]
            for item in media:
                item['members'] = item['member'].split(',')
            return self.json_response({'media': media}, head)
        if path=='/api/korea':
            return self.json_response({'photos':korea_assets.public_catalog()},head)
        if path == '/api/settings':
            context=personal_birthday.context(setting('surprise_mode','auto'),setting('surprise_preview_date'))
            context['recipient']=birthday_names.current(setting)
            return self.json_response({'noteEnabled': setting('sorry_enabled', 'on') == 'on', 'personalBirthday': context}, head)
        if path in ('/sorry', '/sorry/', '/api/note'):
            if path=='/api/note':
                return self.json_response({'error':'Open the one-time note through the gift.'},head,status=404)
            if setting('sorry_enabled', 'on') != 'on':
                return self.send_error(404)
            return self.file(ROOT / 'site.html', head, private=True)
        if path in ('/', '/world', '/world/') or path.rstrip('/') in READING_PAGES or path.rstrip('/') in {'/music/'+slug for slug in RELEASE_SLUGS} or re.fullmatch(r'/members/(rm|jin|suga|jhope|jimin|v|jungkook)/?', path):
            return self.file(ROOT / 'site.html', head)
        if path in ('/design.css', '/experience.js', '/rooms.css', '/rooms.js', '/magic.css', '/magic.js', '/community.css', '/community.js', '/journey.css', '/journey.js', '/natural.css', '/natural.js', '/surprise.css', '/surprise.js', '/korea.css', '/korea.js', '/visitor.js', '/recipient.js', '/lottie.min.js'):
            return self.file(ROOT / path[1:], head)
        if path.startswith('/Download/'):
            name = path.removeprefix('/Download/')
            if name != Path(name).name or name.startswith('.'):
                return self.send_error(404)
            with database() as db:
                row = db.execute('SELECT m.*,i.mime FROM media m LEFT JOIN image_info i ON i.media_id=m.id WHERE m.filename=? OR m.preview=?', (name, name)).fetchone()
            if row:
                if setting('hidden:' + row['id']) == 'on':
                    return self.send_error(404)
                is_preview = name == row['preview'] and row['kind'] != 'file'
                return self.file(DOWNLOAD / name, head, attachment=not is_preview, cached=True, mime=row['mime'] if name==row['filename'] else None)
            asset=korea_assets.find_file(name)
            if asset:
                return self.file(DOWNLOAD/name,head,cached=True,mime=asset['mime'] if name==asset['filename'] else None)
        self.send_error(404)

    def json_response(self, data, head=False, status=200, headers=None):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if not head:
            self.wfile.write(payload)

    def file(self, path, head, attachment=False, cached=False, private=False, mime=None):
        if not path.is_file():
            return self.send_error(404)
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        value = self.headers.get('Range')
        if value and size:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
            if not match or not any(match.groups()):
                return self.send_error(416)
            first, last = match.groups()
            if first:
                start, end = int(first), min(int(last), end) if last else end
            else:
                start = max(0, size - int(last))
            if start > end or start >= size:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.end_headers()
                return
            status = 206
        self.send_response(status)
        self.send_header('Content-Type', mime or mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(max(0, end - start + 1)))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store' if private else 'public, max-age=31536000, immutable' if cached else 'no-cache')
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        if attachment:
            self.send_header('Content-Disposition', f'attachment; filename="{path.name}"')
        self.end_headers()
        if not head:
            try:
                with path.open('rb') as stream:
                    stream.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        chunk = stream.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def log_message(self, format, *args):
        pass


if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    with database() as db:
        db.execute("UPDATE jobs SET status='queued' WHERE status='processing'")
        captions.migrate(db)
        image_quality.migrate(db,DOWNLOAD)
    try:
        import seed_railway
        seed_railway.main()
    except Exception as error:
        print('seed skipped:', error, flush=True)
    try:
        import shutil
        for name in ('korea_photos.json', 'face_references.json', 'local_sort_validation.json'):
            bundled = ROOT / 'data' / name
            target = DATA / name
            if bundled.exists() and not target.exists():
                shutil.copyfile(bundled, target)
                print(f'{name} restored from bundle', flush=True)
    except Exception as error:
        print('bundled data restore skipped:', error, flush=True)
    if not setting('local_sort_enabled') and LOCAL_SORT.status()['ready']:
        set_setting('local_sort_enabled','on')
    threading.Thread(target=upload_worker, daemon=True).start()
    threading.Thread(target=progress_worker, daemon=True).start()
    threading.Thread(target=bot_loop, daemon=True).start()
    threading.Thread(target=chat_worker, daemon=True).start()
    print('Purple Archive running at http://localhost:8000', flush=True)
    server.serve_forever()
