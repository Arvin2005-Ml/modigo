"""Read-only catalog coverage using the same hard filters as recommendations.

Run: PYTHONPATH=apps/api .venv/bin/python -m app.modules.recommendations.coverage
Read-only against the configured public MongoDB catalog. No model key is needed.
"""
from datetime import datetime, timezone
from itertools import product

from app.core.schemas import Context
from app.modules.recommendations.eligibility import eligible

MINUTES = (5, 15, 30, 60, 120, 480)
PARTIES = (('solo', 1), ('together', 2), ('together', 3), ('together', 4),
           ('together', 8), ('together', 12), ('either', 1), ('either', 2), ('either', 12))
VENUES = ('home', 'away_from_home', 'any', 'outdoor', 'indoor_public')
BUDGETS = ({'mode': 'free'}, {'mode': 'cap', 'cap_toman': 1}, {'mode': 'flexible'})


def coverage(candidates, now):
    rows = []
    for minutes, (social, people), venue, budget in product(MINUTES, PARTIES, VENUES, BUDGETS):
        context = Context(available_minutes=minutes, social_mode=social, party_size=people,
                          venue=venue, budget=budget, energy='low', mood='skip').model_dump()
        accessible = {**context, 'max_mobility': 'seated', 'requires_step_free': True, 'requires_quiet': True}
        rows.append(dict(available_minutes=minutes, social_mode=social, party_size=people,
            venue=venue, budget_mode=budget['mode'],
            eligible_count=sum(eligible(context, a, now) is not None for a in candidates),
            quiet_seated_count=sum(eligible(accessible, a, now) is not None for a in candidates)))
    return rows


def markdown(candidates, now):
    rows = coverage(candidates, now)
    labels = {'home': 'خانه', 'away_from_home': 'بیرون از خانه', 'any': 'هرجا',
              'outdoor': 'هوای آزاد (قرارداد قبلی)', 'indoor_public': 'سرپوشیده (قرارداد قبلی)'}
    lines = ['# پوشش کاتالوگ نمایشی', '', f'تاریخ تولید: {now:%Y-%m-%d}؛ {len(candidates)} تجربهٔ فعالِ نمایشی.', '',
        f'{len(rows)} ترکیب زمان، همراه، محیط و بودجه با تابع واقعی فیلتر بررسی شد. '
        f'کمینهٔ گزینهٔ معتبر: {min(r["eligible_count"] for r in rows)}؛ '
        f'سلول‌های زیر شش گزینه: {sum(r["eligible_count"] < 6 for r in rows)}.', '',
        'همهٔ ردیف‌ها بدون وسیله، بدون اجازهٔ تماس و با هوا/روشنایی نامعلوم‌اند. '
        'بودجه‌ها رایگان، سقف یک تومان و منعطف‌اند؛ انرژی و حال در فیلتر سخت نقشی ندارند. '
        'اعداد تعداد گزینه‌های قابل اجرا در کاتالوگ‌اند؛ هر بار فقط یک کارت نمایش داده می‌شود، با حداکثر شش تعویض تازه و مرور دیده‌شده‌ها بدون مصرف سهمیه.', '',
        '| محیط | همراه / تعداد کل | ۵ دقیقه | ۱۵ | ۳۰ | ۶۰ | ۱۲۰ | ۴۸۰ |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for venue, (social, people) in product(VENUES, PARTIES):
        counts = [str(next(r['eligible_count'] for r in rows if r['venue'] == venue and
                  r['social_mode'] == social and r['party_size'] == people and
                  r['available_minutes'] == m and r['budget_mode'] == 'free')) for m in MINUTES]
        label = {'solo': 'تنها', 'together': 'همراه', 'either': 'فرقی ندارد'}[social]
        lines.append(f'| {labels[venue]} | {label} / {people} | ' + ' | '.join(counts) + ' |')
    lines += ['', f'با افزودن هم‌زمان شرط سکوت، نشسته و بدون پله، کمینهٔ گزینه‌ها '
        f'{min(r["quiet_seated_count"] for r in rows)} است و '
        f'{sum(r["quiet_seated_count"] < 6 for r in rows)} سلول زیر شش گزینه دارد.', '',
        'این گزارش برای نخستین نوبت و بدون موضوع مسدود است. موضوع‌های مسدود، کنارگذاشتن محتوا، '
        'فعالیت فعال و جلوگیری از تکرار در تعویض یا نوبت بعد می‌توانند تعداد را کم کنند؛ '
        'فیلترها برای پُرکردن سهمیه تغییر نمی‌کنند. شش گزینه فقط یک اولیه و پنج تعویض را پوشش می‌دهد؛ شش تعویض کامل به هفت گزینه نیاز دارد و برای همهٔ محدودیت‌های دلخواه تضمین نیست.', '',
        'فعالیت‌های بیرون و سرپوشیده فقط در محل امن، مجاز و از قبل در دسترس اجرا می‌شوند؛ '
        'این گزارش وجود مکان، بلیت، مسیر یا آب‌وهوای مناسب را تأیید نمی‌کند. '
        'نمونه‌های وابسته به هوای مناسب یا روز در شمارش پایه وارد نمی‌شوند.', '',
        'منشأ محتوا `demo` و صرفاً محلی است. این شمارش ارزیابی جذابیت توسط کاربر یا تأیید انتشار عمومی نیست.', '',
        'بازتولید از ریشهٔ مخزن:', '', '```sh',
        'PYTHONPATH=apps/api .venv/bin/python -m app.modules.recommendations.coverage', '```', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    from app.core.storage import create_store
    from app.modules.catalog.service import Catalog
    now = datetime.now(timezone.utc)
    store = create_store()
    try:
        print(markdown(Catalog(store, lambda: now).candidates(), now), end='')
    finally:
        store.close()
