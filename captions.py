"""Individual, stable editorial titles; never invent visual facts about an image."""
import hashlib

GENERIC = {'', 'a little purple memory', 'a little sticker love', 'a little memory', 'untitled'}
BEGINNINGS = (
    'A pocketful of wonder', 'The pause you needed', 'Your tiny happy place',
    'A softer kind of magic', 'A little light to keep', 'An almost-secret smile',
    'The sweetest detour', 'A daydream with your name on it', 'A reason to linger',
    'Your favourite kind of quiet', 'A heart-shaped bookmark', 'The small things, always',
    'A spark you get to keep', 'A little beyond ordinary', 'A moment that chose you',
    'The gentlest little surprise', 'A page from a softer world', 'Your next happy thought',
    'A feeling without a name', 'An extra spoonful of joy', 'A tiny escape hatch',
    'A secret worth smiling about', 'A lovely little coincidence', 'One for your heart',
    'A small constellation of comfort', 'A little more than a photograph',
    'Your soft landing', 'A little piece of almost-forever', 'A bookmark for this feeling',
    'A reason to slow the scroll', 'A keepsake from the in-between', 'The good kind of butterflies',
    'A daydream tucked away', 'A tiny invitation to stay', 'A little magic, on purpose',
    'Your very own plot twist', 'A moment outside the noise', 'A heart doing a little dance',
    'A little room for wonder', 'A favourite you haven’t met yet',
)
ENDINGS = (
    'just for you', 'yours to keep', 'in your own time', 'on a softer day',
    'no occasion needed', 'a little closer', 'where your heart wanders',
    'for the next rainy day', 'without a hurry', 'for your collection',
    'whenever you need it', 'in the little things', 'with a little sparkle',
    'one lovely moment at a time', 'a feeling to revisit', 'for another little look',
    'never quite ordinary', 'somewhere between heartbeats', 'from here to your heart',
    'one to come back to', 'with room for a daydream', 'for your softer side',
    'a little unexpectedly', 'for the version of you here today',
)


def is_generic(title):
    return title.strip().casefold().rstrip('.!♡💜 ').strip() in GENERIC


def unique_caption(identity, existing):
    """Deterministic first choice, collision-resolved against the actual collection."""
    digest = int(hashlib.sha256(identity.encode()).hexdigest(), 16)
    count = len(BEGINNINGS) * len(ENDINGS)
    for attempt in range(count):
        choice = (digest + attempt) % count
        title = BEGINNINGS[choice // len(ENDINGS)] + ' · ' + ENDINGS[choice % len(ENDINGS)]
        if title not in existing:
            return title
    # Even a large collection never needs to reuse a title.
    base = BEGINNINGS[digest % len(BEGINNINGS)]
    serial = len(existing) + 1
    while f'{base} · keepsake {serial:04d}' in existing:
        serial += 1
    return f'{base} · keepsake {serial:04d}'


def migrate(db):
    rows = db.execute('SELECT id,title FROM media ORDER BY created,id').fetchall()
    existing = {row['title'] for row in rows}
    changed = 0
    for row in rows:
        if is_generic(row['title']):
            title = unique_caption(row['id'], existing)
            db.execute('UPDATE media SET title=? WHERE id=?', (title, row['id']))
            existing.add(title)
            changed += 1
    return changed
