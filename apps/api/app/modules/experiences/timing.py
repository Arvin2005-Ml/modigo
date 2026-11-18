from datetime import timedelta


def active_until(experience):
    """A two-day outing remains active through its second day; older rows stay at 24 hours."""
    outing = (experience.get('content_snapshot') or {}).get('outing') or {}
    return experience['started_at'] + timedelta(days=2 if outing.get('days') == 2 else 1)


def is_active(experience, now):
    return experience['status'] == 'active' and active_until(experience) > now
