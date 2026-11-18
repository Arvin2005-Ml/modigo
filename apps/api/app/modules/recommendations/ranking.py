"""Versioned deterministic baseline; ranking never relaxes eligibility."""
from datetime import timedelta
from hashlib import sha256
from collections import Counter
from app.modules.recommendations.eligibility import eligible

GOALS = {'unwind': 'relaxation', 'switch_off': 'detachment', 'learn': 'mastery',
         'connect': 'affiliation', 'meaning': 'meaning', 'choose': 'autonomy'}
ENERGY = {'low': 0, 'medium': 1, 'high': 2}
ALGORITHM_VERSION = 'needs_history_v3'


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


def rank(candidates, context, now, excluded, seed, history, feedback, shown, count=1, selected=None):
    selected = list(selected or [])
    scored = []
    needs = current_needs(context)
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
        likes = set(context['liked_tags'])
        interest = len(likes & set(c['tags'])) / len(likes) if likes else .5
        ratio = sum(c[k] for k in ('active_minutes', 'setup_minutes', 'travel_minutes')) / context['available_minutes']
        time = .6 if ratio <= .2 else 1 if ratio <= .8 else .8
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
        scored.append(dict(activity=activity, execution=execution, score=score, tie=tie,
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
                options.append((item['need_fit'], item['dimension_preference'],
                    item['score'] - .12 * similarity - .08 * n, item['tie'], item))
            if not options:
                break
            output.append(max(options, key=lambda x: x[:-1])[-1])
        if len(output) == count:
            break
    return output
