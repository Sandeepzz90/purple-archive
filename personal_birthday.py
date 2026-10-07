"""Calendar policy for the personal October 10 celebration (India time)."""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), 'IST')


def today(now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(IST).date().isoformat()


def context(mode='auto', preview_date='', now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local = now.astimezone(IST)
    date = local.date().isoformat()
    birthday = local.month == 10 and local.day == 10
    preview = preview_date == date
    active = mode != 'off' and (birthday or preview)
    event_year = local.year + int((local.month, local.day) > (10, 10))
    tomorrow = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        'active': active,
        'occasion': 'birthday' if active and birthday else 'preview' if active else 'none',
        'today': date,
        'eventDate': f'{event_year}-10-10',
        'timezone': 'Asia/Kolkata',
        'timezoneLabel': 'IST',
        'previewToday': preview and mode != 'off',
        'expiresAt': tomorrow.timestamp() if active else None,
        'serverNow': now.timestamp(),
    }
