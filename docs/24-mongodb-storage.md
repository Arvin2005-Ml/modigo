# ذخیره‌سازی جاری: MongoDB واقعی روی شبکهٔ عمومی

تصمیم صریح مالک در ۹ نوامبر ۲۰۲۶ جایگزین تصمیم ماک در سند21 و ADR16 است. اجرای محلی و سایر اجراها از همان endpoint عمومی `olympus.liara.cloud:34468` و دیتابیس `my-app` استفاده می‌کنند؛ میزبان خصوصی `shadophen` و Mongo محلی تنظیم نمی‌شوند. نسخهٔ اعلام‌شدهٔ سرور `9.0.2` است؛ نسخه و توپولوژی زنده در این محیط هنوز احراز نشده‌اند.

## تنظیم و اجرا

`DATA_BACKEND=mongo` تنها backend اجرایی است. URI داده‌شده در فایل محرمانهٔ `.env` ریشه با دسترسی محدود ثبت شده و `.gitignore` آن را کنار می‌گذارد؛ رمز در سند، نمونه، وب یا خروجی CLI قرار ندارد. `.env.example` فقط placeholder دارد. API تنظیمات `.env` را بدون اجرای shell و بدون interpolation می‌خواند؛ متغیرهای فرایند بر فایل مقدم‌اند. وب به URI یا رمز نیاز ندارد.

```sh
.venv/bin/python -m pip install -r apps/api/requirements.lock
PYTHONPATH=apps/api .venv/bin/python -m app.cli check-db
PYTHONPATH=apps/api .venv/bin/python -m app.cli
```

کنسول CLI همچنان `role EMAIL admin`، `mailbox EMAIL` و `resume-provider` دارد. اجرای هم‌زمان وب و API با `bash scripts/run-local.sh dev` یا build محلی با `bash scripts/run-local.sh production` است؛ واژهٔ production در این اسکریپت فقط build بهینهٔ فرانت را انتخاب می‌کند و انتشار عمومی محصول نیست. برای uvicorn مستقیم:

```sh
PYTHONPATH=apps/api .venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

`CSRF_HMAC_SECRET` یک مقدار تصادفی حداقل ۳۲نویسه‌ای و ثابت در محیط سرور است؛ با هر restart تولید نشود. مقدار واقعی برای محیط فعلی در `.env` ساخته شده است. تغییر آن نشست‌های فعلی را از نظر CSRF ناسازگار می‌کند و نیازمند ورود تازه است.

## تشخیص اتصال بدون نوشتن

برای تشخیص اتصال بدون ایجاد ایندکس یا نوشتن داده، `PYTHONPATH=apps/api .venv/bin/python -m app.cli diagnose-db` اجرا شود. این فرمان فقط تنظیمات Mongo را می‌خواند، ping، hello و یک read محدود از سند محافظ را انجام می‌دهد؛ CSRF، سرویس‌های برنامه و runner را شروع نمی‌کند. موفقیت آن جای آزمون نوشتن/commit در `check-db` یا startup را نمی‌گیرد. تنظیمات اتصال در هر دو مسیر یکسان و directConnection عمومی است.

پس از گزارش شکست ping در v7، پیام مبهم «MongoDB is unavailable» با دستهٔ ثابت و امن، مرحله و کد عددی سرور جایگزین شد؛ مثلاً `AUTHENTICATION_FAILED (stage=ping, code=18)`. متن خام exception، URI، password، نام replica و سند خطای سرور چاپ نمی‌شوند. DNS، TLS، TCP refused، عدم دسترسی شبکه، auth، مجوز، تنظیمات و transaction تفکیک می‌شوند. این اصلاح قابلیت تشخیص می‌دهد؛ رفع اتصال سرور تا دریافت علت واقعی تأیید نشده است.

## قرارداد adapter

- یک `MongoClient` در lifespan؛ بستن client در shutdown و شکست initialization. هیچ import برنامه اتصال DB را شروع نمی‌کند.
- PyMongo `4.19.0` و وابستگی آن dnspython `2.9.2` در lockfile ثابت‌اند. انتخاب بر پایهٔ مستندات رسمی Python 3.14/MongoDB 9 انجام شده؛ نصب این نسخه‌ها در محیط فعلی به‌علت DNS موفق نشده است.
- `directConnection=True` فقط endpoint تنظیم‌شده را به‌کار می‌برد تا hostname خصوصیِ احتمالی اعضای replica دنبال نشود. endpoint باید primary قابل نوشتن باشد؛ failover خودکار میان اعضای خصوصی در این حالت انجام نمی‌شود.
- هر مجموعهٔ منطقی در collection واقعی مستقل است. `id` دامنه به `_id` رشته‌ای نگاشت می‌شود و `_id` از قرارداد خروجی حذف می‌شود. تاریخ‌ها BSON UTC و خروجی‌های ذخیره‌شده با دقت میلی‌ثانیه‌اند.
- ایندکس‌های یکتای ایمیل، seed، شمارهٔ revision، session هر check-in، یک تجربهٔ active برای هر user، ledger، badge، ذخیره‌ها، receipt و job فعال ساخته می‌شوند. ایندکس TTL نشست، pre-auth، token، receipt، limiter، check-in و purge پیشنهاد وجود دارد. اعتبار زمانی همچنان در منطق برنامه بررسی می‌شود.
- `atomic()` از session و transaction واقعی با snapshot read concern و majority write concern استفاده می‌کند. بلوک‌های تو‌در‌تو به همان transaction می‌پیوندند؛ savepoint مستقل ندارند. provider و ایمیل/await داخل transaction نباشند.
- قفل محلی و سند محافظ مشترک `_funilo_meta/atomic_guard` از رقابت و write skew جلوگیری می‌کنند. این قفل سراسری برای ظرفیت فعلی است؛ ظرفیت بالا و چند instance نیازمند طراحی و آزمون جداست. همچنان یک API process و worker در همان process اجرا شود.
- تلاش مجدد محدود پیش از شروع بدنهٔ atomic و برای نتیجهٔ نامعلوم commit انجام می‌شود. خطای بدنه transaction را rollback و پاسخ 503 می‌دهد؛ کلاینت همان کلید idempotency را برای retry نگه دارد. بدنهٔ arbitrary Python خودکار دوباره اجرا نمی‌شود.
- پاداش، پایان تجربه و receipt، و نیز انتشار و جابه‌جایی pointer در همان transaction ذخیره می‌شوند. خطای اتصال یا تنظیمات fallback به حافظه ندارد.

## شرط تراکنش

MongoDB standalone تراکنش چندسندی ندارد. startup ابتدا `ping` و `hello` را بررسی می‌کند؛ بدون writable replica-set primary خطای روشن می‌دهد. سپس ایجاد ایندکس و commit واقعیِ سند محافظ را می‌سنجد. تنظیم replica set، تغییر سرویس Liara یا دست‌کاری دیتابیس موجود در این برش انجام نشده است؛ وضعیت سرور مالک هنوز نامعلوم است. صرف داشتن URI و پورت، پشتیبانی transaction را اثبات نمی‌کند.

## داده و restart

حساب‌ها، نقش‌ها، hash نشست، ترجیح‌ها، نوبت‌ها، تجربه‌ها، بازخورد، کاتالوگ، صف، امتیاز و audit در Mongo می‌مانند. ورود بانک idempotent و در دسته‌های ۲۵تایی است تا transaction طولانی روی شبکهٔ عمومی ساخته نشود. restart محتوای ویرایش‌شده یا withdrawn را بازنویسی/فعال نمی‌کند. ۴۵۰ بذر draft و کاتالوگ demo همچنان بدون ادعای تأیید انتشار عمومی‌اند؛ `LLM_PROVIDER=demo` ارتباطی با واقعی‌بودن DB ندارد.

jobهای queued پس از restart قابل پردازش‌اند. job در وضعیت running از فرایند متوقف‌شده با `WORKER_INTERRUPTED` به failed تبدیل می‌شود؛ فراخوانی مدل با هزینه/نتیجهٔ نامعلوم خودکار تکرار نمی‌شود. اپراتور می‌تواند پس از بررسی دوباره enqueue کند. صندوق ایمیل توسعه همچنان در حافظهٔ اپراتور است و با restart خالی می‌شود؛ adapter ارسال ایمیل واقعی و ذخیرهٔ پیام خام در DB اضافه نشده‌اند.

`GET /api/v1/health/ready` اتصال واقعی را ping می‌کند و قطع DB پاسخ503 دارد؛ `GET /api/v1/health/live` فقط زنده‌بودن API را نشان می‌دهد. هیچ‌کدام URI یا اطلاعات ورود را نمایش نمی‌دهند.

## آزمون و محدودیت تحویل

تست‌های آفلاین با `MemoryTestStore` فقط از `apps/api/tests/support.py` و تزریق صریح اجرا می‌شوند؛ این کلاس در برنامه یا factory اجرایی وجود ندارد. موفقیت آن‌ها اثبات index/transaction واقعی نیست.

```sh
PYTHONPATH=apps/api .venv/bin/python -m unittest discover -s apps/api/tests -v
RUN_MONGODB_TESTS=1 PYTHONPATH=apps/api .venv/bin/python -m unittest discover -s apps/api/tests -p test_mongo_integration.py -v
```

آزمون دوم از URI سرور، یا `MONGODB_TEST_URI` صریح، استفاده می‌کند و برای هر تست دیتابیس تصادفی `funilo_test_<uuid>` می‌سازد و فقط همان دیتابیس را حذف می‌کند. دیتابیس `my-app` پاک نمی‌شود. این آزمون rollback، ایندکس، CAS، BSON، ماندگاری پس از ساخت client/برنامهٔ تازه، CSRF، دسترسی افقی، انتشار و رقابت پایان را بررسی می‌کند. بدون opt-in صریح، هفت آزمون Mongo skip می‌شوند؛ با opt-in خطای driver/اتصال failure است.

محدودیت تأییدشدهٔ محیط این برش: DNS برای registry و endpoint Liara قابل استفاده نیست، در نتیجه نصب PyMongo، اتصال زنده، ایجاد ایندکس روی سرور و اجرای تست‌های Mongo تأیید نشده‌اند. `check-db` بدون driver با پیام امن و خروج ناموفق متوقف می‌شود. اجرای موفق باید در محیط دارای شبکه با فرمان‌های بالا انجام شود؛ وجود فایل تنظیمات به‌معنای اتصال موفق نیست.

حذف/export حساب، redaction دوره‌ای، backup/restore drill، SMTP، CI و E2E کامل همچنان کارهای باقی‌ماندهٔ تحویل عمومی‌اند. اتصال DB به‌تنهایی آن‌ها را تکمیل نمی‌کند. درخواست بعدی مالک برای Docker لیارا در [25](25-liara-docker.md) ثبت شده و production با HTTPS فعال است؛ محدودیت development برش اتصال دیگر دستور جاری deployment نیست.

## منابع نسخه و قابلیت

- PyMongo releases و compatibility: `https://pypi.org/project/pymongo/` و `https://www.mongodb.com/docs/drivers/compatibility/?driver-language=python&python-driver-framework=pymongo`
- وابستگی driver در tag انتخاب‌شده: `https://raw.githubusercontent.com/mongodb/mongo-python-driver/4.19.0/requirements.txt`
- نسخهٔ dnspython: `https://pypi.org/project/dnspython/`
- transaction و محدودیت standalone: `https://www.mongodb.com/docs/languages/python/pymongo-driver/current/crud/transactions/` و `https://www.mongodb.com/docs/manual/core/transactions-production-consideration/`

