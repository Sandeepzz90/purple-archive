# Purple Archive

Custom English × Korean BTS fan site with a purple-white design, locally cached photographs, individual member collections, a scrapbook gallery and private upload controls.

## Run

Requires Python 3, `requests`, `Pillow`, and optional `ffmpeg`/`ffprobe` for compatibility handling. Offline member matching uses OpenCV and NumPy in a separate Python worker (configured here as `/usr/bin/python3`).

```sh
python -m pip install requests Pillow
python seed.py
python seed_more.py
python server.py
```

- Home: http://localhost:8000/
- Personal birthday preview: http://localhost:8000/surprise
- Shivani’s Korean world: http://localhost:8000/korea
- Private conversation: http://localhost:8000/chat
- Normal homepage during a birthday preview: http://localhost:8000/?home=1
- Gallery: http://localhost:8000/world
- BTS story: http://localhost:8000/story
- Music guide: http://localhost:8000/music (18 release pages, e.g. `/music/wings`)
- Era guide: http://localhost:8000/eras
- Facts, quiz and solo listening paths: http://localhost:8000/discover
- Birthday calendar and quests: http://localhost:8000/birthdays
- Member directory: http://localhost:8000/members
- Apology note: http://localhost:8000/sorry
- Profiles: `/members/rm`, `/members/jin`, `/members/suga`, `/members/jhope`, `/members/jimin`, `/members/v`, `/members/jungkook`

The server listens on port 8000 on all local network interfaces. No domain is required.

## Telegram

The private `.env` file contains `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OWNER_ID`. The server never serves this file or its source/database over HTTP. Only private messages from the configured owner are imported. A bot already using a webhook is left alone and reported in the gallery status.

Send `/cmds` to the bot, then send photos, videos, GIFs, stickers, audio, or documents. Albums and mixed bursts are accepted into a persistent queue immediately. Messages arriving within an 8-second burst share one batch summary. That message is edited at most every 4 seconds with received, processed, saved, duplicate, failed, member-sorted and total-library counts. Individual files do not generate replies. Download/conversion runs in a background worker; unfinished jobs resume after restart.

Captions become gallery titles. Optional tags: `#rm`, `#jin`, `#suga`, `#jhope`, `#jimin`, `#v`, `#jungkook`. Names and common aliases in English or Korean are also recognised in captions and filenames. Multiple names put the same image into multiple member profiles. Albums inherit the first labelled item's destination. Caption/filename sorting works without an external API. Unlabelled uploads go to All seven unless a destination is selected with `/member` or optional vision classification identifies a member. The homepage's new-memory wall, gallery and profile collections check for updates every 10 seconds.

### Private commands

- `/cmds`: all owner-only commands. `/help` and `/start` are aliases. Other users receive no replies, and the default/public command menu is empty.
- `/panel`: formatted owner control room with inline buttons for conversations, uploads, statistics, note visibility, vision setup and command help. Callback actions authenticate both the sender and the private chat.
- `/name Arjun`: change the birthday person's display name (works for a girl or boy). Names with spaces are supported. `/name` alone shows the current setting.
- `/name Arjun | 아르준`: optionally specify a Korean spelling. Without it, unfamiliar names are displayed as entered within the Korean phrases; no phonetic spelling is guessed. Shivani defaults to `시바니`.
- `/surprise today`: temporarily show the personal October 10 celebration on the homepage for the current India calendar day.
- `/surprise auto`: end the temporary preview and keep only the annual October 10 activation.
- `/surprise off`: disable automatic homepage activation. The explicit `/surprise` preview route remains available.
- `/chats`: recent visitor IDs and private conversations, including visitors who have not sent a message yet.
- `/chat PV-ID your reply`: send a reply only to that visitor's conversation.
- `/chatlog PV-ID`: recent messages from that conversation.
- `/sorry on` makes the one-time **“I’m really sorry / 정말 미안해”** gift available in the Korean world. Its first successful open automatically sets the flag off and queues an owner notification with that visitor ID. `/sorry off` hides it manually. Re-enable explicitly before another intended opening.
- `/member auto`: automatic caption/filename routing.
- `/member jimin`: choose the destination for upcoming uploads. Accepts all seven IDs and `all`.
- `/tag latest rm,jin`: reassign the last upload to one or several member collections. An upload ID can replace `latest`.
- `/recent`: list the latest 10 upload IDs.
- `/hide latest`: hide an upload and its media URLs while retaining local files.
- `/show FILE_ID`: restore a hidden upload.
- `/status`: current note setting, destination, stored media count.
- `/stats`: total media, uploaded media, images/GIFs, videos, stickers, audio, other files and queue counts.
- `/progress`: refresh the latest batch's existing progress message.
- `/api`: private vision configuration and usage help.
- `/sort pending`: classify existing unassigned photo uploads with the configured vision service; progress is edited in one message.
- `/local`: status of the offline OpenCV matcher; `/local on` and `/local off` control it.
- `/sort local`: conservatively sort existing unassigned photos on this device.
- `/learn latest v`: add an explicitly labelled, single-face reference; a file ID can replace `latest`.

