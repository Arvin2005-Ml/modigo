"""Apply current withdrawal rules even to responses from idempotency receipts."""
from copy import deepcopy
from app.modules.catalog.venue_programs import place_id, program_for_place


def with_venue_programs(value, store):
    """Decorate public views after ownership, visibility and idempotency checks."""
    resolved = {}

    def walk(item):
        if isinstance(item, list):
            return [walk(entry) for entry in item]
        if not isinstance(item, dict) or item.get('unavailable'):
            return item
        result = {**item}
        for field in ('items', 'item', 'experience', 'content', 'content_snapshot'):
            if field in item:
                result[field] = walk(item[field])
        place = item.get('place')
        if isinstance(place, dict):
            # Only the separately validated registry may supply the public link.
            clean = {k: v for k, v in place.items() if k != 'program'}
            city, name = place.get('city'), place.get('name')
            if isinstance(city, str) and isinstance(name, str) and city and name:
                key = place_id(city, name)
                if key not in resolved:
                    resolved[key] = program_for_place(store, key)
                if resolved[key]:
                    clean['program'] = resolved[key]
            result['place'] = clean
        return result

    return walk(value)


def public_response(value, store):
    value = deepcopy(value)
    def walk(item):
        if isinstance(item, list):
            return [walk(v) for v in item]
        if not isinstance(item, dict):
            return item
        if item.get('activity_id'):
            activity = store.get('activities', item['activity_id'])
            revision = store.get('activity_revisions', item.get('revision_id', ''))
            if item.get('slot_id') and 'title' in item and 'requires_venue_check' not in item and revision:
                # A receipt saved before city/consent existed cannot authorize a venue.
                content = revision.get('content') or {}
                if content.get('place') or content.get('requires_venue_check'):
                    return {'slot_id': item['slot_id'], 'unavailable': True}
            if activity and (not activity['active'] or revision and revision['state'] == 'archived'):
                if item.get('slot_id') and 'title' in item:
                    return {'slot_id': item['slot_id'], 'unavailable': True}
                item['unavailable'] = True
                for field in ('content_snapshot', 'content', 'title', 'teaser', 'first_step', 'steps',
                              'requires_venue_check', 'place', 'venue_check_message', 'outing'):
                    item.pop(field, None)
        result = {k: walk(v) for k, v in item.items()}
        if 'items' in result and 'result_count' in result:
            n = sum(not v.get('unavailable', False) for v in result['items'])
            result.update(result_count=n, partial=n == 0, empty_reason=None if n else 'NO_MATCHES')
        return result
    return walk(value)
