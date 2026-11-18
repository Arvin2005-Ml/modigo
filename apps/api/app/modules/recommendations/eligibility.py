"""Pure hard-filter rules. Inputs must first be validated against the API schemas.

This module deliberately has no database or HTTP dependencies. It is not an API;
publication state and ownership are checked here only as candidate eligibility.
"""
from datetime import datetime
from app.core.schemas import city_key

VENUE_POLICY_VERSION = 'explicit_opt_in_and_exact_city_v1'

MOBILITY = {'seated': 0, 'light': 1, 'active': 2}
VENUE_MATCHES = {
    'home': ('home',),
    'away_from_home': ('outdoor', 'indoor_public'),
    'any': ('home', 'outdoor', 'indoor_public'),
    'outdoor': ('outdoor',),
    'indoor_public': ('indoor_public',),
}

def total_minutes(content: dict) -> int:
    return sum(content[key] for key in ('active_minutes', 'setup_minutes', 'travel_minutes'))


def venue_allowed(context: dict, content: dict) -> bool:
    place = content.get('place')
    if (place or content.get('requires_venue_check')) and context.get('allow_venue_planning') is not True:
        return False
    return not place or bool(context.get('city') and city_key(context['city']) == city_key(place['city']))


def eligible(context: dict, activity: dict, now: datetime, excluded: set[str] | None = None) -> tuple[str, int] | None:
    """Return the execution mode and number of people, or None if ineligible.

    ``activity`` combines activity publication fields and revision content. ``now``
    must be timezone-aware and is injected to make cost expiry deterministic.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now must be timezone-aware')
    if (not activity.get('active') or activity.get('state') != 'published'
            or not activity.get('revision_id')
            or activity.get('published_revision_id') != activity.get('revision_id')
            or activity['id'] in (excluded or set())):
        return None
    content = activity['content']
    if total_minutes(content) > context['available_minutes']:
        return None
    if content['venue'] not in VENUE_MATCHES.get(context['venue'], ()):
        return None
    if not venue_allowed(context, content):
        return None
    requested = context['social_mode']
    size = context['party_size']
    modes = content['supported_social_modes']
    if requested in ('solo', 'either') and 'solo' in modes and content['min_people'] <= 1 <= content['max_people']:
        mode, people = 'solo', 1
    elif requested in ('together', 'either') and size >= 2 and 'together' in modes and content['min_people'] <= size <= content['max_people']:
        mode, people = 'together', size
    else:
        return None
    cost = content['cost']
    budget = context['budget']
    if budget['mode'] == 'free' and cost['kind'] != 'free':
        return None
    if budget['mode'] == 'cap' and cost['kind'] != 'free':
        verified = cost.get('verified_at')
        valid_until = cost.get('valid_until')
        if (cost['kind'] != 'estimated' or not verified or not valid_until
                or verified > now or valid_until <= now
                or valid_until <= verified
                or (valid_until - verified).total_seconds() > 30 * 86400
                or cost.get('max_toman') is None or cost['max_toman'] < 0):
            return None
        total = cost['max_toman'] * (people if cost['basis'] == 'per_person' else 1)
        if total > budget['cap_toman']:
            return None
    if not set(content['required_items']).issubset(context.get('owned_items', [])):
        return None
    if MOBILITY[content['mobility_required']] > MOBILITY[context.get('max_mobility', 'active')]:
        return None
    if context.get('requires_step_free', False) and content['step_free'] is not True:
        return None
    if context.get('requires_quiet', False) and content['quiet_compatible'] is not True:
        return None
    if set(content['tags']) & set(context.get('blocked_tags', [])):
        return None
    if content['requires_async_contact'] and not context.get('allow_async_contact', False):
        return None
    if content['weather_requirement'] == 'fair' and context.get('weather', 'unknown') != 'fair':
        return None
    if content['daylight_requirement'] == 'day' and context.get('daylight', 'unknown') != 'day':
        return None
    return mode, people
