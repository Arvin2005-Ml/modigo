# شش نمونهٔ پختهٔ تألیفی

این نمونه‌ها دستی و برای روشن‌شدن کیفیت و قرارداد نوشته شده‌اند؛ خروجی واقعی GapGPT یا محتوای تأییدشده توسط مالک نیستند. هر JSON یک `content` کامل مطابق05 است؛ seed_key در عنوان بخش،جزو خروجی مدل نیست. همه برای شرایط مشخص و بدون دادهٔ محلی طراحی شده‌اند. این شش نمونه الزاماً در یک نوبت به یک نفر نمایش داده نمی‌شوند: نمونهٔ گروهی به کاربر solo و نمونهٔ دارای قلم به کاربر بدون وسیله پیشنهاد نشود.

## D001 — از «شکار شکل‌ها» به یک بازی دیداری کوچک

```json
{
  "title": "توی وسایل خونه شکل تازه پیدا کن",
  "teaser": "شاید دستهٔ لیوان شبیه گوش یه موجود خیالی باشه؛ چند دقیقه خونه رو جور دیگه ببین.",
  "first_step": "از همون جایی که راحتی،سه شکل توی وسایل اطرافت پیدا کن.",
  "steps": [
    "سه وسیله رو فقط با نگاه انتخاب کن؛ لازم نیست چیزی جابه‌جا کنی.",
    "برای هرکدوم یه شباهت بامزه پیدا کن:حیوان،چهره یا یه جای خیالی.",
    "به یکی‌شون اسم بده و توی ذهنت یه ماجرای کوتاه براش بساز."
  ],
  "lighter_version": "فقط برای یه وسیله یه اسم خیالی پیدا کن و همین‌جا تمومش کن.",
  "materials_note": "وسیلهٔ خاصی لازم نیست؛ فقط چیزهایی که از جات می‌بینی.",
  "accessibility_note": "می‌تونی نشسته و بدون جابه‌جایی انجامش بدی؛ این نسخه به دیدن محیط وابسته‌ست.",
  "conditions_note": "در فضای آشنای خانه و از جای راحت و امن انجامش بده.",
  "primary_dimension": "detachment",
  "secondary_dimensions": ["autonomy"],
  "tags": ["observation", "imagination", "play", "no_screen"],
  "active_minutes": 10,
  "setup_minutes": 0,
  "travel_minutes": 0,
  "energy_required": "low",
  "mobility_required": "seated",
  "supported_social_modes": ["solo"],
  "min_people": 1,
  "max_people": 1,
  "venue": "home",
  "required_items": [],
  "requires_async_contact": false,
  "step_free": true,
  "quiet_compatible": true,
  "weather_requirement": "any",
  "daylight_requirement": "any",
  "cost": {"kind":"free","min_toman":0,"max_toman":0,"basis":"per_person","verified_at":null,"valid_until":null,"note":"با فضای موجود؛ خرید یا رفت‌وآمد لازم نیست."},
  "safety_notes": []
}
```

## R001 — از «شنیدن صدای خانه» به یک مکث شنیداری

```json
{
  "title": "صدای خونه رو پیدا کن",
  "teaser": "یه جای راحت بمون و چند دقیقه فقط شنوندهٔ صداهای همین اطرافت باش.",
  "first_step": "در همون جای امنی که هستی،یه حالت نشستن راحت پیدا کن.",
  "steps": [
    "گوشی رو لازم نیست برداری؛ فقط دنبال یه صدای نزدیک بگرد.",
    "حالا اگه صدای دورتری هست،چند لحظه به اون گوش بده؛ لازم نیست منبعش رو پیدا کنی.",
    "هر وقت حواست رفت جای دیگه،می‌تونی برگردی به یه صدا یا همین‌جا مکث رو تموم کنی."
  ],
  "lighter_version": "فقط یه صدای نزدیک رو پیدا کن و چند لحظه بشنوش؛ بیشترش اختیاریه.",
  "materials_note": "وسیله،موسیقی و هدفون لازم نیست.",
  "accessibility_note": "نشسته و بدون حرکت انجام می‌شه؛ این نسخه به شنیدن صدا وابسته‌ست.",
  "conditions_note": "از جای امن و آشنای خانه انجام بده؛ به صداهای ناخوشایند اصرار نکن.",
  "primary_dimension": "relaxation",
  "secondary_dimensions": ["detachment"],
  "tags": ["listening", "sensory", "rest", "no_screen"],
  "active_minutes": 5,
  "setup_minutes": 0,
  "travel_minutes": 0,
  "energy_required": "low",
  "mobility_required": "seated",
  "supported_social_modes": ["solo"],
  "min_people": 1,
  "max_people": 1,
  "venue": "home",
  "required_items": [],
  "requires_async_contact": false,
  "step_free": true,
  "quiet_compatible": true,
  "weather_requirement": "any",
  "daylight_requirement": "any",
  "cost": {"kind":"free","min_toman":0,"max_toman":0,"basis":"per_person","verified_at":null,"valid_until":null,"note":"بدون وسیله و خرید تازه."},
  "safety_notes": []
}
```

