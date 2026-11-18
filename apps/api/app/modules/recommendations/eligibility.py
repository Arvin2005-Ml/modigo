"""Pure hard-filter rules. Inputs must first be validated against the API schemas.

This module deliberately has no database or HTTP dependencies. It is not an API;
publication state and ownership are checked here only as candidate eligibility.
"""
from datetime import datetime
from app.core.schemas import city_key

VENUE_POLICY_VERSION = 'exact_city_and_reviewed_outing_origins_v2'

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


def verified_cost(cost: dict, people: int, now: datetime) -> tuple[int, int] | None:
    """Return the current estimate for the whole party, including zero for a free plan."""
    if cost['kind'] == 'free':
        return (0, 0)
    verified, until = cost.get('verified_at'), cost.get('valid_until')
    minimum, maximum = cost.get('min_toman'), cost.get('max_toman')
    if (cost['kind'] != 'estimated' or not verified or not until or not verified <= now < until
            or (until - verified).total_seconds() > 30 * 86400
            or minimum is None or maximum is None or not 0 <= minimum <= maximum):
        return None
    multiplier = people if cost['basis'] == 'per_person' else 1
    return minimum * multiplier, maximum * multiplier


def venue_allowed(context: dict, content: dict) -> bool:
    place = content.get('place')
    if (place or content.get('requires_venue_check')) and context.get('allow_venue_planning') is not True:
        return False
    if outing := content.get('outing'):
        return (context.get('outing_days') == outing['days']
                and context['venue'] == 'away_from_home'
                and context.get('city') == outing['origin_city'])
    if context.get('outing_days') is not None:
        return False
    return not place or bool(context.get('city') and city_key(context['city']) == city_key(place['city']))


def execution_for_party(content, requested, size):
    modes = content['supported_social_modes']
    if requested in ('solo', 'either') and 'solo' in modes and content['min_people'] <= 1 <= content['max_people']:
        return 'solo', 1
    if requested in ('together', 'either') and size >= 2 and 'together' in modes and content['min_people'] <= size <= content['max_people']:
        return 'together', size
    return None


def access_allows(content, constraints):
    return (MOBILITY[content['mobility_required']] <= MOBILITY[constraints.get('max_mobility', 'active')]
            and (not constraints.get('requires_step_free') or content['step_free'] is True)
            and (not constraints.get('requires_quiet') or content['quiet_compatible'] is True)
            and not (set(content['tags']) & set(constraints.get('blocked_tags', []))))


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
    execution = execution_for_party(content, context['social_mode'], context['party_size'])
    if execution is None:
        return None
    _, people = execution
    cost = content['cost']
    budget = context['budget']
    if budget['mode'] == 'free' and cost['kind'] != 'free':
        return None
    if budget['mode'] == 'cap':
        estimate = verified_cost(cost, people, now)
        if estimate is None or estimate[1] > budget['cap_toman']:
            return None
    if not set(content['required_items']).issubset(context.get('owned_items', [])):
        return None
    if not access_allows(content, context):
        return None
    if content['requires_async_contact'] and not context.get('allow_async_contact', False):
        return None
    if content['weather_requirement'] == 'fair' and context.get('weather', 'unknown') != 'fair':
        return None
    if content['daylight_requirement'] == 'day' and context.get('daylight', 'unknown') != 'day':
        return None
    return execution
