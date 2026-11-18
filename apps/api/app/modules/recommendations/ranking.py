"""Versioned deterministic baseline; ranking never relaxes eligibility."""
from datetime import timedelta
from hashlib import sha256
from collections import Counter
from app.modules.recommendations.eligibility import eligible, total_minutes, verified_cost

GOALS = {'unwind': 'relaxation', 'switch_off': 'detachment', 'learn': 'mastery',
         'connect': 'affiliation', 'meaning': 'meaning', 'choose': 'autonomy'}
ENERGY = {'low': 0, 'medium': 1, 'high': 2}
ALGORITHM_VERSION = 'nearby_full_day_outings_v8'


def activity_family(content):
    tags = set(content['tags'])
    if content.get('place') or content.get('requires_venue_check'):
        for name, markers in (
            ('screen', {'storytelling'}),
            ('stage', {'music', 'listening'}),
            ('food', {'food'}),
            ('moving', {'movement', 'walking', 'dance'}),
            ('games', {'games', 'play'}),
        ):
            if markers & tags:
                return name
        return 'visiting'
    items = set(content.get('required_items', ()))
    moves = content['mobility_required'] != 'seated'
    if 'walking' in tags and moves:
        return 'walking'
    if {'movement', 'dance'} & tags:
        return 'moving'
    if {'board_game', 'playing_cards', 'dice', 'puzzle', 'ball'} & items:
        return 'games'
    if {'games', 'puzzles', 'play'} & tags:
        return 'games' if items or moves else 'mental'
    if 'imagination' in tags and not items and not moves:
        return 'mental'
    for name, markers in (
        ('food', {'food'}),
        ('hands_on', {'craft', 'gardening', 'drawing'}),
        ('looking', {'photography', 'nature'}),
        ('reading', {'reading'}),
        ('visiting', {'culture'}),
        ('music', {'music', 'rhythm'}),
        ('making_stories', {'writing', 'storytelling'}),
        ('with_others', {'conversation', 'cooperation', 'community'}),
    ):
        if markers & tags and (items or moves or name == 'music'
                or (name == 'with_others' and 'together' in content['supported_social_modes'])):
            return name
    if {'rest', 'mindfulness'} & tags and not {'observation', 'reflection', 'imagination'} & tags:
        return 'resting'
    if {'observation', 'reflection', 'play', 'discovery', 'imagination', 'memory',
         'gratitude', 'language', 'storytelling', 'design', 'puzzles', 'games'} & tags:
        return 'mental'
    return 'other'


def time_tier(minutes, available):
    if available < 60:
        return 0
    return sum(minutes * 100 >= available * percent for percent in (33, 50, 75, 90))


def current_needs(context):
    """Explicit situational answers take precedence over a profile default."""
    intent = context.get('activity_intent')
    fallback = GOALS.get(context.get('goal'))
    if intent is not None:
        target = GOALS.get(intent) or fallback
        return {target: 1.} if target else {}
    answers = [(GOALS.get(context.get('need_now')), .6),
               (GOALS.get(context.get('desired_outcome')), .4)]
    answered = [(dimension, weight) for dimension, weight in answers if dimension]
    if not answered:
        return {fallback: 1.} if fallback else {}
    total = sum(weight for _, weight in answered)
    result = Counter()
    for dimension, weight in answered:
        result[dimension] += weight / total
    return dict(result)


def dimension_preferences(history):
    """One explicit start per recommendation session, using immutable snapshots."""
    counts, seen = Counter(), set()
    for experience in sorted(history, key=lambda e: (e['started_at'], e['id'])):
        key = experience.get('recommendation_session_id') or experience['id']
        if key in seen:
            continue
        seen.add(key)
        dimension = experience['primary_dimension_snapshot']
        counts[dimension] += 1
    total = sum(counts.values())
    return {dimension: count / (total + 6) for dimension, count in counts.items()}


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0