## A001 — از «انتخاب آزاد» به انتخاب و انجام واقعی

```json
{
  "title": "این چند دقیقه قانونش با توئه",
  "teaser": "بین خیال‌پردازی،تماشای جزئیات و ساختن یه قصه یکی رو بردار؛ فقط چون دلت می‌خواد.",
  "first_step": "یکی رو انتخاب کن:دیدن سه جزئیات اطرافت،ساختن یه جای خیالی،یا یه قصهٔ توی ذهن.",
  "steps": [
    "از بین سه گزینه یکی رو بدون دلیل‌آوردن انتخاب کن؛ هر سه می‌تونن بی‌وسیله باشن.",
    "چند دقیقه همون کار رو انجام بده؛ جزئیات،شخصیت‌ها یا منظره رو خودت تعیین کن.",
    "اگه خواستی مسیرش رو عوض کن؛ وقتی برات کافیه،پایانش هم انتخاب خودته."
  ],
  "lighter_version": "فقط یک جزئیات اطرافت رو انتخاب کن و برای چند لحظه به روش دلخواهت ببینش.",
  "materials_note": "هیچ وسیله‌ای لازم نیست؛ همهٔ گزینه‌ها توی ذهن یا با نگاه انجام می‌شن.",
  "accessibility_note": "می‌تونی نشسته بمونی؛ اگر تماشا مناسب تو نیست،قصه یا جای خیالی رو انتخاب کن.",
  "conditions_note": "در جای آشنا و راحت خانه؛ این تجربه آزمون تصمیم‌گیری نیست.",
  "primary_dimension": "autonomy",
  "secondary_dimensions": ["detachment"],
  "tags": ["choice", "imagination", "creativity", "no_screen"],
  "active_minutes": 10,
  "setup_minutes": 0,
  "travel_minutes": 0,
  "energy_required": "low",
  "mobility_required": "seated",
  "supported_social_modes": ["solo"],
  "min_people": 1,
  "max_people": 1,
  "venue": "home",
  "required_items": [],
  "requires_async_contact": false,
  "step_free": true,
  "quiet_compatible": true,
  "weather_requirement": "any",
  "daylight_requirement": "any",
  "cost": {"kind":"free","min_toman":0,"max_toman":0,"basis":"per_person","verified_at":null,"valid_until":null,"note":"هیچ خرید،اشتراک یا وسیله‌ای نیاز نیست."},
  "safety_notes": []
}
```

## M001 — از «طراحی» به تمرین کوچک با تفاوت قابل دیدن

```json
{
  "title": "یه نقاشی با یه خط بکش",
  "teaser": "قلم رو برندار؛ بذار یه شیء ساده با یه خط پیوسته روی کاغذ پیداش بشه.",
  "first_step": "قلم و کاغذی که داری بردار و یه شیء سادهٔ قابل دیدن انتخاب کن.",
  "steps": [
    "قلم رو روی کاغذ بذار و بدون برداشتنش دور شکل شیء حرکت کن؛ شبیه‌شدن کامل لازم نیست.",
    "بار دوم همون شیء رو بکش،این بار یه جزئیات کوچیک رو بیشتر ببین.",
    "دو طرح رو کنار هم نگاه کن و فقط یه تفاوت جالب پیدا کن؛ لازم نیست بهتر و بدترشون کنی."
  ],
  "lighter_version": "به‌جای کل شیء،فقط دور یک بخش ساده‌ش رو با یه خط بکش.",
  "materials_note": "یک قلم و یک کاغذ موجود؛ نوع خاص یا ابزار تازه لازم نیست.",
  "accessibility_note": "نشسته قابل انجامه؛ این نسخه به کنترل قلم و دیدن شیء نیاز داره.",
  "conditions_note": "فضای روشن و راحت برای دیدن کاغذ و شیء؛ آماده‌سازی توی زمان حساب شده.",
  "primary_dimension": "mastery",
  "secondary_dimensions": ["autonomy", "detachment"],
  "tags": ["drawing", "observation", "creativity", "no_screen"],
  "active_minutes": 13,
  "setup_minutes": 2,
  "travel_minutes": 0,
  "energy_required": "medium",
  "mobility_required": "seated",
  "supported_social_modes": ["solo"],
  "min_people": 1,
  "max_people": 1,
  "venue": "home",
  "required_items": ["paper", "pen"],
  "requires_async_contact": false,
  "step_free": true,
  "quiet_compatible": true,
  "weather_requirement": "any",
  "daylight_requirement": "any",
  "cost": {"kind":"free","min_toman":0,"max_toman":0,"basis":"per_person","verified_at":null,"valid_until":null,"note":"فقط با قلم و کاغذی که از قبل داری؛ خرید لازم نیست."},
  "safety_notes": []
}
```

## N001 — از «قدردانی» به مرور اختیاری و بی‌فشار

