# پیشنهاددهی بدون دادهٔ آموزش

نسخهٔ الگوریتم `needs_history_v2` طبق [23](23-single-suggestion.md). cold start با محتوای برچسب‌خورده حل می‌شود. نتیجه احتمالی و قابل توضیح است؛ برچسب علمی یا ادعای شناخت شخصیت ندارد. فقط یک پیشنهاد هم‌زمان و حداکثر شش جایگزین تازه، همراه مرور رایگان دیده‌شده‌ها. هر گزینه مستقل با وقت و شرایط کاربر سنجیده می‌شود.

## مرحله۱: snapshot و فیلتر سخت

از آخرین revision منتشرشدهٔ هر activity فعال استفاده شود. context نرمال و constraints ماندگار merge شوند. فقط موارد زیر eligible هستند:

۱. total_minutes<=available_minutes؛ رفت‌وآمد و setup شمرده شوند. برای جایی که زمان رفت‌وآمد ناشناخته است سفر صفر حدس نزن؛ محتوا باید شرط «در دسترس در زمان مشخص» معتبر داشته باشد یا نیاز سفر را روشن کند.
۲. تطابق venue؛ any همهٔ سه محیط. social solo فقط solo، together فقط together و min/max گروه سازگار، either طبق party_size سند05. تعداد اجرا برای candidate تک‌نفره همیشه۱است و برای گروهی همان party_size؛ هزینه و حدود گروه بر اساس آن‌اند. candidate با هر دو social mode ابتدا mode سازگار انتخاب کند،برای either نسخهٔ solo اولویت دارد تا نیاز به جمع اضافه ایجاد نکند؛ mode انتخاب‌شده در item با `execution_social_mode` و `execution_people` ثبت و در start حفظ شود.
۳. هزینهٔ کل گروه: free فقط free؛ cap فقط free یا estimated تأییدشده و منقضی‌نشده با max_total<=cap؛ unknown فقط flexible. اعدادِ تولیدشده توسط مدل معتبر نیستند.
۴. required_items زیرمجموعهٔ owned_items. فهرست خالی یعنی هیچ وسیله‌ای لازم نیست؛ phone و internet خودکار فرض نشوند.
۵. mobility_required<=max_mobility؛ requires_step_free→step_free=true و requires_quiet→quiet_compatible=true. null سازگار محسوب نمی‌شود.
۶. تداخل با blocked_tags صفر؛ تماس async فقط با allow_async_contact؛ weather=fair و daylight=day هرجا metadata الزام کرده لازم‌اند. unknown شرط را تأمین نمی‌کند.
۷. برای ساخت و تعویض پیشنهاد،exclude فعالیت شروع‌شدهٔ فعال و همهٔ activityهای قبلاً عرضه‌شده در همین check-in؛ تکرار با revision جدید دور زده نشود. عرضه‌شدن به‌معنای قرارگرفتن در payload است؛ impression واقعی metric جدا دارد. این excludeها eligibility واقعی اجرا نیستند و موقع start دوباره اعمال نشوند. نسخه‌های archived و محتوای withdrawn همواره ممنوع.

انرژی، mood، goal، علاقه و سابقه soft preference هستند. انرژی بیشتر از کاربر را به‌شدت کم‌امتیاز کن، اما سخت‌گیری تحرک در max_mobility است. برای پُرکردن سهمیهٔ تعویض، نیاز جاری یا سابقهٔ انتخاب، فیلتر سخت را رها نکن.

## مرحله۲: امتیاز پایه

همهٔ featureها در [0,1]، وزن‌ها آغازین و تصمیم محصول‌اند و باید با پایلوت کالیبره شوند. tie-break با hash پایدار `(session.seed,activity_id)`، نه زمان اجرای تصادفی.

```text
base = 0.22*goal_fit + 0.20*energy_fit + 0.16*interest_fit
     + 0.14*time_fit + 0.10*mood_fit + 0.10*personal_feedback
     + 0.08*novelty
base = clamp(base - recent_penalty, 0, 1)
```

- goal_fit: هدف any→0.5 برای همه؛ unwind→relaxation، switch_off→detachment، learn→mastery، connect→affiliation، meaning→meaning، choose→autonomy. primary تطبیق۱، secondary تطبیق۰٫۷، بقیه۰٫۳.
- energy_fit: low/medium/high به۰/۱/۲؛ مساوی۱، نیاز کمتر۰٫۸، یک‌سطح بیشتر۰٫۲، دو‌سطح بیشتر۰. unknown→۰٫۵ برای همه.
- interest_fit: اگر liked_tags خالی ۰٫۵؛ وگرنه `|tags∩liked_tags|/|liked_tags|` با clamp؛ ترکیب با feedback جداست.
- time_fit: نسبت total/available؛ نسبت<=۰٫۲→۰٫۶، <=۰٫۸→۱، باقی→۰٫۸. پرکردن همهٔ وقت پاداش اضافی ندارد.
- mood_fit: skip/okay→۰٫۵؛ tired به relaxation و low-energy مقدار۱، restless به detachment و mobility light مقدار۱، bored به mastery/autonomy مقدار۱، low به relaxation/meaning مقدار۰٫۸؛ بقیه۰٫۵. این جدول فرض محصول است، نه نسخهٔ روان‌شناختی. اگر چند شرط برقرار شد max، نه جمع.
- personal_feedback: prior خنثی۰٫۵. حداکثر۱۰۰۰ بازخورد۹۰روز اخیر کاربر، روی tagهای مشترک: `(2 + sum(rating_value * overlap))/(4 + sum(overlap))`؛ liked=1،neutral=.5،disliked=0؛ overlap=Jaccard. بازخورد تغییرکرده فقط یک بار شمرده شود. حذف feedback خواندن بعد را عوض می‌کند.
- novelty: activity که هنوز در history کامل/عرضهٔ operational کاربر نیست۱، فقط عرضهٔ گذشته۰٫۵، completed قبلی۰٫۲۵. این feature برای همه از سوابق عملیاتی است و به consent analytics یا دیده‌شدن واقعی وابسته نیست.
- recent_penalty: completed در۷روز اخیر۰٫۲، عرضهٔ ثبت‌شده در۲۴ساعت اخیر۰٫۱؛ max این دو. علاقهٔ صریحِ مسدودشده قبلاً hard-filter می‌شود؛ dislike تک‌نوبتی block دائمی نیست.

