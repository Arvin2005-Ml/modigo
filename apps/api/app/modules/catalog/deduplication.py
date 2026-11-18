"""Conservative deduplication; do not merge similar but distinct experiences."""
import re
import unicodedata

# Explicitly reviewed aliases. Do not infer equivalence from fuzzy similarity.
ALIASES = {
    'اسموفامیلکوتاه': 'اسمفامیل', 'اسمفامیلکلاسیک': 'اسمفامیل',
    'نقاشیوحدس': 'نقاشیوحدس', 'حدسنقاشیرویکاغذ': 'نقاشیوحدس',
    'بازیبیستسؤالی': 'بیستسوال', 'بازیحدسشیءباسؤال': 'بیستسوال',
    'بازیکلمهممنوع': 'کلمهممنوع', 'حدسواژهباکلماتممنوع': 'کلمهممنوع',
    'نقطهبازیدونفره': 'نقطهوخط', 'بازینقطهوخط': 'نقطهوخط',
    'نبرددریاییکاغذی': 'کشتیجنگی', 'کشتیجنگیکاغذیساده': 'کشتیجنگی',
}


def normalized(text):
    text = unicodedata.normalize('NFKC', text).translate(str.maketrans({'ي':'ی','ك':'ک','\u200c':''})).casefold()
    return re.sub(r'[^\w]', '', text)


def identity(content):
    title = normalized(content['title'])
    title = ALIASES.get(title, title)
    place = content.get('place') or {}
    return (title, content.get('venue'), normalized(place.get('city','')),
            normalized(place.get('name','')))


def existing_identities(store):
    """Include withdrawn records and human-edited revisions; exclude raw/demo fixtures."""
    revisions = store.list('activity_revisions')
    by_activity = {}
    for r in revisions:
        if r.get('content') and r.get('origin') != 'demo':
            by_activity.setdefault(r['activity_id'], []).append(r)
    result = {}
    for activity in store.list('activities'):
        for revision in by_activity.get(activity['id'], []):
            content = revision['content']
            if content.get('title') and content.get('venue'):
                result.setdefault(identity(content), activity['id'])
    return result


def duplicate_records(store):
    """Report pre-existing duplicates without deleting referenced history."""
    grouped = {}
    for revision in store.list('activity_revisions'):
        content = revision.get('content')
        if (not content or revision.get('origin') == 'demo' or
                not content.get('title') or not content.get('venue')):
            continue
        grouped.setdefault(identity(content), set()).add(revision['activity_id'])
    return [sorted(ids) for ids in grouped.values() if len(ids) > 1]