These commands only work in private messages from the configured owner. Bot details and ingestion metadata are not exposed through public site UI or APIs. The old `/api/status` endpoint is disabled.

### Optional vision sorting

No provider key is bundled. Configure it privately through the bot:

```text
/api key YOUR_PROVIDER_KEY
/api url https://api.openai.com/v1/chat/completions
/api model gpt-4.1-mini
/api on
/member auto
/api test
/sort pending
```

The endpoint and model shown are defaults. Other vision-capable OpenAI-compatible chat-completions services can be configured. `/api test` sends one saved photo without modifying its member tags. `/api on` opts into sending unlabelled photos to the configured external provider; its usage charges may apply. Images are reduced to 1024 pixels and sent as JPEG data. Only allowlisted BTS member IDs with reported confidence of at least 0.90 are accepted. This threshold cannot guarantee perfect identification: unknown/uncertain people remain in All seven, and `/tag` corrects mistakes. Provider failures do not discard uploaded files. Videos and unsupported image formats keep metadata-based routing.

`/api off` disables calls, including the next step of a pending sorting pass. `/api clear` also removes the saved key. Keys are not repeated in bot replies or public responses. Settings and queue data are in the private SQLite database (mode 0600, parent directory 0700). A manually chosen `/member` destination takes priority over automatic classification.

### Offline open-source matching

The site now includes **OpenCV YuNet + SFace**. Official OpenCV Zoo model files are downloaded by `setup_local_sort.py`, verified against their Git LFS SHA-256 values, and kept in `models/` alongside their upstream licences (MIT for YuNet, Apache-2.0 for SFace). `models/manifest.json` records provenance and hashes. The models and reference data are not served by the web server.

```sh
python setup_local_sort.py
python prepare_faces.py
python sort_existing_locally.py
```

The worker needs a Python installation with `cv2` (FaceDetectorYN and FaceRecognizerSF) and NumPy. This environment already provides OpenCV 5 under `/usr/bin/python3`; set `LOCAL_FACE_PYTHON` to use a different interpreter. The website's main Python process does not need to import OpenCV itself.

Reference portraits for all seven members bootstrap the system. Matching uses normalized SFace embeddings, a minimum cosine score of 0.50, and a 0.10 margin over the next member. These are conservative matching thresholds, not percentage probabilities. Unknown, small, obscured or ambiguous faces remain unassigned. Multi-face photos can go into multiple profiles when the faces are confidently matched. `/learn` requires exactly one clear face and an owner-supplied identity; automatic guesses are never added as training references.

Routing order is: manually selected destination, caption/filename labels, local recognition, then an optional external vision service if the owner has explicitly enabled it. Local processing never sends photos off-device, and all recognition resizing/cropping is in memory: the original files are not changed. References and diagnostic match scores stay in the private `data/` directory.

## Public experience