## نتیجهٔ آزمون برش MongoDB — ۹ نوامبر ۲۰۲۶

۹۰ تست آفلاین پایتون موفق؛ هفت تست Mongo واقعی بدون opt-in صریح skip شدند (خروجی unittest: Ran 97, OK, skipped=7). ۱۸ تست فرانت، typecheck و build نیز موفق بودند. بررسی syntax پایتون و shell، لینک‌های داخلی و عدم کپی secret در کد/مستندات موفق بود. نصب driver از registry و اتصال endpoint Liara به‌علت DNS محیط تأیید نشد؛ check-db با پیام نصب‌نبودن PyMongo و exit1 متوقف شد. این نتایج تأیید ایندکس، transaction، نسخه یا ماندگاری روی سرور مالک نیستند. CI، E2E و بازبینی بصری این برش اجرا نشده‌اند.

## بازآزمایی endpoint عمومی به درخواست مالک — ۹ نوامبر ۲۰۲۶

تنظیمات محرمانهٔ موجود، میزبان `olympus.liara.cloud`، پورت `34468`، دیتابیس `my-app` و `authSource=admin` را دارند؛ فایل `.env` مجوز `0600` دارد. رمز و URI کامل در گزارش درج نشده‌اند. میزبان خصوصی برای این آزمون استفاده نشد.