## مرحله۳: نیاز جاری، ترجیح تدریجی و انتخاب

گزینهٔ مجاز با کلید `(need_fit, dimension_preference, base, stable_hash)` انتخاب می‌شود. پاسخ need_now وزن ۰٫۶ و desired_outcome وزن ۰٫۴ دارد؛ any کنار گذاشته و وزن باقی‌مانده نرمال می‌شود. نگاشت به primary dimension همان goal است. اگر هر دو any باشند، goal صریح یا پیش‌فرض حساب fallback است.

ترجیح بُعد از اولین شروع موفق هر recommendation session همان کاربر به دست می‌آید: `count_dimension/(total_selections+6)`. snapshot بُعد تجربه منبع است؛ لغو بعدی رأی را حذف یا اضافه نمی‌کند. مرور، بازکردن جزئیات، ذخیره، تعویض و پایان رأی تازه نیستند. نیاز اعلام‌شده مقدم بر سابقه است؛ در نیاز یکسان بُعد پرتکرارتر زودتر می‌آید و سپس base فعالیت ملاک است. بدون سابقه همهٔ ترجیح‌ها صفرند.

تولید جایگزین با همین context و تازه‌ترین فیلترها، پس از حذف همهٔ activityهای عرضه‌شده در همین check-in انجام می‌شود؛ تا شش موفقیت. مرور قبلی/بعدی تولید تازه و رتبه‌بندی دوباره نیست؛ snapshot قبلی را جاری می‌کند و سهمیه ثابت است. expected_version رقابت تعویض، مرور و شروع را کنترل می‌کند. context ثابت است؛ ویرایش سؤال‌ها check-in تازه می‌سازد.

تابع داخلی rank برای آزمون پوشش، count بیشتر از یک را می‌پذیرد و در آن حالت penalty شباهت ۰٫۱۲ و تکرار بُعد ۰٫۰۸ و سقف نرم ۲، سپس ۳ و ۶ دارد. مسیر واقعی API همیشه یک گزینه درخواست می‌کند؛ این قابلیت آزمون به معنی شش کارت در UI نیست.

## توضیح قابل نمایش

دلیل از templateهای server و feature واقعی بیاید، نه از LLM در لحظه. ابتدا نیاز جاریِ منطبق، سپس بُعد انتخاب‌شدهٔ قبلی، سپس علاقه/energy/goal که واقعاً برقرار است؛ «با وقت و انرژی الانت جور درمیاد»، «خونه و بدون خرج می‌تونی انجامش بدی»، «یه انتخاب برای یادگرفتن یه چیز کوچیک». متن ادعای احساس یا outcome نکند؛ وقتی energy_fit پایین است انرژی را دلیل نگو. score_breakdown فقط ادمین با حذف mood فردی در گزارش عمومی.

## مثال‌های قابل آزمون

۳۰دقیقه، solo،home،free،بدون وسیله: فعالیت۲۰+۵+۱۰دقیقه رد،۱۰+۰+۰ قبول؛ کافه با قیمت نامعلوم رد؛ بازی دونفره رد؛ کار با گوشی رد اگر owned_items خالی. در گروه۳نفره cap=۳۰۰هزارتومان، max per_person=۱۲۰هزار رد،۸۰هزار قبول اگر برآورد معتبر است. outdoor و daylight unknown، فعالیت نیازمند روز رد. با دو گزینهٔ معتبر، صفحه یک کارت و فقط یک تعویض تازه دارد؛ هر دو پس از عرضه قابل مرورند و نبود سومین گزینه سهمیه کم نمی‌کند.

## رشد آینده

از روز اول نسخهٔ الگوریتم، candidate count، دلایل حذف تجمیعی و actionهای واقعی ثبت شوند. A/B پس از خط پایه و ترافیک کافی، metric اصلی شروع/پایانِ خوداظهاری و رضایت است؛ کلیک بیشتر به‌تنهایی هدف نیست. embeddings، learning-to-rank و bandit فقط با ضرورت، consent مناسب، ارزیابی offline و rollback افزوده شوند. آستانهٔ حجم دیتا از پیش ساختگی تعیین نکن.