- The homepage is now reduced to an uncluttered photo-led introduction, useful page links, the seven members, six complete photographs, the next birthday and private chat. Decorative games, floating objects, repetitive bento sections and the extra photo strips have been removed from the homepage. The small note link appears only when enabled.
- `/world` separates media into an asymmetric moodboard, scrapbook, contact sheets, a cinema, sticker club, sound room, and keepsakes. Rooms appear when matching media exists. Member/type/saved filters apply to all rooms. Pagination progressively unfolds more frames.
- Hearts are stored in the visitor's browser. New files and retagged profile collections refresh every 10 seconds.
- Birthday dates follow **Asia/Seoul (KST)**. The next member has a countdown and calendar card. On the birthday itself, the welcome message, ribbon, member card and portrait are highlighted; confetti, a cake, and a locally saved birthday wish card are available. Open tabs check for date changes every 30 seconds and when returning from the background. Birthday quests, ages and the days-since-debut counter update automatically; local-hour greetings update too. All seven birthdays are supported, including Jimin on 13 October.
- Reduced-motion preferences disable entrance animations, particles and candle animation. The secret keyboard word `borahae` triggers a small celebration outside input fields.

### Your growing world

`/world` now derives its rooms from the current collection, with a new photo chapter for each six images. Chapters rotate between moodboards, scrapbooks, arch frames, light-box frames, ribbon frames, window frames and contact sheets. Other media also receive their own six-item rooms. Every room is listed immediately; the first rooms are unfolded, while closed rooms populate their cards on demand. The room directory, manual unfolding, type/member filters and automatic 10-second refresh work together. This keeps a large collection browsable without initially loading every full-sized image.

Old generic upload titles are migrated at startup to unique, stable editorial captions. New uncaptained uploads receive the same treatment. Custom captions are preserved. Titles are generated locally, without vision/API calls, and do not claim to describe what is in a photograph.

The homepage uses actual photographs in natural proportions. The future-self postcard, daily time capsule, abstract-object cabinet and constellation are not displayed there. The saved-photo collection remains available through the gallery.

Every fresh page load generates new random image ranks and a new visual seed. The home photo wall, member-card order, portraits, hero arrangement, page illustrations and gallery layout receive a fresh arrangement. A live poll keeps existing ranks stable to avoid moving the page while someone is reading or chatting; new uploads receive new ranks. Member labels stay attached to matching member photos. Reading material and release dates keep their logical order.

The Story, Music, Eras, Discover, Birthdays and Members pages provide distinct reading and interactive experiences. The music guide includes 18 selected historic releases with dedicated internal routes, release dates, context and selected tracks. The era selector, music filters, discovery quiz, birthday selector and member solo-work notes are functional. An exploration navigation row and photo cards connect the pages.

Page-specific entrance scenes finish when content is ready, with a bounded wait for the leading image and an immediate skip button. Fetches time out rather than leaving an indefinite loading screen. There are no fabricated percentage counters. Image fades and section reveals respect reduced-motion settings. Interface copy is personalized toward “you”; the apology note and authored media captions are excluded from copy normalization.

Originals and compatibility copies live in `Download/`. Metadata, image dimensions and the Telegram polling offset persist in `data/gallery.sqlite`. Seed photos download once; the browser loads local files with long-lived caching, not remote photo URLs. Google Fonts has local system-font fallbacks.

The standard Telegram Bot API permits downloads up to 20 MB. **Send photographs as File/Document to avoid Telegram's own photo compression.** Files received by the site are kept byte-for-byte. Native JPEG, PNG, GIF, WebP, AVIF and BMP images are served directly rather than resized/re-encoded JPEG previews. Existing photo records are migrated back to their original files. Native dimensions include EXIF display orientation; portrait, landscape and square filters are available in the gallery.

Every photo layout preserves the complete intrinsic aspect ratio, without `object-fit: cover`, circular masks, enlargement, saturation changes or image rotations. CSS can scale an image down to fit a smaller screen, but does not enlarge small originals. The viewer shows pixel dimensions and file size, with a switch between fitting the complete picture and viewing original pixels in a scrollable surface. Unsupported browser image formats get a full-sized lossless PNG when the decoder supports it; the original always remains downloadable. Video conversion uses FFmpeg where needed. TGS stickers use the local Lottie renderer.

Photo source metadata is retained internally in the database. Public pages contain no attribution/source links. Member descriptions are short original summaries. This is an unofficial fan site. Heart-saved memories are kept locally in the visitor's browser.

## Compact photo placement

