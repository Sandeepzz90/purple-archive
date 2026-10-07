"""Owner-configurable birthday display names; no change to authored note text."""
import unicodedata


def parse(value):
    parts=value.split('|')
    if len(parts)>2:
        raise ValueError('Use /name Name or /name Name | Korean spelling.')
    names=[]
    for part in parts:
        raw=part.strip()
        if not raw or len(raw)>50 or any(unicodedata.category(c).startswith('C') for c in raw) or any(c in '<>\\/' for c in raw) or not any(c.isalpha() for c in raw):
            raise ValueError('Use a name of 1–50 characters, without control characters or markup.')
        names.append(' '.join(raw.split()))
    name=names[0]
    korean=names[1] if len(names)==2 else '시바니' if name.casefold()=='shivani' else name
    return {'name':name,'koreanName':korean}


def current(setting):
    name=setting('birthday_name','Shivani')
    return {'name':name,'koreanName':setting('birthday_name_korean','시바니' if name.casefold()=='shivani' else name)}