```json
{
  "title": "سه لحظهٔ کوچیک برای خودت نگه دار",
  "teaser": "لازم نیست اتفاق بزرگی افتاده باشه؛ فقط چند لحظهٔ راحت که برای خودت ارزش داشتن.",
  "first_step": "یه اتفاق کوچک و بی‌حساسیت رو یاد بیار که دوست داشتی همون‌طور می‌موند.",
  "steps": [
    "یکی از جزئیات اون لحظه رو توی ذهنت ببین؛مثلاً نور،یه جمله یا صدای آشنا.",
    "اگه دوست داشتی دو لحظهٔ دیگه هم اضافه کن؛پیدانشدنشون اشکالی نداره.",
    "برای یکی‌شون یه اسم کوتاه بساز؛فقط برای خودت،بدون نیاز به نوشتن یا فرستادن."
  ],
  "lighter_version": "فقط به یک چیز ساده که همین الان برات خوشاینده توجه کن؛مرور گذشته لازم نیست.",
  "materials_note": "کاغذ،گوشی یا اشتراک‌گذاری لازم نیست؛می‌تونه فقط ذهنی باشه.",
  "accessibility_note": "نشسته و بدون وسیله انجام می‌شه؛مرور خاطره کاملاً اختیاریه.",
  "conditions_note": "موضوع‌های سبک و راحت انتخاب کن؛اگر دوستش نداشتی می‌تونی تجربهٔ دیگه‌ای برداری.",
  "primary_dimension": "meaning",
  "secondary_dimensions": ["relaxation"],
  "tags": ["reflection", "memory", "gratitude", "no_screen"],
  "active_minutes": 10,
  "setup_minutes": 0,
  "travel_minutes": 0,
  "energy_required": "low",
  "mobility_required": "seated",
  "supported_social_modes": ["solo"],
  "min_people": 1,
  "max_people": 1,
  "venue": "home",
  "required_items": [],
  "requires_async_contact": false,
  "step_free": true,
  "quiet_compatible": true,
  "weather_requirement": "any",
  "daylight_requirement": "any",
  "cost": {"kind":"free","min_toman":0,"max_toman":0,"basis":"per_person","verified_at":null,"valid_until":null,"note":"هیچ ابزار یا خریدی نیاز نیست."},
  "safety_notes": []
}
```

## F001 — از «با هم حرف‌زدن» به یک بازی نوبتی روشن

```json
{
  "title": "یه قصه رو نوبتی بسازین",
  "teaser": "تو یه جمله بگو،نفر بعد یکی اضافه کنه؛ببینین قصهٔ بی‌نقشه‌تون کجا می‌ره.",
  "first_step": "از همراه‌های موافق بخواه راحت بشینن و برای یه قصهٔ خیالی نوبت بذارین.",
  "steps": [
    "یکی با یه جملهٔ ساده شروع کنه؛مثلاً یه روز یه ابر کوچیک راهش رو گم کرد.",
    "هر نفر فقط یه جمله اضافه کنه؛لازم نیست قصه واقعی،منطقی یا خیلی بامزه بشه.",
    "بعد از چند دور،با هم یه پایان کوتاه براش پیدا کنین؛هر نفر می‌تونه نوبتش رو رد کنه."
  ],
  "lighter_version": "هر نفر فقط یه جمله بگه و همون قصهٔ خیلی کوتاه رو با هم تموم کنین.",
  "materials_note": "هیچ وسیله‌ای لازم نیست؛ضبط‌کردن هم جزو این بازی نیست.",
  "accessibility_note": "نشسته انجام می‌شه؛این نسخه بر گفت‌وگوی شنیداری تکیه داره و فضای کاملاً ساکت نمی‌خواد.",
  "conditions_note": "دو تا چهار نفرِ آشنا و مایل،از قبل در خانه کنار هم باشین؛زمان جمع‌شدن کوتاه حساب شده.",
  "primary_dimension": "affiliation",
  "secondary_dimensions": ["autonomy", "detachment"],
  "tags": ["storytelling", "conversation", "cooperation", "play"],
  "active_minutes": 10,
  "setup_minutes": 2,
  "travel_minutes": 0,
  "energy_required": "low",
  "mobility_required": "seated",
  "supported_social_modes": ["together"],
  "min_people": 2,
  "max_people": 4,
  "venue": "home",
  "required_items": [],
  "requires_async_contact": false,
  "step_free": true,
  "quiet_compatible": false,
  "weather_requirement": "any",
  "daylight_requirement": "any",
  "cost": {"kind":"free","min_toman":0,"max_toman":0,"basis":"per_group","verified_at":null,"valid_until":null,"note":"برای همراه‌های حاضر و بدون خرید یا رفت‌وآمد."},
  "safety_notes": ["از خاطرهٔ خصوصی یا مسخره‌کردن آدم‌های واقعی برای قصه استفاده نکنین."]
}
```

## الگوی بد در برابر خروجی مطلوب

«یه کم نقاشی کن؛حالت بهتر می‌شه» کافی نیست:نه نقطهٔ شروع،نه وسایل،نه زمان و نه حق توقف روشن است. نمونهٔ M001 عمل اول،زمان۱۵دقیقه شامل۲دقیقه آماده‌سازی،قلم و کاغذِ موجود و نسخهٔ کوچک‌تر دارد؛اثر احساسی را تضمین نمی‌کند. همین تفاوت معیار پختن همهٔ بانک است.