Photo collections now use shortest-column masonry placement rather than equal-height rows. A shorter landscape or square card receives the next card directly beneath it, separated only by the normal gutter. Original aspect ratios and native-size limits remain intact. The layout updates when images finish loading, captions/fonts change size, new cards arrive, a gallery room opens, or the viewport changes. Placement keeps DOM order and existing card interactions; it does not resize or re-encode image files.

## Private website chat

The homepage and `/chat` provide a scrollable private conversation with the site owner. The dedicated chat route opens directly to the conversation rather than a large introduction. Every page prepares the same private browser session, so the owner can start a conversation before the visitor types anything. Each browser receives a random public ID such as `PV-A1B2C3D4E5` and a separate 256-bit secret in an HttpOnly, SameSite=Strict cookie scoped to `/api/chat`. Only the secret's hash is stored in the database. A public chat ID alone cannot read a conversation. IP addresses are not identities: browsers on the same Wi-Fi have separate conversations, and an IP change does not change an existing chat. A short-lived per-address session-creation limit is held only in memory.

All visitor and owner messages persist in `chat_messages` inside `data/gallery.sqlite`. The UI loads the latest 60 messages, offers earlier-history pagination, preserves scroll position while reading, and polls for new replies every 3.5 seconds while the tab is visible. Failed sends keep the draft and retry with the same request ID to avoid duplicate site messages. Message text and quotes are escaped and excluded from interface-copy personalization.

Owner replies create an in-page **“A message for you / 메시지가 왔어요”** notice across the site. Tapping it opens `/chat`. Unread state is stored server-side and survives closing/reopening the browser; replies are acknowledged only when the actual chat transcript is visible. No OS/browser push notification permission is requested. Chat and the Korean-world page remain usable independently of the BTS photo-feed endpoint.

Each full page visit (including a return from browser back/forward cache) records one idempotent event with the browser's visitor ID, page path and timestamp. API polling and image requests do not create visit alerts. A durable background queue sends the owner a private visit notification with **Message this visitor** and **Conversation** buttons. Retries reuse the visit ID rather than creating duplicate events. Page paths exclude query strings; IP addresses are not stored in visit records. Visit recording is capped at 30 events per visitor per minute.

Incoming visitor messages are saved before a background worker notifies the owner. The durable outbox retries on network failures and resumes after restart. The website distinguishes “Saved · awaiting delivery” from “Delivered”; it does not claim that a delivered message has been read. Delivery is at-least-once to the owner's messaging service: an ambiguous network timeout after a send can result in a duplicate notification, while the website still retains one message.

Owner reply options:

```text
/chats
/chat PV-A1B2C3D4E5 Hello! This reply is just for you.
/chatlog PV-A1B2C3D4E5
```

Alternatively, use the bot app's normal **Reply** action on a visitor notification and type a response. That response is linked to the quoted visitor message. A `/chat ID text` command quoting a different visitor's notification is rejected to prevent accidentally mixing conversations. `/chat ID` can also forward text from an owner-authored message when issued as a reply to that owner's message. Only the configured owner's private messages can trigger these actions; other users are ignored.

Notifications also have **Reply privately** and **Conversation** buttons. Reply privately creates a targeted reply prompt; its visitor/message mapping is persisted, so a reply to that prompt retains the correct conversation even after restart. Conversation buttons open formatted history cards with refresh and navigation controls. Arbitrary callback text is never executed as a command.

Cookie loss or switching browsers starts a new visitor identity; the old history remains stored, but its public ID is not a recovery credential. For HTTPS hosting behind a reverse proxy, set `CHAT_COOKIE_SECURE=1` and preserve the public `Host` header. Local HTTP on port 8000 works without that setting. Chat mutations require JSON, a same-origin/custom-header request and an authenticated cookie; they are rate-limited to 10 visitor messages per minute.

## Birthday countdown quest

The next member's homepage birthday section and each member profile now include seven countdown doors, opening daily from **D−7 through D−1**, plus a birthday-day finale. For Jimin this means **6–12 October**, then **13 October** for the finale, following KST.

