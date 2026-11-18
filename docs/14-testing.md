# آزمون و معیار پذیرش

جدول زیر الزام محصول است؛ تکمیل همهٔ آن ادعا نمی‌شود. runtime فقط MongoDB واقعی است. تست آفلاین با double مخصوص تست و تزریق صریح اجرا می‌شود؛ آزمون Mongo واقعی با opt-in و دیتابیس موقتِ جدا طبق [سند24](24-mongodb-storage.md) اجرا شود. خطای اتصال زنده هرگز موفقیت آفلاین محسوب نمی‌شود.

## تست‌های ضروری

| حوزه | سناریو و انتظار |
| --- | --- |
| hard filters | ۳۰دقیقه در برابر جمع۳۵ رد؛ total۳۰ قبول؛ برآورد منقضی و unknown زیر cap رد؛ هزینهٔ گروه ضرب شود |
| constraints | ابزار ناموجود، تماس بدون رضایت، social ناسازگار، blocked tag، daylight/weather ناشناخته و accessibility null رد شوند |
| ranking | هر سؤال نیاز مستقل مؤثر؛ نیاز جاری مقدم بر سابقه، بُعد پرتکرارتر در نیاز یکسان اول؛ یک رأی از اولین شروع هر نوبت؛ seed ثابت تکرارپذیر؛ یک کارت، شش تعویض متمایز و رد هفتم؛ کمبود بدون relax سخت |
| catalog coverage | حداقل شش گزینه در ۶۴۸ ترکیب پایه، بدون وسیله و هوا/روز معلوم؛ شرط سکوت/نشسته/بدون پله نیز جدا؛ ۴۸۰ رتبه‌بندی کوتاه با همهٔ energy/moodها؛ کمبود پس از exhaustion معتبر بماند |
| suggestion history | مرور قبلی/بعدی بدون مصرف سهمیه، حتی پس از سقف؛ reload و replay جای مرور را حفظ کنند؛ شروع کارت برگشتی مجاز و غیرجاری رد؛ مرز، race، مالکیت، CSRF و withdrawal در رسید بررسی شوند |
| context | Persian digits normalize، cap معتبر، either با party_size1 گروهی پیشنهاد ندهد، mood skip معتبر |
| sessions | expired با TTL هنوز حذف‌نشده هم401؛ cookie flags production؛ rotate؛ logout/revoke؛ access user suspended |
| CSRF | login CSRF، Origin نادرست، token غایب/نشست دیگر رد؛ GET بدون mutation |
| authorization | userA همهٔ session/experience/saved userB را نبیند؛ editor publish403؛ draft برای user404 |
| recommendation race | replace با expected_version قدیمی409؛ دوبار start فقط یک تجربهٔ active؛ slot تعویض‌شده قابل start نباشد |
| idempotency | payload یکسان یک اثر؛ کلید یکسان متفاوت409؛ retry پایان پس از۲۴ساعت همان award_result |
| reward race | ۲۰ درخواست complete هم‌زمان یک ledger و یک پاداش؛ cap روزانه/rolling، تکرار۷روز و timezone رعایت |
| publication | publish اتمیک pointer و supersede؛ withdrawn در شروع session قدیمی رد؛ draft job دیررس نسخهٔ ویرایش‌شده را overwrite نکند |
| provider | 429/backoff،timeout،401 توقف صف،JSON ناقص،refusal،schema invalid، سقف مشترک۴call، usage غایب و provider خاموش |
| worker | lease expiry،heartbeat،crash پس از response،دریافت job توسط دو worker،cancel حین call؛ حداکثر یک نتیجهٔ قابل review |
| import | ۴۵۰seed یکتا،۷۵هر بُعد؛ import مجدد بدون duplicate؛ invalid row و preview checksum conflict |
| privacy | opt-out از analytics،properties اضافی،event دیگران،redaction۹۰روزه و purge حساب؛ export بدون hash/token |

آزمون API/دامنهٔ آفلاین، rollback، نسخه، فیلتر، مالکیت و هم‌زمانی را بدون کلید مدل می‌سنجد. `RUN_MONGODB_TESTS=1` آزمون‌های واقعی index/transaction، BSON، restart، CSRF، دسترسی افقی و انتشار را روی دیتابیس‌های UUIDدار همان endpoint عمومی فعال می‌کند؛ `my-app` پاک نمی‌شود. این آزمون‌ها تا نصب driver و دسترسی شبکه تأیید نشده‌اند. clock برای expiry و cap تزریق‌پذیر و provider/email در آزمون fake هستند. آزمون خودکار مدل پولی/ارسال ایمیل ندارد.

## E2Eهای اصلی با Playwright

