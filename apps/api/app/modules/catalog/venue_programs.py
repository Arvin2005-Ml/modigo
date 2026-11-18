"""Reviewed outgoing links, independent of published revisions and snapshots."""
import json
import re
from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, ValidationError, field_validator, model_validator

from app.core.schemas import Input, city_key
from app.core.values import digest, replace

COLLECTION = 'venue_program_links'
Kind = Literal['cinema', 'theatre', 'concert']
Scope = Literal['venue', 'collection', 'directory']
CINEMA = 'https://cinematicket.org/home/cinema'
TIWALL = 'https://www.tiwall.com/'
ROUDAKI = TIWALL + 'roudaki'
DIRECTORIES = {
    'cinema': (CINEMA, 'دیدن فهرست سینماها و سانس‌ها در سینماتیکت'),
    'theatre': (TIWALL + 'showcase?filters=s:theater', 'دیدن فهرست نمایش‌ها در تیوال'),
    'concert': (TIWALL + 'showcase?filters=s:music', 'دیدن فهرست کنسرت‌ها در تیوال'),
}


def place_id(city, name):
    # Keep cities separate even if two cinemas share the same name.
    return digest(json.dumps([city_key(city), city_key(name)], ensure_ascii=False))


class Program(Input):
    kind: Kind
    scope: Scope
    url: str = Field(max_length=240)
    checked_on: str

    @field_validator('checked_on')
    @classmethod
    def iso_date(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError('expected ISO calendar date')
        return value

    @model_validator(mode='after')
    def reviewed_destination(self):
        url = self.url
        if self.scope == 'directory':
            allowed = url == DIRECTORIES[self.kind][0]
        elif self.scope == 'collection':
            allowed = self.kind in ('theatre', 'concert') and url == ROUDAKI
        elif self.kind == 'cinema':
            allowed = re.fullmatch(r'https://(?:cinematicket\.org/cinema/detail|gisheh7\.ir/cinema)/[1-9][0-9]*/?', url)
        else:
            allowed = (url in {TIWALL + 'iranshahr', TIWALL + 'talarvahdat'}
                       or re.fullmatch(r'https://www\.tiwall\.com/showcase\?filters=venue:[1-9][0-9]*&w=where', url))
        if not allowed:
            raise ValueError('unsupported program destination')
        return self

    def public(self):
        if self.scope == 'directory':
            label = DIRECTORIES[self.kind][1]
        elif self.scope == 'collection':
            label = 'دیدن برنامه‌های بنیاد رودکی در تیوال'
        elif self.kind == 'cinema':
            provider = 'گیشه ۷' if urlsplit(self.url).hostname == 'gisheh7.ir' else 'سینماتیکت'
            label = f'دیدن سانس‌های این سینما در {provider}'
        else:
            label = 'دیدن برنامهٔ این سالن در تیوال'
        return {'url': self.url, 'label': label, 'scope': self.scope}


def program_for_place(store, key):
    row = store.get(COLLECTION, key)
    if not row:
        return None
    try:
        return Program.model_validate(row.get('program')).public()
    except ValidationError:
        # Do not expose an invalid URL even if inserted outside the importer.
        return None


def seed_rows():
    from app.modules.catalog.bootstrap import ROOT
    from app.modules.catalog.unified import unified_catalog

    overrides = {}
    source = ROOT / 'content/venue-programs.txt'
    for line in source.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        city, name, kind, scope, url, checked_on = line.split('|')
        key = place_id(city, name)
        if key in overrides:
            raise ValueError(f'Duplicate program override: {city} / {name}')
        overrides[key] = Program(kind=kind, scope=scope, url=url, checked_on=checked_on)

    rows, activities = {}, {}
    for release in unified_catalog()['releases'].values():
        for entry in release['entries']:
            kind, place = entry['category'], entry['content'].get('place')
            if kind not in DIRECTORIES or not place:
                continue
            city, name = place['city'], place['name']
            key = place_id(city, name)
            program = overrides.get(key) or Program(kind=kind, scope='directory',
                url=DIRECTORIES[kind][0], checked_on='2026-11-19')
            if program.kind != kind:
                raise ValueError(f'Program kind differs from catalog: {city} / {name}')
            rows[key] = dict(id=key, city=city, name=name, program=program.model_dump())
            activities[entry['key']] = key

    if overrides.keys() - rows.keys():
        raise ValueError('Program override names a venue absent from the catalog')
    return rows, activities


def apply_programs(store, rows):
    from collections import Counter

    counts = Counter(inserted=0, updated=0, unchanged=0)
    # Keep Mongo transactions short on the public endpoint.
    rows = list(rows.values())
    for offset in range(0, len(rows), 15):
        with store.atomic():
            for row in rows[offset:offset + 15]:
                previous = store.get(COLLECTION, row['id'])
                if previous is None:
                    store.insert(COLLECTION, row)
                    counts['inserted'] += 1
                elif all(previous.get(field) == value for field, value in row.items()):
                    counts['unchanged'] += 1
                else:
                    replace(store, COLLECTION, {**row, 'version': previous['version']})
                    counts['updated'] += 1
    return dict(counts)


def verify_programs(store, rows, activity_keys):
    persisted = {row['id']: row for row in store.list(COLLECTION)}
    verified = {key for key, row in rows.items()
                if key in persisted and all(persisted[key].get(field) == value for field, value in row.items())}
    keys = sorted(activity_keys)
    linked = live = 0
    for offset in range(0, len(keys), 25):
        activities = store.activities_by_seed_keys(set(keys[offset:offset + 25]))
        expected = {item['id']: activity_keys[item['seed_key']] for item in activities}
        for item in store.published_catalog(set(expected)):
            live += 1
            place = (item.get('content') or {}).get('place')
            if place:
                key = place_id(place['city'], place['name'])
                linked += key == expected[item['id']] and key in verified
    return {'stored_verified': len(verified), 'published_target_activities': live,
            'published_linked_activities': linked}


def main(argv=None):
    import argparse
    from collections import Counter
    import sys
    from app.core.config import Settings
    from app.core.storage import create_store, StorageUnavailable

    parser = argparse.ArgumentParser(description='Manage reviewed links to cinema and performance listings')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--verify', action='store_true')
    args = parser.parse_args(argv)
    rows, activities = seed_rows()
    summary = {'venues': len(rows), 'catalog_activities': len(activities),
               'by_kind': dict(Counter(row['program']['kind'] for row in rows.values())),
               'by_scope': dict(Counter(row['program']['scope'] for row in rows.values()))}
    if not (args.apply or args.verify):
        print(json.dumps({'mode': 'files_only', **summary}, ensure_ascii=False))
        return 0
    store = None
    try:
        settings = Settings.load()
        store = create_store({'DATA_BACKEND': settings.data_backend, 'MONGODB_URI': settings.mongodb_uri})
        if args.apply:
            print(json.dumps({'mode': 'real_mongodb_apply', **summary, **apply_programs(store, rows)}), flush=True)
            return 0
        result = verify_programs(store, rows, activities)
        print(json.dumps({'mode': 'real_mongodb_verify', **summary, **result}))
        return int(result['stored_verified'] != len(rows) or
                   result['published_target_activities'] != result['published_linked_activities'])
    except StorageUnavailable as exc:
        print(f'{exc}. Venue program operation not confirmed; no memory fallback was used.', file=sys.stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
