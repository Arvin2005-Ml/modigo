"""Apply current withdrawal rules even to responses from idempotency receipts."""
from copy import deepcopy


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
            if activity and (not activity['active'] or revision and revision['state'] == 'archived'):
                if item.get('slot_id') and 'title' in item:
                    return {'slot_id': item['slot_id'], 'unavailable': True}
                item['unavailable'] = True
                for field in ('content_snapshot', 'content', 'title', 'teaser', 'first_step', 'steps'):
                    item.pop(field, None)
        result = {k: walk(v) for k, v in item.items()}
        if 'items' in result and 'result_count' in result:
            n = sum(not v.get('unavailable', False) for v in result['items'])
            result.update(result_count=n, partial=n == 0, empty_reason=None if n else 'NO_MATCHES')
        return result
    return walk(value)
