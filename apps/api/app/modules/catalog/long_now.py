"""Authored longer activities for a place the user can already use."""
from functools import lru_cache

from app.modules.catalog.bootstrap import ROOT
from app.modules.catalog.cinema_expansion import import_additive
from app.modules.catalog.deduplication import identity
from app.modules.catalog.schemas import Content

VERSION = 'long_now_v1'
FILE = 'content/long-now.txt'


@lru_cache(maxsize=1)
def long_now_catalog():
    entries, keys, fingerprints = [], set(), set()
    for line in (ROOT / FILE).read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        (slug, venue, minutes, dimension, mobility, energy, mode, items, weather, daylight,
         tags, title, teaser, first, second, third, lighter, intent) = line.split('|')
        key = 'real:long-now-' + slug
        items = [] if items == '-' else items.split(',')
        people = 2 if mode == 'together' else 1
        content = Content.model_validate(dict(
            title=title, teaser=teaser, first_step=first, steps=[first, second, third],
            lighter_version=lighter, primary_dimension=dimension, secondary_dimensions=[],
            tags=tags.split(','), active_minutes=int(minutes), setup_minutes=0, travel_minutes=0,
            energy_required=energy, mobility_required=mobility, supported_social_modes=[mode],
            min_people=people, max_people=people, venue=venue, required_items=items,
            materials_note='با وسایلی که از قبل داری؛ خرید تازه لازم نیست.' if items else 'وسیلهٔ خاصی لازم نیست.',
            accessibility_note='اگر فضای فعلی و حرکت‌های پیشنهادی برایت مناسب نیستند، گزینهٔ دیگری بگیر.',
            conditions_note=('در همان فضای امنی که الآن در آن هستی اجرا کن. اگر شرایط شروع در این محل فراهم '
                             'نیست، گزینهٔ دیگری بگیر؛ رفت‌وآمد یا ورود تازه در این برنامه نیست.'),
            requires_async_contact=False, step_free=None, quiet_compatible=mode == 'solo' and mobility == 'seated',
            weather_requirement=weather, daylight_requirement=daylight,
            cost=dict(kind='free', min_toman=0, max_toman=0, basis='per_person', verified_at=None,
                      valid_until=None, note='در محل و با وسایل از قبل در دسترس، هزینهٔ تازه ندارد.'),
            safety_notes=['در مسیر امن و مجاز بمان و در صورت خستگی زودتر توقف کن.'] if venue != 'home' else [],
            place=None, requires_venue_check=False, dramma=dict(version='dramma_v1',
                mechanisms=[dict(dimension=dimension, intent=intent, step_indexes=[2, 3])]))).model_dump()
        fingerprint = identity(content)
        if key in keys or fingerprint in fingerprints or not 45 <= content['active_minutes'] <= 120:
            raise ValueError('Invalid or duplicate long-now activity')
        keys.add(key)
        fingerprints.add(fingerprint)
        entries.append(dict(key=key, content=content, source_ids=[]))
    return dict(version=VERSION, researched_on=None, sources={}, entries=entries,
                publication_basis='owner_requested_authored_same_place_activities',
                evidence_scope='authored_instructions_no_external_venue')


def import_long_now(store, clock):
    return import_additive(store, clock, long_now_catalog(), version=VERSION, source_file=FILE,
        raw_intent='تجربهٔ ۴۵ تا ۱۲۰ دقیقه‌ای در همان محل، بدون ورود یا خرید اضافه',
        reason='Owner request: meaningful longer activities for longer time windows')
