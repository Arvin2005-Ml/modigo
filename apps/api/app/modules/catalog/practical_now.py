"""Authored recreation for the current location, with explicit prerequisites."""
from functools import lru_cache

from app.modules.catalog.bootstrap import ROOT
from app.modules.catalog.cinema_expansion import import_additive
from app.modules.catalog.deduplication import identity
from app.modules.catalog.schemas import Content

VERSION = 'practical_now_v1'
FILE = 'content/practical-now.txt'


@lru_cache(maxsize=1)
def practical_now_catalog():
    entries, keys, fingerprints = [], set(), set()
    for line in (ROOT / FILE).read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        (slug, venue, minutes, setup, dimension, mobility, mode, items, quiet, weather, tags,
         title, teaser, conditions, first, second, third, lighter, intent) = line.split('|')
        key = 'real:practical-now-' + slug
        items = [] if items == '-' else items.split(',')
        modes = ['solo', 'together'] if mode == 'both' else [mode]
        content = Content.model_validate(dict(
            title=title, teaser=teaser, first_step=first, steps=[first, second, third],
            lighter_version=lighter, primary_dimension=dimension, secondary_dimensions=[],
            tags=tags.split(','), active_minutes=int(minutes), setup_minutes=int(setup), travel_minutes=0,
            energy_required='low' if mobility != 'active' else 'medium', mobility_required=mobility,
            supported_social_modes=modes, min_people=1 if 'solo' in modes else 2,
            max_people=2 if 'together' in modes else 1, venue=venue, required_items=items,
            materials_note='از وسایلی که از قبل دم‌دستت هستند استفاده کن.' if items else 'وسیلهٔ خاصی لازم نیست.',
            accessibility_note='فقط اگر فضای فعلی و حرکت‌های گفته‌شده برایت مناسب‌اند شروع کن.',
            conditions_note=conditions, requires_async_contact=False, step_free=None,
            quiet_compatible={'yes': True, 'no': False}[quiet], weather_requirement=weather,
            daylight_requirement='day' if venue == 'outdoor' and mobility != 'seated' else 'any',
            cost=dict(kind='free', min_toman=0, max_toman=0, basis='per_person', verified_at=None,
                      valid_until=None, note='در محل فعلی، با وسایل موجود، هزینهٔ تازه‌ای ندارد.'),
            safety_notes=['در محدودهٔ امن و مجاز بمان و راه عبور دیگران را باز بگذار.'] if venue != 'home' else [],
            place=None, requires_venue_check=False, dramma=dict(version='dramma_v1',
                mechanisms=[dict(dimension=dimension, intent=intent, step_indexes=[2, 3])]))).model_dump()
        fingerprint = identity(content)
        if key in keys or fingerprint in fingerprints or not 5 <= int(minutes) + int(setup) <= 60:
            raise ValueError('Invalid or duplicate practical-now activity')
        keys.add(key)
        fingerprints.add(fingerprint)
        entries.append(dict(key=key, content=content, source_ids=[]))
    return dict(version=VERSION, researched_on=None, sources={}, entries=entries,
                publication_basis='owner_requested_practical_recreation',
                evidence_scope='authored_instructions_no_external_venue')


def import_practical_now(store, clock):
    return import_additive(store, clock, practical_now_catalog(), version=VERSION, source_file=FILE,
        raw_intent='تفریح عملیِ تألیفی با شرایط روشن و بدون خرید یا رفت‌وآمد تازه',
        reason='Owner request for more practical and varied recommendations')
