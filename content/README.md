# بانک اولیهٔ ۴۵۰ بذر تفریح

**مجموعهٔ جاری — ۱۴ نوامبر ۲۰۲۶:** [فهرست ۷۰۰ تفریح](../content/real-catalog-index.md)، [JSON کامل](../content/real-catalog.json) و [CSV](../exports/real-activities-700.csv) شامل ۴۰۰ تجربهٔ دارای مکان/شهر/منبع و ۳۰۰ دستور عملی خانگی است. [قرارداد ورود و محدودیت‌های واقعی](../docs/28-real-catalog-700.md). شمارهای ۸۸۱/۴۳۱/۴۱۳ در ادامه، خروجی تاریخی release قبلی‌اند و تعداد زندهٔ Mongo را نشان نمی‌دهند.


**انطباق DRAMMA — ۱۴ نوامبر۲۰۲۶:** همهٔ۴۳۱ محتوای پخته و شش قالب نمایشی دارای هدف و ارجاع به قدم اجرایی‌اند؛ نگاشت۳۰۰ تفریح ایران موردی است. انتشار و شروع، این قرارداد را کنترل می‌کنند. [شرح و محدودیت‌ها](../docs/27-dramma-alignment.md).

این بانک برای شروع طراحی محتوا تألیف شده و «۴۵۰ تفریح رسمی DRAMMA» نیست. اگر مالک بانک خودش را دارد،import با mapping و حفظ سابقه انجام شود. همهٔ ردیف‌ها **raw/draft** هستند؛ هیچ زمان،هزینه،دسترس‌پذیری یا اثر روان‌شناختی از عنوان به‌تنهایی معتبر فرض نشود.

| فایل | prefix | primary_dimension | نام انسانی | تعداد |
| --- | --- | --- | --- | --- |
| [فاصله از کار](seeds-detachment.md) | D | detachment | یه فاصله از روزمرگی |۷۵|
| [آرامش](seeds-relaxation.md) | R | relaxation | یه مکث آروم |۷۵|
| [اختیار](seeds-autonomy.md) | A | autonomy | به سلیقهٔ خودت |۷۵|
| [تسلط](seeds-mastery.md) | M | mastery | یه چیز تازه یاد بگیر |۷۵|
| [معنا](seeds-meaning.md) | N | meaning | یه کار باارزش برای تو |۷۵|
| [ارتباط](seeds-affiliation.md) | F | affiliation | یه لحظه کنار هم |۷۵|

prefixهای N و F صرفاً برای شناسهٔ بی‌ابهام‌اند؛ DRAMMA همچنان همان شش نیاز است. ستون‌ها `seed_key / raw_title / raw_intent`؛ dimension از فایل گرفته شود. شناسه‌ها از001تا075 و پایدارند. parser،جدول کامل را بخواند و از شماره‌گذاری نمایشی استنتاج نکند. مجموع۴۵۰،شناسه‌ها و عنوان‌های خام یکتا؛ تکرار معنایی همچنان نیازمند review است. فعالیت می‌تواند secondary dimension داشته باشد؛ primary بیانگر **قصد این نسخه** است،نه ماهیت ثابت خود فعالیت.

## مسیر تبدیل

بذر ← پختن با قرارداد05 و08 ← بررسی واقعی شرایط ← preview ← انتشار. برای نمونهٔ کیفیت [شش تجربهٔ پخته](cooked-examples.md) را ببین. اگر وسیله یا مکان نداریم یا قیمت نامعلوم است،metadata صادقانه و eligibility محدود باشد؛ کیفیت برای رسیدن به عدد۴۵۰ قربانی نشود. انتخاب بیرونی،تماس و فعالیت بدنی باید فقط با شرایط سازگار ارائه شوند.

## واژگان کنترل‌شدهٔ اولیه `taxonomy_v1`

tagهای مجاز:

```text
observation, sensory, imagination, play, nature, walking, music, listening,
reading, writing, drawing, photography, craft, puzzles, language, rhythm,
movement, dance, rest, reflection, storytelling, memory, gratitude, kindness,
community, culture, family, friendship, conversation, cooperation, food,
gardening, discovery, choice, creativity, mindfulness, science, games,
design, humor, outdoors, indoors, no_screen, digital
```

itemهای مجاز:

```text
paper, pen, colored_pencils, scissors, glue, tape, cardboard, yarn,
needle, fabric, clay, phone, internet, headphones, speaker, book,
camera, board_game, playing_cards, dice, ball, bicycle, yoga_mat,
plant, pot, soil, kitchen, food_ingredients, towel, blanket, cushion,
musical_instrument, computer, puzzle, binoculars
```

هر item صرفاً مالکیت/دسترسی اعلام‌شده است و ایمنی یا مهارت را اثبات نمی‌کند. required_items فقط وسایل لازم،نه تزئینی؛ مثلاً تمرین شنیدن بدون گوشی ممکن است هیچ item نخواهد. تغییر واژگان version و migration و هماهنگی UI دارد. هنگام cook چیزی خارج این لیست به‌عنوان enum نپذیر؛ بذر نیازمند ابزار تازه ابتدا به editor برگردد.