def rank(candidates, context, now, excluded, seed, history, feedback, shown, count=1, selected=None, *, seen=()):
    selected = list(selected or [])
    seen_families = Counter(activity_family(a['content']) for a in seen)
    is_outing = context.get('outing_days') is not None
    seen_cities = Counter(a['content']['place']['city'] for a in seen if a['content'].get('outing')) if is_outing else {}
    scored = []
    needs = current_needs(context)
    likes = set(context['liked_tags'])
    mood_answer = context.get('mood', 'skip') if context.get('activity_intent') is None else 'skip'
    preferences = dimension_preferences(history)
    completed = [e for e in history if e['status'] == 'completed']
    by_experience = {e['id']: e for e in completed}
    recent_feedback = sorted([f for f in feedback if f['updated_at'] >= now - timedelta(days=90)],
                             key=lambda f: f['updated_at'], reverse=True)[:1000]
    for activity in candidates:
        execution = eligible(context, activity, now, excluded)
        if not execution:
            continue
        c = activity['content']
        target = GOALS.get(context['goal'])
        goal = .5 if not target else 1 if target == c['primary_dimension'] else .7 if target in c['secondary_dimensions'] else .3
        if context['energy'] == 'unknown':
            energy = .5
        else:
            difference = ENERGY[c['energy_required']] - ENERGY[context['energy']]
            energy = 1 if difference == 0 else .8 if difference < 0 else .2 if difference == 1 else 0
        liked_count = len(likes.intersection(c['tags']))
        interest = liked_count / len(likes) if likes else .5
        minutes = total_minutes(c)
        cost = verified_cost(c['cost'], execution[1], now) if context['budget']['mode'] == 'cap' else None
        ratio = minutes / context['available_minutes']
        time = min(1, ratio / .85) if context['available_minutes'] >= 60 else (
            .6 if ratio <= .2 else 1 if ratio <= .8 else .8)
        mood = .5
        if mood_answer == 'tired' and (c['primary_dimension'] == 'relaxation' or c['energy_required'] == 'low'):
            mood = 1
        elif mood_answer == 'restless' and (c['primary_dimension'] == 'detachment' or c['mobility_required'] == 'light'):
            mood = 1
        elif mood_answer == 'bored' and c['primary_dimension'] in ('mastery', 'autonomy'):
            mood = 1
        elif mood_answer == 'low' and c['primary_dimension'] in ('relaxation', 'meaning'):
            mood = .8
        numerator, denominator = 2., 4.
        for f in recent_feedback:
            past = by_experience.get(f['experience_id'])
            if past:
                overlap = jaccard(c['tags'], past['content_snapshot']['tags'])
                numerator += {'liked': 1, 'neutral': .5, 'disliked': 0}[f['rating']] * overlap
                denominator += overlap
        fb = numerator / denominator
        prior = [e for e in completed if e['activity_id'] == activity['id']]
        offers = [s for s in shown if activity['id'] in s['shown_activity_ids']]
        novelty = .25 if prior else .5 if offers else 1
        penalty = .2 if any(e['completed_at'] >= now - timedelta(days=7) for e in prior) else .1 if any(
            s['created_at'] >= now - timedelta(hours=24) for s in offers) else 0
        score = max(0, min(1, .22 * goal + .20 * energy + .16 * interest + .14 * time + .10 * mood + .10 * fb + .08 * novelty - penalty))
        tie = sha256(f'{seed}:{activity["id"]}'.encode()).hexdigest()
        family = activity_family(c)
        scored.append(dict(activity=activity, execution=execution, score=score, tie=tie,
            time_tier=time_tier(minutes, context['available_minutes']), minutes=minutes,
            budget_fit=cost or (0, 0),
            family=family, practical=(family not in {'mental', 'other', 'resting'} or liked_count > 0
                                      or (family == 'resting' and 'relaxation' in needs)),
            interest=liked_count > 0, named_place=bool(c.get('place')),
            need_fit=needs.get(c['primary_dimension'], 0),
            dimension_preference=preferences.get(c['primary_dimension'], 0)))
    output = []
    for cap in (2, 3, 6):
        while len(output) < count:
            options = []
            for item in scored:
                if any(x['activity']['id'] == item['activity']['id'] for x in output):
                    continue
                c = item['activity']['content']
                others = selected + [x['activity'] for x in output]
                n = sum(a['content']['primary_dimension'] == c['primary_dimension'] for a in others)
                if n >= cap:
                    continue
                similarity = max((jaccard(c['tags'], a['content']['tags']) for a in others), default=0)
                family_count = seen_families[item['family']] + sum(
                    activity_family(a['content']) == item['family'] for a in others)
                base = item['score'] - .12 * similarity - .08 * n
                if is_outing:
                    city = c['place']['city']
                    city_count = seen_cities.get(city, 0) + sum(
                        (a['content'].get('place') or {}).get('city') == city for a in others)
                    travel = c['outing']['one_way_travel_minutes']
                    options.append((-city_count, -(travel // 45), -family_count, item['need_fit'],
                                    item['interest'], base - travel / 1000, item['tie'], item))
                    continue
                long_window = context['available_minutes'] >= 60
                preference = item['dimension_preference']
                minutes = item['minutes'] if long_window else 0
                variety_and_time = ((-family_count, minutes) if seen or others else (minutes, -family_count))
                options.append((item['time_tier'], item['budget_fit'],
                    item['practical'], item['named_place'], *variety_and_time, item['interest'],
                    item['need_fit'], 0 if long_window else preference,
                    base + (.12 * preference if long_window else 0), item['tie'], item))
            if not options:
                break
            output.append(max(options, key=lambda x: x[:-1])[-1])
        if len(output) == count:
            break
    return output