The surprises are a welcome letter, a memory to save, a Korean birthday phrase, a birthplace quiz, cake colours, a personal birthday wish and a favourite musical chapter. Collected seals, cake choice, wish and music choice stay in that browser under a member/year-specific key. Earlier unlocked doors remain available during the countdown. The birthday finale includes a locally generated downloadable SVG keepsake and can be opened even if earlier days were missed. These are date-based local experiences, not protected paid content; they use the visitor's current clock interpreted in KST.

## Personal October 10 surprise

This celebration is separate from the BTS member birthdays. The backend activates it on **10 October, 00:00–23:59 in India (IST / Asia/Kolkata)**, every year, unless the owner selects `/surprise off`. `/surprise today` stores one exact India-calendar date in SQLite; that preview expires at midnight and is not renewed on server restart. `/surprise auto` can end today's demo early.

When active, `/` greets **Shivani / 시바니** with **“Happy Birthday Shivani / 시바니, 생일 축하해!”**. The opening has a personal invitation, tappable balloons and a countdown. The unwanted “main character” wording and the large generic heart-letter section have been removed.

The gift flow is now **scratch card → birthday boarding pass → virtual India-to-South-Korea flight → Korean world**. Scratching or pressing the accessible reveal button uncovers the travel gift. The illustrated flight is a virtual birthday experience, with English/Korean departure and arrival messages. A returning visitor can continue straight to Korea or explicitly replay the flight.

`/surprise` is available outside the birthday date, but opening it again no longer automatically replays the birthday sequence. A durable local marker remembers that the opening has been seen, including migration from earlier session markers. Replay is an explicit button on the birthday page and a link on the normal home tab (`/surprise?replay=1`); the query flag is consumed immediately so reloading does not repeat it. Scratch and journey progress also persist locally. Reduced-motion settings skip the animated countdown/flight while keeping the controls usable. Sound is opt-in only.

The birthday page still works if the photo feed is temporarily unavailable. A date change affects new page loads automatically; existing readers can continue enjoying an already opened celebration without having the page replaced underneath them. A small preview label distinguishes test mode from the real birthday.

### Korean-world photography and hidden gifts

`prepare_korea.py` downloads six Wikimedia travel photos as delivered by the source: India Gate, Seoul, Gyeongbokgung, Bukchon, Busan and Jeju. They are kept locally in `Download/`, separate from the BTS library. Source/provenance records are private in `data/korea_photos.json`; the public API only returns image filenames, dimensions and place labels. The website does not re-encode or crop them.

The Korean world has five photo stops with bilingual hidden wishes and collectible stamps. Finding all five unlocks a Shivani Korean-name birthday card. These are local, playful surprises. The private-message banner is available throughout the journey.

### One-time apology gift

The original apology paragraphs are preserved; the presentation is now **“I’m really sorry / 정말 미안해”**, addressed to Shivani, with a Korean-paper/finger-heart design. It appears as a gift only when enabled. An authenticated browser opens it through `POST /api/chat/note/open`, not through a preloadable GET endpoint. In one SQLite transaction, the first open stores a private receipt, turns the global note flag off and queues the owner notification. Two simultaneous readers cannot both claim the note. A failed response can be retried using the same request ID by the same browser; other browsers cannot retrieve that receipt.

The open reader can finish reading, while the gift/link disappears from the site. Closing the dialog clears its visible content. `/api/note` no longer exposes raw note text; disabled direct `/sorry` requests return 404. Use `/sorry on` again when the note should be available for another opening. Tests use isolated data and mocked delivery rather than consuming the live note.

## Check

The `/name` setting updates the birthday heading, scratch foil, flight, Korean-world labels, BTS invitation and downloaded name card. Existing open pages refresh their labels through the settings poll. Handwritten apology paragraphs, image captions and private chat messages are preserved. Progress and replay markers are separate for different recipients. The birthday date is still October 10.

```sh
python -m unittest test_media.py test_chat.py test_image_quality.py test_personal_birthday.py test_activity.py test_birthday_names.py -v
node --check experience.js
node --check rooms.js
node --check magic.js
node --check community.js
node --check journey.js
node --check natural.js
node --check surprise.js
node --check korea.js
node --check visitor.js
node --check recipient.js
```