## کاتالوگ محلی — ۹ نوامبر ۲۰۲۶

`demo-catalog.json` شامل ۱۰۷ تجربهٔ تألیفی با کلید پایدار و تمام فیلدهای `Content` است؛ JSON کامل منبع قابل ویرایش است و هنگام اجرا با schema واقعی بررسی می‌شود. `version=demo_catalog_v2` نسخهٔ بسته است؛ taxonomy و قرارداد API تغییر نکرده‌اند. تولید در لحظه یا وابستگی به کلید مدل وجود ندارد.

شش نمونهٔ `cooked-examples.md` فعال می‌مانند. هجده نمونهٔ قدیمی `demo-extra.json` برای بررسی نگه داشته شده‌اند، اما از پیشنهادها کنار رفته‌اند: شناسه‌های `demo:007` تا `demo:024` غیرفعال و revision آن‌ها archived است. جمع کاتالوگ نمایشی ۱۳۱ رکورد، شامل **۱۱۳ فعال** و ۱۸ کنارگذاشته‌شده است؛ بانک خام ۴۵۰تایی جدا و همچنان draft است.

تجربه‌های تازه بازی کلامی و بی‌صدا، معما، نمایش، اوریگامی، بازی ورق، نقاشی، کمیک، کتاب، عکاسی، موسیقی و حرکت را پوشش می‌دهند. نمونه‌های کوتاه بدون ابزار برای خانه، فضای باز و سرپوشیده و اجرای تنها/همراه جدا نوشته شده‌اند؛ گروه‌های بزرگ در نمونه‌های مناسب به زیرگروه تقسیم می‌شوند. تجربه‌های طولانی‌تر و نیازمند ابزار فقط با وسایل اعلام‌شده پیشنهاد می‌شوند. تعداد و شرایط بررسی‌شده در [گزارش پوشش](../docs/22-catalog-coverage.md) آمده است؛ این گزارش جای بازخورد کاربر و review پیش از انتشار عمومی را نمی‌گیرد.

## خروجی CSV و JSON

فرمان `.venv/bin/python scripts/export-activities.py` از ریشه، خروجی بانک جاری مالک و کاتالوگ پخته را در `exports/activities.csv` و `exports/cooked-activities.json` می‌سازد. منبع، فایل‌های پروژه است و وضعیت زندهٔ MongoDB را ادعا نمی‌کند. شرح ستون‌ها، تعدادها و زمان‌های ثبت‌نشده در [راهنمای خروجی](../exports/README.md) آمده است.

## کاتالوگ۳۰۰تایی هزینه‌دار — ۱۳ نوامبر ۲۰۲۶

`iran-catalog.json` محتوای پختهٔ۳۰۰ تفریح تألیفی در۲۵ گروه را دارد؛ [فهرست عنوان‌ها](iran-catalog-index.md) برای مرور و `iran-recipes.txt` برای ویرایش قدم‌های اختصاصی است. `scripts/build-iran-catalog.py` محتوای کامل را بازتولید و با `Content` واقعی validate می‌کند. ترتیب ردیف‌ها در هر گروه برای ثبات کلیدها تغییر نکند؛ مورد جدید به انتها افزوده شود. پس از اصلاح فایل دستورها، builder و exporter اجرا شوند.

تمام موارد جدید هزینه‌دار با قیمت `unknown` و نیازمند بررسی محل و ظرفیت‌اند؛ در بودجهٔ free/cap یا بدون رضایت `allow_venue_planning` وارد پیشنهاد نمی‌شوند. کارت و جزئیات این شرط را آشکار نشان می‌دهند. زمان‌ها سقف انتخاب سانس و مسیرند و وعدهٔ زمان سفر واقعی نیستند. منابع در `iran-sources.json` و JSON خروجی آمده‌اند؛ وجود دستهٔ فعالیت با تأیید رزرو امروز یا برگزاری هر کارگاه در هر شهر یکی نیست. درخواست جاری مالک برای گسترش تفریح‌های مکان‌محور و حدود آن در [سند26](../docs/26-iran-paid-catalog.md) ثبت است.

جمع تعریف‌شده اکنون۴۳۱ محتوای پخته،۴۱۳ فعال اولیه و۱۸ archived است؛۴۵۰ بذر خام جدا باقی می‌مانند. import کلیدها را تکرار و withdrawn را فعال نمی‌کند. `origin=demo` و فقدان تأیید انسانی حفظ شده و خروجی واقعی مدل ادعا نشده است. `exports/iran-activities.csv` فقط همین۳۰۰مورد را با تمام متن و metadata ارائه می‌کند. ورود به MongoDB زنده در این محیط به‌علت دریافت‌نشدن driver تأیید نشده است.
