"""Supported origins and reviewed domestic areas for full-day outings."""

# Order is part of the form contract. These are coverage choices, not a population ranking.
OUTING_ORIGINS = {
    'tehran': 'تهران',
    'mashhad': 'مشهد',
    'isfahan': 'اصفهان',
    'shiraz': 'شیراز',
    'tabriz': 'تبریز',
}
OUTING_DESTINATIONS = {
    'تهران': frozenset(('تهران', 'شهرری', 'ورامین', 'لواسان', 'کرج', 'طالقان', 'قزوین')),
    'مشهد': frozenset(('مشهد', 'توس', 'طرقبه', 'شاندیز', 'چناران', 'رادکان', 'نیشابور', 'قدمگاه')),
    'اصفهان': frozenset(('اصفهان', 'نطنز', 'ابیانه', 'کاشان', 'نیاسر', 'اردستان', 'نائین')),
    'شیراز': frozenset(('شیراز', 'مرودشت', 'پاسارگاد', 'سروستان', 'فیروزآباد', 'کازرون', 'مهارلو')),
    'تبریز': frozenset(('تبریز', 'اسکو', 'کندوان', 'مرند', 'جلفا', 'مراغه', 'اهر')),
}
OUTING_ONE_WAY_LIMIT = {1: 120, 2: 180}
MINUTES_PER_DAY = 24 * 60
