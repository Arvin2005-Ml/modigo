"""Authored activities at home or somewhere the user already has access to."""
from functools import lru_cache

from app.modules.catalog.bootstrap import ROOT
from app.modules.catalog.cinema_expansion import import_additive
from app.modules.catalog.deduplication import identity
from app.modules.catalog.schemas import Content

VERSION = 'short_now_v1'
FILE = 'content/short-now.txt'
CONDITIONS = {
    'home': 'در همان جای راحتی که خانه هستی انجامش بده؛ خرید یا آماده‌سازی لازم نیست.',
    'outdoor': 'فقط در فضای بیرونی امن و مجازی که همین حالا در دسترس توست؛ سفر یا ورود تازه لازم نیست.',
    'indoor_public': 'فقط در فضای سرپوشیده‌ای که همین حالا اجازهٔ حضور داری؛ ورود تازه یا خرید لازم نیست.',
}


@lru_cache(maxsize=1)
def short_now_catalog():
    entries = []
    keys, identities = set(), set()
    for line in (ROOT / FILE).read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        (slug, venue, minutes, dimension, mobility, tags, title, teaser,
         first, second, third, lighter, intent) = line.split('|')
        together = dimension == 'affiliation'
        content = Content.model_validate(dict(title=title, teaser=teaser, first_step=first,
            steps=[first, second, third], lighter_version=lighter,
            materials_note='هیچ وسیله یا خریدی لازم نیست.',
            accessibility_note='از جای راحت و مجازِ فعلی شروع کن؛ حرکت یا تغییر مسیر لازم نیست.',
            conditions_note=CONDITIONS[venue], primary_dimension=dimension, secondary_dimensions=[],
            tags=tags.split(',') + (['no_screen'] if venue == 'home' else ['outdoors' if venue == 'outdoor' else 'indoors', 'no_screen']),
            active_minutes=int(minutes), setup_minutes=0, travel_minutes=0, energy_required='low',
            mobility_required=mobility, supported_social_modes=['together' if together else 'solo'],
            min_people=2 if together else 1, max_people=2 if together else 1, venue=venue, required_items=[],
            requires_async_contact=False, step_free=True, quiet_compatible=not together,
            weather_requirement='any', daylight_requirement='any',
            cost=dict(kind='free', min_toman=0, max_toman=0, basis='per_person', verified_at=None,
                      valid_until=None, note='اجرا در محل فعلی هزینهٔ جداگانه ندارد.'),
            safety_notes=[] if venue == 'home' else ['راه عبور را نبند و اگر محیط فعلی مناسب نیست، این فعالیت را رد کن.'],
            place=None, requires_venue_check=False, dramma=dict(version='dramma_v1',
                mechanisms=[dict(dimension=dimension, intent=intent, step_indexes=[2, 3])]))).model_dump()
        key = 'real:short-now-' + slug
        fingerprint = identity(content)
        if key in keys or fingerprint in identities or not 5 <= content['active_minutes'] <= 30:
            raise ValueError('Invalid or duplicate short-now activity')
        keys.add(key)
        identities.add(fingerprint)
        entries.append(dict(key=key, content=content, source_ids=[]))
    return dict(version=VERSION, researched_on=None, sources={}, entries=entries,
                publication_basis='owner_requested_authored_same_place_activities',
                evidence_scope='authored_instructions_no_external_venue')


def import_short_now(store, clock):
    return import_additive(store, clock, short_now_catalog(), version=VERSION, source_file=FILE,
        raw_intent='تجربهٔ کوتاه و تألیفی در همان محل، بدون وسیله و خرید',
        reason='Owner request 2026-11-18: free, short, same-place activities')