| بررسی اجراشده | نتیجهٔ مشاهده‌شده |
| --- | --- |
| اتصال با `socket.create_connection` به endpoint عمومی | شکست در DNS با `socket.gaierror` و errno برابر `-3`؛ اتصال TCP برقرار نشد |
| اتصال به `pypi.org:443` | همان خطای DNS؛ دسترسی registry در این محیط تأیید نشد |
| نصب `pymongo==4.19.0` و `dnspython==2.9.2` با pip، بدون retry و timeout پنج‌ثانیه | خروج۱؛ توزیع‌های قفل‌شده دریافت نشدند و driver نصب نشد |
| `app.cli diagnose-db` | خروج۱ با پیام امن نصب‌نبودن PyMongo؛ فرمان به ping نرسید |
| `app.cli check-db` | خروج۱ با همان پیام؛ ایندکس و commit بررسی نشدند |
| `test_mongo_connection.py` | هر۹ تست آفلاین موفق؛ clientها تزریق‌شده‌اند و اتصال زنده را اثبات نمی‌کنند |
| `test_mongo_integration.py` با `RUN_MONGODB_TESTS=1` | هر۷ تست در setup خطا دادند؛ پنج خطای `StorageUnavailable` مربوط به driver و دو خطای نبود `bson`؛ هیچ تستی skip یا موفق گزارش نشد |

این خطاها وضعیت محیط اجرا را نشان می‌دهند؛ نادرست‌بودن اطلاعات ورود یا خرابی سرور از آن‌ها نتیجه نمی‌شود. احراز هویت، نسخهٔ اعلام‌شدهٔ `9.0.2`، writable replica-set primary، خواندن/نوشتن، ایندکس‌ها، rollback، ماندگاری و readiness زنده همچنان تأیید نشده‌اند. هیچ داده‌ای از این آزمون‌ها به دیتابیس نوشته نشد. کد برنامه، lockfile و تنظیمات اتصال تغییر نکردند؛ تغییر این نوبت فقط ثبت نتیجهٔ آزمون است.

برای تکرار پس از فراهم‌شدن شبکه و نصب وابستگی‌های قفل‌شده، از ریشهٔ پروژه و با `.env` سمت سرور:

```sh
.venv/bin/python -m pip install -r apps/api/requirements.lock
PYTHONPATH=apps/api .venv/bin/python -m app.cli diagnose-db
PYTHONPATH=apps/api .venv/bin/python -m app.cli check-db
RUN_MONGODB_TESTS=1 PYTHONPATH=apps/api .venv/bin/python -m unittest discover -s apps/api/tests -p test_mongo_integration.py -v
```

`check-db` طبق قرارداد بالا ایندکس‌ها و سند محافظ برنامه را بررسی/ایجاد می‌کند. تست‌های integration دادهٔ آزمایشی را فقط در دیتابیس‌های تصادفی خود می‌سازند و همان‌ها را حذف می‌کنند.