۱. signup بدون verify طبق تصمیم محلی مالک،login،پاسخ هشت سؤال در شش قدم،یک کارت با fixture پوشش‌دار و شش تعویض،مرور و انتخاب کارت قبلی،جزئیات،شروع،پایان،ردکردن feedback،دیدن۱۰امتیاز و نشان اول.
۲. ثبت feedback و ویرایش/حذف آن؛ ذخیره و حذف؛ برگشت پس از reload و نشست منقضی بدون از دست‌رفتن پاسخ موقت.
۳. حالت صفر،یک و هفت گزینهٔ موجود، ولی یک کارت هم‌زمان؛ تغییر شرایط فقط با عمل کاربر؛ replace بدون گزینه،خطای شبکه و session expired.
۴. editor cook demo،اصلاح،submit؛ admin publish و withdraw؛ user نتیجهٔ جدید و ممنوعیت شروع قدیمی را ببیند.
۵. keyboard-only و RTL در موبایل۳۶۰؛ validation با ارقام فارسی؛ dialog focus trap و بازگشت focus؛ zoom۲۰۰٪.
۶. از «کشف» جزئیات را باز کن، شرایط و تعداد نفرات را تأیید کن، شروع کن، از فهرست ادامه بده و پس از reload پایان و بازخورد را ثبت کن. همان فعالیت از «ذخیره‌ها» نیز قابل شروع باشد. API بدون نشست/CSRF، نسخهٔ قدیمی یا draft، شرایط تأییدنشده و شروع هم‌زمان از پیشنهاد و کاتالوگ را کنترل کند.

## معیارهای کیفی و عملکرد

در fixture بانک۴۵۰ revision و محیط staging ثبت‌شده، endpoint recommendation بدون LLM با p95 هدف کمتر از۸۰۰ms برای۲۰درخواست هم‌زمان؛ اندازه و سخت‌افزار در گزارش بیاید. تغییر محیط نیازمند ادعای همان سرعت نیست. UI اصلی روی شبکهٔ کند قابل استفاده، skeleton محدود، تصاویر/فونت بهینه و بدون layout shift مزاحم. برای production، حجم ترافیک واقعی پایش و ظرفیت‌سنجی مجدد شود.

اسکن axe برای صفحات اصلی بدون خطای critical/serious، اما جای آزمون دستی focus/RTL را نمی‌گیرد. ترکیب‌های رنگ و حرکت کاهش‌یافته بررسی شوند. Typecheck،lint،unit/integration،build web و E2E اصلی در CI اجباری. تست امنیت dependency و secret scan روی تغییرات؛ خطای شناخته‌شدهٔ بحرانی unresolved تحویل عمومی نشود.

## Definition of Done

کد قابل اجرا،خطایابی و حالت‌های UI،کنترل مالکیت،تست‌های مناسب،migration/indexها،OpenAPI و client هماهنگ،۲۴نمونهٔ demo بازبینی‌شده،۴۵۰بذر draft،راهنمای اجرای بدون کلید،env نمونه،گزارش تست واقعی و screenshotهای سه صفحه. هیچ قابلیت غایب با placeholder موفقیت‌آمیز پنهان نشود؛ provider زنده اگر آزمون نشده صریح گزارش شود.

## نتیجهٔ برش تک‌پیشنهاد و مرور — ۹ نوامبر ۲۰۲۶

۷۹ تست Python با ASGI و store واقعی ماک و ۱۸ تست فرانت موفق شدند؛ typecheck و build نیز موفق. شش تست رندر کامپوننت پیشنهاد از React واقعی استفاده می‌کنند؛ آزمون کلیک end-to-end مرورگر، screenshot و CI این برش انجام نشده‌اند. این گزارش تکمیل الزامات آیندهٔ جدول را ادعا نمی‌کند.

## نتیجهٔ آزمون برش MongoDB — ۹ نوامبر ۲۰۲۶

۹۰ تست آفلاین پایتون موفق؛ هفت تست Mongo واقعی بدون opt-in صریح skip شدند (خروجی unittest: Ran 97, OK, skipped=7). ۱۸ تست فرانت، typecheck و build نیز موفق بودند. بررسی syntax پایتون و shell، لینک‌های داخلی و عدم کپی secret در کد/مستندات موفق بود. نصب driver از registry و اتصال endpoint Liara به‌علت DNS محیط تأیید نشد؛ check-db با پیام نصب‌نبودن PyMongo و exit1 متوقف شد. این نتایج تأیید ایندکس، transaction، نسخه یا ماندگاری روی سرور مالک نیستند. CI، E2E و بازبینی بصری این برش اجرا نشده‌اند.
