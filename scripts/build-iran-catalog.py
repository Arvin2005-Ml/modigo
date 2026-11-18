"""Build the authored Iran catalog from reviewable recipes, without DB or LLM access."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))
from app.modules.catalog.schemas import Content

# Planning durations are limits for choosing a suitable local session, not measured
# venue data. Every card makes this condition visible; no price or schedule is invented.
GROUPS = {
    'cinema': ('سینما و نمایش فیلم', 'culture storytelling indoors'.split(), 120, 'low', 'seated', 'indoor_public', ['tiwall', 'cinematicket']),
    'theatre': ('تئاتر و هنرهای نمایشی', 'culture storytelling creativity indoors'.split(), 100, 'low', 'seated', 'indoor_public', ['tiwall']),
    'music': ('کنسرت و اجرای زنده', 'music listening culture indoors'.split(), 120, 'low', 'seated', 'indoor_public', ['honarticket', 'tiwall']),
    'dining': ('رستوران و فست‌فود', 'food sensory discovery indoors'.split(), 75, 'low', 'seated', 'indoor_public', ['snappfood']),
    'cafe': ('کافه و تجربهٔ طعم', 'food sensory rest indoors'.split(), 60, 'low', 'seated', 'indoor_public', ['snappfood']),
    'cooking': ('کارگاه آشپزی و شیرینی', 'food craft creativity indoors'.split(), 180, 'medium', 'light', 'indoor_public', ['chocolate_workshop', 'craft_workshops']),
    'clay': ('سفال، کاشی و شیشه', 'craft design creativity indoors'.split(), 150, 'medium', 'light', 'indoor_public', ['kashan_crafts', 'craft_workshops']),
    'textile': ('بافت و هنرهای پارچه‌ای', 'craft design culture indoors'.split(), 150, 'medium', 'seated', 'indoor_public', ['kashan_crafts']),
    'wood': ('چوب، چرم و فلز', 'craft design creativity indoors'.split(), 150, 'medium', 'light', 'indoor_public', ['kashan_crafts']),
    'painting': ('نقاشی و تصویرسازی عملی', 'drawing design creativity indoors'.split(), 150, 'medium', 'seated', 'indoor_public', ['tiwall', 'craft_workshops']),
    'paper': ('چاپ، کاغذ و ساختنی', 'craft design drawing indoors'.split(), 120, 'medium', 'seated', 'indoor_public', ['tiwall', 'kashan_crafts']),
    'performance': ('کارگاه موسیقی و اجرا', 'music rhythm storytelling creativity indoors'.split(), 90, 'medium', 'light', 'indoor_public', ['tiwall', 'honarticket']),
    'racket': ('راکت و بازی‌های هدف‌گیری', 'games movement play indoors'.split(), 60, 'high', 'active', 'indoor_public', ['enghelab']),
    'team_sport': ('ورزش و بازی تیمی', 'movement cooperation play friendship indoors'.split(), 75, 'high', 'active', 'indoor_public', ['enghelab']),
    'balance': ('تحرک، تعادل و مهارت بدنی', 'movement play discovery indoors'.split(), 60, 'high', 'active', 'indoor_public', ['enghelab']),
    'water_ice': ('تفریح آبی و پیست', 'movement play discovery'.split(), 75, 'high', 'active', 'indoor_public', ['enghelab', 'tochal_facilities']),
    'table_games': ('بازی‌های سالنی و آرکید', 'games play friendship indoors'.split(), 60, 'medium', 'light', 'indoor_public', ['plania', 'enghelab']),
    'group_games': ('بازی‌های جمعی و اتاق فرار', 'games cooperation puzzles friendship indoors'.split(), 90, 'medium', 'light', 'indoor_public', ['escape_example', 'tiwall']),
    'simulation': ('شبیه‌ساز و واقعیت مجازی', 'games digital play discovery indoors'.split(), 45, 'medium', 'light', 'indoor_public', ['plania']),
    'amusement': ('شهربازی و تفریح هیجانی', 'play movement discovery'.split(), 60, 'medium', 'active', 'outdoor', ['plania', 'tochal_facilities']),
    'museum': ('موزه و مجموعه‌های دیدنی', 'culture discovery observation indoors'.split(), 90, 'medium', 'light', 'indoor_public', ['iran_museums', 'science_museum']),
    'heritage': ('بناهای تاریخی و معماری', 'culture discovery walking outdoors'.split(), 90, 'medium', 'light', 'outdoor', ['kashan_attractions', 'iran_museums']),
    'garden': ('باغ، طبیعت و گردش آرام', 'nature walking discovery outdoors'.split(), 90, 'medium', 'light', 'outdoor', ['botanical_garden', 'tochal_facilities']),
    'local_tour': ('گردش شهری و دیدار با صنعتگر', 'culture craft discovery walking outdoors'.split(), 120, 'medium', 'light', 'outdoor', ['kashan_crafts', 'kashan_attractions']),
    'science': ('تجربهٔ علم و فناوری', 'science discovery play indoors'.split(), 90, 'medium', 'light', 'indoor_public', ['science_museum']),
}

DIMENSION_LABELS = dict(detachment='فاصله از مشغله', relaxation='استراحت',
    autonomy='انتخاب آزاد', mastery='یادگیری مهارت', meaning='معنای شخصی', affiliation='ارتباط با همراه')

PREP = 'پیش از پرداخت، وجود همین برنامه در شهر خودت، ظرفیت، هزینهٔ همهٔ نفرها، وسایل و شرایط ورود را از برگزارکننده تأیید کن؛ فقط سانسی را بگیر که در زمان این کارت جا شود.'

# Execution metadata follows each recipe, including exceptions within a category.
OVERRIDES = {
    'iran-cinema-09': dict(venue='outdoor', weather_requirement='fair', daylight_requirement='any'),
    'iran-dining-11': dict(venue='outdoor', weather_requirement='fair', daylight_requirement='any'),
    'iran-racket-01': dict(supported_social_modes=['together'], min_people=2, max_people=4),
    'iran-racket-02': dict(venue='outdoor', weather_requirement='fair', daylight_requirement='day'),
    'iran-racket-03': dict(supported_social_modes=['together'], min_people=4, max_people=4,
        venue='outdoor', weather_requirement='fair', daylight_requirement='day'),
    'iran-racket-05': dict(supported_social_modes=['together'], min_people=2, max_people=2),
    'iran-racket-06': dict(supported_social_modes=['together'], min_people=4, max_people=4),
    'iran-racket-07': dict(supported_social_modes=['together'], min_people=4, max_people=4),
    'iran-racket-08': dict(venue='outdoor', weather_requirement='fair', daylight_requirement='day'),
    'iran-racket-09': dict(venue='outdoor', weather_requirement='fair', daylight_requirement='day'),
    'iran-team_sport-01': dict(min_people=6),
    'iran-team_sport-02': dict(min_people=6, max_people=6),
    'iran-team_sport-03': dict(min_people=4),
    'iran-team_sport-04': dict(min_people=6, venue='outdoor', weather_requirement='fair', daylight_requirement='day'),
    'iran-team_sport-05': dict(min_people=4),
    'iran-team_sport-07': dict(min_people=4),
    'iran-team_sport-08': dict(min_people=6),
    'iran-team_sport-09': dict(min_people=4, venue='outdoor', weather_requirement='fair', daylight_requirement='day'),
    'iran-team_sport-10': dict(min_people=4),
    'iran-team_sport-11': dict(mobility_required='active', required_items=['towel']),
    'iran-team_sport-12': dict(min_people=4, venue='outdoor', weather_requirement='fair', daylight_requirement='day'),
    **{f'iran-water_ice-{i:02}': dict(required_items=['towel']) for i in range(1, 6)},
    **{f'iran-water_ice-{i:02}': dict(venue='outdoor', weather_requirement='fair', daylight_requirement='day') for i in range(6, 11)},
    'iran-water_ice-06': dict(supported_social_modes=['together'], min_people=2, max_people=2,
        venue='outdoor', weather_requirement='fair', daylight_requirement='day'),
    'iran-water_ice-12': dict(venue='outdoor', weather_requirement='fair', daylight_requirement='day', active_minutes=120),
    **{f'iran-table_games-{i:02}': dict(supported_social_modes=['together'], min_people=2, max_people=2) for i in (1, 2, 3, 4, 11)},
    'iran-table_games-09': dict(supported_social_modes=['together'], min_people=2, max_people=8),
    'iran-table_games-10': dict(supported_social_modes=['together'], min_people=2, max_people=4),
    'iran-table_games-12': dict(supported_social_modes=['together'], min_people=2, max_people=8),
    'iran-group_games-05': dict(min_people=6, max_people=12),
    'iran-group_games-11': dict(max_people=12, energy_required='high', mobility_required='active'),
    'iran-group_games-12': dict(min_people=6, max_people=12, energy_required='high', mobility_required='active',
        venue='outdoor', weather_requirement='fair', daylight_requirement='day'),
    'iran-simulation-06': dict(supported_social_modes=['together'], min_people=2, max_people=2),
    'iran-simulation-08': dict(energy_required='low', mobility_required='seated'),
    **{f'iran-amusement-{i:02}': dict(venue='indoor_public', weather_requirement='any', daylight_requirement='any') for i in (2, 8, 12)},
    'iran-garden-02': dict(venue='indoor_public', weather_requirement='any', daylight_requirement='any'),
    'iran-garden-04': dict(venue='indoor_public', weather_requirement='any', daylight_requirement='any'),
    'iran-garden-05': dict(venue='indoor_public', weather_requirement='any', daylight_requirement='any', active_minutes=120),
    'iran-garden-06': dict(venue='indoor_public', weather_requirement='any', daylight_requirement='any', active_minutes=120),
    'iran-garden-11': dict(venue='indoor_public', weather_requirement='any', daylight_requirement='any'),
    **{f'iran-local_tour-{i:02}': dict(venue='indoor_public', weather_requirement='any', daylight_requirement='any') for i in (1, 2, 3, 4, 5, 6, 11)},
    'iran-local_tour-07': dict(required_items=['phone']),
    'iran-local_tour-10': dict(energy_required='low', mobility_required='seated'),
    'iran-science-06': dict(energy_required='low', mobility_required='seated'),
}


def build():
    sources = json.loads((ROOT / 'content/iran-sources.json').read_text(encoding='utf-8'))
    alignment = json.loads((ROOT / 'content/iran-dramma.json').read_text(encoding='utf-8'))
    if alignment['version'] != 'dramma_v1':
        raise ValueError('Unsupported DRAMMA mapping')
    entries, group, counts = [], None, Counter()
    for line in (ROOT / 'content/iran-recipes.txt').read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        if line.startswith('@'):
            group = line[1:]
            if group not in GROUPS:
                raise ValueError('Unknown recipe group: ' + group)
            continue
        title, first, action, finish = line.split('|')
        label, tags, minutes, energy, mobility, venue, evidence = GROUPS[group]
        counts[group] += 1
        key = f'iran-{group}-{counts[group]:02}'
        # The recipe file is append-only within each group: identifiers must not shift.
        profile = alignment['entries'][key]
        dimension = profile['primary_dimension']
        together = group in ('team_sport', 'group_games')
        minimum = 4 if group == 'group_games' else 2 if together else 1
        maximum = 8 if group == 'group_games' else 12
        extra = ' برای کارگاه فقط جلسهٔ تفریحی مبتدی با وسایل مجموعه را انتخاب کن؛ دورهٔ چندجلسه‌ای منظور نیست.' if group in (
            'cooking', 'clay', 'textile', 'wood', 'painting', 'paper', 'performance', 'science') else ''
        conditions = f'فقط در صورت وجود برنامهٔ مناسب در شهرت: اجرا حداکثر {minutes} دقیقه، پذیرش ۳۰ دقیقه و رفت‌وبرگشت حداکثر ۶۰ دقیقه.{extra}'
        if len(conditions) > 240:
            raise ValueError('Conditions too long: ' + key)
        safety = []
        if group in ('racket', 'team_sport', 'balance', 'water_ice', 'amusement'):
            safety.append('محدودیت سن، قد، پوشش و مهارت مجموعه را رعایت کن؛ اجرای حرکت تازه فقط با راهنمایی مربی یا اپراتور باشد.')
        if group in ('dining', 'cafe', 'cooking'):
            safety.append('ترکیبات و حساسیت غذایی را پیش از سفارش یا چشیدن با مسئول مجموعه بررسی کن.')
        if group in ('clay', 'wood', 'paper'):
            safety.append('کار با کوره، تیغ، دستگاه و مواد داغ فقط بر عهدهٔ مربی یا با نظارت مستقیم او باشد.')
        raw = dict(
            title=title, teaser=action, first_step=first, steps=[PREP, action, finish],
            lighter_version='از مسئول مجموعه نسخهٔ مبتدی، نوبت کوتاه‌تر یا بخش ساده‌تر همین تجربه را بخواه؛ مدت و شرایط واقعی را دوباره بررسی کن.',
            materials_note='وسایل شخصی و پوشش لازم را از محل بپرس؛ اجاره یا تأمین ابزار و هزینهٔ آن باید پیش از رزرو تأیید شود.',
            accessibility_note='پله، مسیر، سرویس و امکان نشستن از محل تأیید نشده؛ دسترسی بدون پله و سکوت تضمین نیست.',
            conditions_note=conditions, requires_venue_check=True,
            primary_dimension=dimension, secondary_dimensions=[], tags=tags,
            active_minutes=minutes, setup_minutes=30, travel_minutes=60,
            energy_required=energy, mobility_required=mobility,
            supported_social_modes=['together'] if together else ['solo', 'together'],
            min_people=minimum, max_people=maximum, venue=venue, required_items=[],
            requires_async_contact=False, step_free=None, quiet_compatible=None,
            weather_requirement='fair' if venue == 'outdoor' else 'any',
            daylight_requirement='day' if venue == 'outdoor' else 'any',
            cost=dict(kind='unknown', min_toman=None, max_toman=None, basis='per_person',
                verified_at=None, valid_until=None,
                note='هزینه‌دار؛ قیمت بلیت، سفارش یا کارگاه با محل و روز تغییر می‌کند. مبلغ همهٔ نفرها، اجارهٔ ابزار و رفت‌وآمد را پیش از خرید بپرس؛ قیمت تأییدشده نداریم.'),
            safety_notes=safety)
        raw.update(OVERRIDES.get(key, {}))
        raw.update(profile)
        if dimension == 'affiliation' and 'solo' in raw['supported_social_modes']:
            raw.update(supported_social_modes=['together'], min_people=max(2, raw['min_people']))
        if raw['active_minutes'] != minutes:
            raw['conditions_note'] = raw['conditions_note'].replace(f'{minutes} دقیقه', f"{raw['active_minutes']} دقیقه", 1)
        if group in ('cinema', 'theatre', 'music'):
            raw['lighter_version'] = 'سانس کوتاه‌تر یا اجرای کوچک‌تر همین نوع برنامه را انتخاب کن؛ مدت واقعی و امکان خروج را پیش از خرید بپرس و کوتاه‌تر شدن خودکار اجرا را فرض نکن.'
        if group in ('museum', 'heritage', 'garden', 'local_tour'):
            raw['lighter_version'] = 'با هماهنگی محل فقط یک بخش یا مسیر کوتاه‌تر از همین بازدید را انتخاب کن و برای نشستن در محل مجاز زمان بگذار؛ شرایط همان محل را دوباره بپرس.'
        if key == 'iran-local_tour-07':
            raw['materials_note'] = 'گوشی دوربین‌دارِ در دسترس لازم است؛ شارژ و فضای ذخیره را بررسی کن. دوربین حرفه‌ای الزامی نیست.'
        if 'towel' in raw['required_items']:
            raw['materials_note'] = 'حولهٔ شخصی و پوشش شنای مورد تأیید استخر لازم است؛ بقیهٔ وسایل و هزینهٔ اجاره را پیش از رزرو بپرس.'
        content = Content.model_validate(raw).model_dump(mode='json')
        entries.append(dict(key=key, category=group, category_label=label, source_ids=evidence,
            evidence_scope='category_examples_only', availability_verified=False,
            price_verified=False, content=content))
    if len(entries) != 300 or set(counts) != set(GROUPS):
        raise ValueError(f'Expected 300 recipes in 25 groups, got {len(entries)}: {dict(counts)}')
    if set(alignment['entries']) != {entry['key'] for entry in entries}:
        raise ValueError('DRAMMA mapping must cover exactly the recipe keys')
    if len({e['content']['title'] for e in entries}) != 300:
        raise ValueError('Duplicate titles')
    if any(source not in sources['sources'] for e in entries for source in e['source_ids']):
        raise ValueError('Unknown source reference')
    return dict(version='iran_catalog_v1', authored_on='2026-11-13', origin='demo',
        human_approval=False, sources=sources['sources'], entries=entries)


if __name__ == '__main__':
    payload = build()
    (ROOT / 'content/iran-catalog.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    index = ['# فهرست ۳۰۰ تفریح تازهٔ ایران', '',
        '۱۳ نوامبر ۲۰۲۶؛ تجربه‌های تألیفی و آمادهٔ اجرا با شرط بررسی محل، سانس، وسایل و قیمت. این فهرست بلیت یا موجودی زنده نیست.', '',
        'مدت‌ها سقف برنامه‌ریزی با ۳۰ دقیقه پذیرش و حداکثر ۶۰ دقیقه رفت‌وبرگشت‌اند؛ اگر شرایط واقعی جا نمی‌شود این نوبت را انتخاب نکن. قیمت همهٔ موارد نیاز به بررسی دارد.', '']
    current = None
    for position, entry in enumerate(payload['entries']):
        if current != entry['category']:
            current = entry['category']
            index += [f"## {entry['category_label']}", '', '| کلید پایدار | تفریح | هدف اصلی | سقف زمان کل، دقیقه |', '| --- | --- | --- | --- |']
        total = sum(entry['content'][key] for key in ('active_minutes', 'setup_minutes', 'travel_minutes'))
        dimension = DIMENSION_LABELS[entry['content']['primary_dimension']]
        index.append(f"| {entry['key']} | {entry['content']['title']} | {dimension} | {total} |")
        if position + 1 == len(payload['entries']) or payload['entries'][position + 1]['category'] != current:
            index.append('')
    (ROOT / 'content/iran-catalog-index.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    print(json.dumps(dict(entries=len(payload['entries']), groups=Counter(e['category'] for e in payload['entries'])), ensure_ascii=False))
