# استقرار Docker در لیارا

درخواست مالک در ۹ نوامبر ۲۰۲۶ استقرار نسخهٔ فعلی روی پلتفرم Docker لیارا را مجاز کرد. این سند مرجع جاری بسته‌بندی و اجرای production است؛ محدودیت development در سند15/24 و ADR19 مربوط به برش قبل بود. MongoDB همچنان فقط روی endpoint عمومی تعیین‌شدهٔ مالک است، حتی در localhost. هیچ Mongo محلی، آدرس خصوصی یا fallback حافظه‌ای در ایمیج وجود ندارد.

## بستهٔ آمادهٔ آپلود

از ریشهٔ پروژه اجرا کنید:

```sh
python3 scripts/package-deploy.py
```

خروجی `dist/funilo-liara.zip` است؛ فایل‌های Docker در ریشهٔ ZIP قرار دارند. این بسته با فهرست مجاز از سورس، lockfileها و داده‌های لازم ساخته می‌شود؛ `.env`، credentialها، node_modules، .venv، .next، cache، تست‌ها و بستهٔ مستندات داخل آن نیستند. رمز واقعی Mongo فقط در `.env` محلی موجود است و باید در تنظیمات محیطی برنامهٔ لیارا وارد شود. فایل ZIP سورس خامِ کل پوشه را آپلود نکنید. `.dockerignore` و `.liaraignore` نیز فهرست مجاز مستقل دارند.

## تنظیم برنامه در کنسول لیارا

۱. یک برنامه از نوع **Docker** بسازید و دامنهٔ HTTPS نهایی آن را مشخص کنید. پورت برنامه **3000** است؛ دستور شروع `python /app/scripts/container.py` است که هم در CMD و هم در args فایل liara.json ثبت شده است. اجرای مستقیم Next به‌تنهایی API را راه نمی‌اندازد.

۲. در تنظیمات برنامه، **استقرار بدون اختلال را خاموش** و تعداد نمونه را **۱** نگه دارید. runner فعلی تک‌پردازشی است؛ حتی دو نسخهٔ قدیم/جدید نباید هم‌زمان روی این DB کار کنند. اگر هم‌اکنون اجرای محلی روی همان DB فعال است، پیش از اجرای نسخهٔ ابری آن را متوقف کنید. برای انتشارهای بعدی توقف کوتاه پذیرفته می‌شود؛ worker چندنمونه‌ای/lease تحویل نشده است.

۳. این سه متغیر را در **متغیرهای محیطی زمان اجرا** وارد کنید:

| متغیر | مقدار |
| --- | --- |
| `APP_ORIGIN` | `https://shadophena.liara.run`؛ دامنهٔ فعلی مورد تأیید مالک |
| `CSRF_TRUSTED_ORIGINS` | فهرست جداشده با ویرگول از originهای HTTPS اضافی؛ پیش‌فرض `https://moodigo.ir,https://www.moodigo.ir` |
| `MONGODB_URI` | URI محرمانهٔ فعلی مالک؛ هاست عمومی `olympus.liara.cloud`، پورت `34468`، دیتابیس `my-app` و `authSource=admin` |
| `CSRF_HMAC_SECRET` | کلید تصادفی ثابت حداقل ۳۲نویسه‌ای؛ با restart/deploy عوض نشود |

برای ساخت کلید فقط یک بار اجرا کنید و خروجی را در محیط سرور نگه دارید:

```sh
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

ایمیج این پیش‌فرض‌ها را دارد:

```dotenv
APP_ENV=production
APP_ORIGIN=https://shadophena.liara.run
CSRF_TRUSTED_ORIGINS=https://moodigo.ir,https://www.moodigo.ir
PORT=3000
DATA_BACKEND=mongo
API_WORKERS=1
WEB_CONCURRENCY=1
JOB_RUNNER_MODE=in_process
LLM_PROVIDER=demo
DEMO_CONTENT=true
```

`APP_ORIGIN` در production الزاماً HTTPS است و نشست با `__Host-funilo_session`، Secure، HttpOnly، SameSite=Lax و Path=/ صادر می‌شود. TLS در ورودی لیارا خاتمه می‌یابد؛ ارتباط داخلی Next و API روی loopback است. کلید CSRF، URI و کلید مدل در build، liara.json، Dockerfile یا `NEXT_PUBLIC_*` قرار نگیرند؛ محیط process فرانت نیز آن‌ها را به ارث نمی‌برد.

`CSRF_TRUSTED_ORIGINS` فقط allowlist دقیق `Origin` مرورگر را گسترش می‌دهد؛ wildcard، زیردامنهٔ خودکار و اعتماد به `Host`/`X-Forwarded-*` پذیرفته نمی‌شود. هر مقدار باید origin کامل و canonical باشد (بدون مسیر، query، fragment، credential یا اسلش انتهایی) و در production فقط HTTPS عمومی مجاز است. دامنهٔ اصلی `APP_ORIGIN` همچنان مرجع ساخت لینک ایمیل و بررسی کوکی امن است؛ اگر دامنهٔ اصلی محصول به `https://moodigo.ir` منتقل شد، `APP_ORIGIN` را هم همان مقدار کنید و moodigo.ir را از فهرست اضافی حذف کنید. نشست برای هر hostname جداست؛ ورود از `moodigo.ir` و `www.moodigo.ir` دو کوکی مستقل می‌سازد.

کلید مدل لازم نیست. برای استفادهٔ اختیاری از provider واقعی، `LLM_PROVIDER=gapgpt` و `GAPGPT_API_KEY` را در محیط سرور تنظیم کنید؛ endpoint و مدل پیش‌فرض تنظیمات حفظ می‌شوند. demo صریحاً نمایشی است. `DEMO_CONTENT=true` کاتالوگ تألیفی موجود را idempotent وارد می‌کند و انتشار عمومی بانک ۴۵۰تایی محسوب نمی‌شود. `false` فقط import بعدی demo را متوقف می‌کند؛ محتوای قبلاً موجود را حذف یا غیرفعال نمی‌کند.

۴. ZIP ساخته‌شده را از «استقرار جدید» و Drag & Drop آپلود کنید. لیارا Dockerfile ریشه را می‌سازد. `liara.json` پورت، Dockerfile و health check را مشخص می‌کند؛ شناسهٔ `shadophena` مطابق انتخاب واقعی مالک ثبت شده است. برای CLI، بعد از ورود به حساب:

```sh
liara deploy --app shadophena --platform docker --port 3000
```

استقرار واقعی از محیط فعلی انجام نشده است؛ این فرمان برای حساب مالک است. سورس و تنظیمات آماده‌اند و نیازی به تغییر آدرس Mongo یا build با رمز ندارند.

## ساختار کانتینر و سلامت

Dockerfile چندمرحله‌ای با `node:22.23.4-bookworm-slim` و `python:3.14.10-slim-bookworm` pin شده است. npm ci و requirements.lock نصب تکرارپذیر را تعیین می‌کنند. Next با `output: standalone` ساخته می‌شود؛ public شامل فونت، آیکون و service worker و نیز `.next/static` صریحاً به runtime کپی می‌شوند. فرآیندها با کاربر غیر root اجرا می‌شوند.

یک launcher پایتون ابتدا فقط یک Uvicorn worker را با `python -u -m app.cli serve` روی `127.0.0.1:8000` شروع می‌کند. تا پاسخ200 و status=ready از API مستقیم دریافت نشود، Next شروع نمی‌شود؛ این پاسخ پس از اتصال، ایندکس/تراکنش Mongo، import داده و شروع runner ممکن است. سپس Next روی `0.0.0.0:3000` شروع و مسیر سلامت هم‌مبدأ نیز بررسی می‌شود. API و job runner در همان process هستند. `/api/v1/*` از Next به API داخلی proxy می‌شود؛ فقط3000 منتشر می‌شود. در شکست یا timeout API، فرانت اجرا نمی‌شود؛ خروج غیرمنتظرهٔ هر سرویس دیگری را متوقف و exit غیرصفر می‌دهد. SIGTERM/SIGINT به توقف هر دو process group، فرصت shutdown و جمع‌کردن فرزندان منتهی می‌شود. build هیچ اتصال Mongo انجام نمی‌دهد.

دستور سلامت زیر ابتدا آمادگی API مستقیم را بررسی می‌کند و پس از آن از پورت وب عبور می‌کند تا JSON readiness و ping واقعی Mongo نیز بررسی شوند؛ در نبود API، درخواست proxy به Next ارسال نمی‌شود:

```sh
python /app/scripts/container.py --healthcheck
```

Docker HEALTHCHECK و healthCheck لیارا هر دو همین دستور را اجرا می‌کنند. مقدارهای عددی liara.json عبارت‌اند از `startPeriod=180`، `interval=30`، `timeout=5` و `retries=3`. این مقیاس با نمونهٔ عددی مستندات لیارا هماهنگ است؛ مقدار پیشین `startPeriod=180000` در درخواست واقعی مالک با خطای400 و سقف3000 رد شد. مقادیر را دوباره در1000 ضرب نکنید. متن مستندات رسمی و prompt نسخهٔ CLI واحد را ms می‌نامند، ولی مثال عددی و محدودیت واقعی برای تبدیل پیشین کافی نبودند؛ واحد مؤثر سرویس در این محیط اندازه‌گیری نشده است. زمان‌بندی صریح داخل Dockerfile مستقل است: فاصله۳۰ثانیه، مهلت۵ثانیه و دورهٔ شروع۱۸۰ثانیه؛ launcher نیز برای آماده‌شدن اولیه۱۸۰ثانیه فرصت می‌دهد. `/api/v1/health/live` فقط زنده‌بودن API است؛ آمادگی استقرار با `/api/v1/health/ready` تعیین می‌شود. timeout شبکه و DB به آماده‌نبودن منتهی می‌شود؛ credential در پاسخ سلامت وجود ندارد.

Mongo باید writable replica-set primary با تراکنش چندسندی باشد؛ standalone جلوی startup را می‌گیرد. داشتن URI یا ساخت موفق ایمیج این شرط را اثبات نمی‌کند. بررسی DB از خط فرمان کنسول لیارا:

```sh
python -m app.cli check-db
```

بعد از استقرار، دامنه و health/ready و جریان ورود ← سؤال ← پیشنهاد ← شروع ← پایان را smoke کنید. برای ادمین ابتدا حساب را در UI بسازید، سپس فقط از کنسول خصوصی لیارا اجرا کنید:

```sh
python -m app.cli role your-email@example.com admin
```

این فرمان از DB مشترک استفاده، تغییر را audit و نشست‌های قبلی حساب را revoke می‌کند؛ سرور یا worker دوم بالا نمی‌آورد. پس از آن دوباره وارد شوید. endpoint تغییر نقش وجود ندارد.

## اجرای Docker روی سیستم دارای daemon

از ریشهٔ مخزن:

```sh
docker build -t funilo:liara .
docker run --rm --name funilo --env-file .env \
  -e APP_ENV=development -e APP_ORIGIN=http://127.0.0.1:3000 \
  -p 127.0.0.1:3000:3000 funilo:liara
```

این نمونه برای مرورگر localhost و Mongo واقعی عمومی است. با HTTPS واقعی، APP_ENV=production و APP_ORIGIN را متناسب با دامنه تغییر دهید. `.env` با `--env-file` فقط هنگام اجرا وارد محیط می‌شود و به ایمیج کپی نمی‌شود. برای این معماری volume محلیِ داده لازم نیست؛ دادهٔ محصول در Mongo است. ایمیج و دادهٔ زنده را هنگام rollback از هم مستقل نگه دارید؛ دیتابیس یا ledger را پاک نکنید.

## محدودیت‌های واقعی

دسترسی به Docker daemon در محیط پیاده‌سازی permission denied است؛ build و run کامل ایمیج اینجا تأیید نشده‌اند. DNS shell برای registry و Mongo قابل استفاده نبوده است؛ نصب PyMongo و اتصال زنده، transaction و نسخهٔ سرویس مالک هنوز تأیید نشده‌اند. نتایج تست‌های آفلاین جای آن‌ها نیستند.

SMTP واقعی و بازیابی ایمیلی در کانتینر تحویل نشده‌اند؛ mailbox فقط در کنسول توسعهٔ همان process موقت است و launcher کانتینر stdin console ندارد. از اجرای `python -m app.cli` بدون آرگومان در کانتینر استفاده نکنید، چون سرور دوم می‌سازد. export/حذف حساب، backup/restore drill، CI و E2E مرورگر نیز باقی‌اند. rate limit مبتنی بر IP در proxy فعلی peer مشترک loopback را می‌بیند؛ برای کاربران زیاد، forwarding معتبر و آزمون مرز اعتماد لازم است. این بسته راه استقرار نسخهٔ فعلی را فراهم می‌کند و تأیید محتوایی یا تکمیل همهٔ backlog نیست.

## نتیجهٔ آزمون این برش — ۹ نوامبر ۲۰۲۶

۹۷ تست آفلاین پایتون موفق و هفت تست Mongo واقعی skip شدند (Ran104، skipped=7). ۱۸ تست فرانت، typecheck و build standalone موفق بودند. تست‌های تازه، HTTPS/CSRF، کوکی امن، مرز upload، توقف فرایندها در خروج/timeout و CLI نقش با audit/revoke را بررسی کردند. ZIP۷۴فایلی با خروجی آرشیوساز محلی Liara CLI دقیقاً یکسان بود؛ هیچ آپلودی انجام نشد. extraction و bootstrap بسته با double تزریق‌شدهٔ تست، مسیر همهٔ محتواها را تأیید کرد؛ این آزمون DB واقعی نیست. اسکن ZIP و خروجی فرانت credentialهای تنظیم‌شده را نیافت. syntax پایتون و shell نیز بررسی شد.

build/run کامل ایمیج، smoke شبکه‌ای standalone، استقرار لیارا، Mongo زنده، CI و E2E انجام نشده‌اند؛ Docker daemon و bind پورت در این محیط مجاز نیستند و DNS شبکه محدود است.

## اصلاح خطای400 استقرار مالک — ۹ نوامبر ۲۰۲۶

در اجرای واقعی مالک، سورس با موفقیت آپلود شد ولی ایجاد release با `healthCheck.startPeriod must be less than or equal to 3000` متوقف شد. تنظیمات عددی سلامت اصلاح و شناسهٔ واقعی برنامه `shadophena` ثبت شد؛ ZIP سورس و ZIP مستندات دوباره ساخته شدند. پیام‌های Git در debug برای جمع‌آوری metadata بودند و قبل از upload موفق ثبت شدند؛ برای رفع این خطا git init یا commit لازم نیست. پذیرش release با مقادیر اصلاح‌شده و build/run روی لیارا هنوز در این محیط آزموده نشده‌اند.

## اصلاح EUSAGE در npm ci — ۹ نوامبر ۲۰۲۶

build واقعی مالک پس از عبور از تنظیمات release در مرحلهٔ npm ci متوقف شد. ۲۳ رکورد Sharp در lockfile فقط optional:true و بدون version بودند؛ dependencyهای sharp-wasm32 و emnapi/runtime نیز غایب بودند. lockfile در پوشهٔ خالی، بدون node_modules، با npm و metadata معتبر cache بازسازی شد؛ resolved/integrity سایر رکوردهای ناقص نیز از metadata و tarballهای cache تکمیل شدند. همهٔ۱۳۷بستهٔ خارجی اکنون version،resolved وintegrity دارند؛ نسخهٔ هیچ dependency قبلاً قفل‌شده‌ای و package.json تغییر نکرده است. npm ci در Docker حفظ شده و upgrade npm برای دورزدن این خطا انجام نشد.

نصب تمیز `npm ci --offline --no-audit --no-fund` با cache جدا موفق و Sharp0.35.5 بارگذاری شد. ۱۸تست فرانت، typecheck و build standalone روی نصب تازه موفق شدند. محدودیت: SWC16.4.5 در cache tarball نداشت و npm آن را به‌عنوان optional کنار گذاشت؛ فقط برای آزمون build، همان نسخه از node_modules محلی کپی شد. این کار داخل سورس یا Dockerfile نیست؛ Docker از آدرس و integrity قفل‌شده نصب می‌کند. دانلود آنلاین و build کامل ایمیج همچنان در این محیط تأیید نشده‌اند؛ npm محلی10.9.8 و npm ایمیج گزارش‌شدهٔ مالک10.9.9 است.

برای بررسی نصب تمیز بدون دست‌زدن به node_modules فعلی، از ریشهٔ مخزن:

```sh
task_install_dir="$(mktemp -d)"
cp apps/web/package.json apps/web/package-lock.json "$task_install_dir/"
cd "$task_install_dir"
npm ci --no-audit --no-fund
```

برای بازسازی‌های بعدی lockfile، در یک پوشهٔ بدون node_modules از `npm install --package-lock-only --ignore-scripts --include=optional` استفاده و قبل از جایگزینی، نسخه‌ها و نصب تمیز را بررسی کنید. Sharp در مستندات رسمی دربارهٔ مشکل lockfile مشترک بین پلتفرم‌ها در npm هشدار داده است. موفقیت build با node_modules موجود به‌تنهایی نصب تمیز را اثبات نمی‌کند. ZIP استقرار و ZIP مستندات با اصلاح فعلی دوباره ساخته شدند.

## اصلاح ECONNREFUSED در شروع v6 — ۹ نوامبر ۲۰۲۶

لاگ مالک نشان داد Next در13:21:21 شروع و در13:21:25 اتصال health/ready به پورت8000 رد شده است. این بخش لاگ، علت نبود API را نشان نمی‌دهد؛ startup دیرهنگام، شکست API یا دورزدن launcher باید از لاگ API تفکیک شوند. نسخهٔ قبلی launcher هر دو سرویس را هم‌زمان شروع و بلافاصله از مسیر Next سلامت را probe می‌کرد؛ Uvicorn تا پایان lifespan و init Mongo پورت را باز نمی‌کند. این race قطعی اصلاح شد: اول API مستقیم آماده شود، سپس Next؛ تا قبل از آمادگی API، حتی health check نیز Next را probe نمی‌کند. args صریح در liara.json اجرای launcher را مشخص می‌کند و API با خروجی unbuffered و پیام‌های مرحله‌ای startup اجرا می‌شود. Mongo عمومی و شرط transaction تغییر نکردند و آمادگی جعلی گزارش نمی‌شود.

توالی مورد انتظار لاگ در نسخهٔ اصلاح‌شده:

```text
Funilo launcher: validating server configuration
Starting API
Waiting for API readiness
API: importing the ASGI application
API: starting one Uvicorn worker on 127.0.0.1:8000
API startup: checking MongoDB connection, replica-set primary, indexes and transactions
...
API startup: application initialization complete
API ready
Starting Web
...
Funilo ready: web, API and MongoDB
```

پیام‌های startup اتصال/تراکنش Mongo، ورود بذر و کاتالوگ، بازیابی job و شروع runner را مشخص می‌کنند و credential ندارند. اگر «API startup: checking MongoDB...» آخرین مرحله باشد، پیام خطای بعدی را بررسی کنید؛ writable replica-set primary و دسترسی عمومی لازم‌اند. اگر اصلاً «Funilo launcher» وجود ندارد، release و دستور شروع کنسول را با args فوق تطبیق دهید. برای لاگ کامل:

```sh
liara logs --app shadophena --last-lines --timestamps
```

نتیجهٔ تست:۱۰۱تست آفلاین پایتون موفق،۷تست Mongo زنده skip (Ran108)؛۱۰تست deployment شامل startup کند، ترتیب API→Web، جلوگیری از اجرای Web هنگام شکست/timeout، توقف هنگام انتظار و health check مرحله‌ای موفق بودند. syntax پایتون و shell بررسی شد و ZIPها بازسازی شدند. تست lifecycle از processهای واقعی و marker تست استفاده می‌کند؛ HTTP socket و DB واقعی را شبیه‌سازی موفقیت‌آمیز اعلام نمی‌کند. دریافت لاگ v6 از این محیط با EAI_AGAIN برای api.liara.ir ناموفق بود؛ علت اصلی احتمالیِ شکست Mongo/API در سرور از لاگ ارسالی قابل اثبات نیست. build/run ایمیج و smoke زندهٔ نسخهٔ جدید هنوز اینجا اجرا نشده‌اند.

## شکست ping در v7 — ۹ نوامبر ۲۰۲۶

لاگ v7 نشان می‌دهد launcher و ترتیب شروع API درست اجرا شده‌اند، اما نخستین ping پیش از hello و ساخت ایندکس ناموفق است. از پیام قدیمی «MongoDB is unavailable» نمی‌توان علت auth، شبکه یا TLS را تعیین کرد؛ مدت دوثانیه‌ای شکست نیز اثبات خطای رمز نیست. تنظیم محلی با endpoint عمومی، دیتابیس و authSource داده‌شده تطبیق دارد؛ مقدار محیط واقعی برنامهٔ لیارا از این محیط قابل دریافت نیست، زیرا DNS برای api.liara.ir و olympus.liara.cloud با EAI_AGAIN ناموفق است.

گزارش خطای adapter اصلاح شد تا دستهٔ ثابت، مرحله و کد عددی سرور را بدون متن خام driver، URI یا رمز نشان دهد. اتصال، hello، ایندکس و تراکنش دیگر همگی به پیام مبهم تبدیل نمی‌شوند. تنظیمات اتصال در یک factory مشترک برای runtime و تشخیص قرار دارند؛ endpoint عمومی، directConnection، timeoutها و شرط transaction تغییر نکرده‌اند.

پس از استقرار سورس تازه، از shell همان برنامه تشخیص بدون نوشتن را اجرا کنید:

```sh
liara shell --app shadophena --command "python -m app.cli diagnose-db"
```

این فرمان API یا runner دوم نمی‌سازد و فقط ping، hello و read محدود سند محافظ را اجرا می‌کند؛ ایندکس/داده/نقش تغییر نمی‌کند. موفقیت آن به‌معنای موفقیت commit یا مجوز ایجاد ایندکس نیست. `check-db` همچنان آزمون کامل‌تری است و ممکن است ایندکس و سند محافظ ایجاد کند. اگر release پیش از آماده‌شدن restart می‌شود و shell در دسترس نیست، همان دستهٔ خطا در log startup تازه دیده می‌شود.

| دستهٔ خروجی | اقدام متناسب با نتیجهٔ واقعی |
| --- | --- |
| `AUTHENTICATION_FAILED`, کد18 | مقدار **MONGODB_URI زمان اجرا در برنامهٔ shadophena** را با URI معتبر دیتابیس و authSource=admin تطبیق دهید؛ .env محلی داخل ایمیج نیست. رمز/URI را در لاگ یا پیام عمومی نفرستید. |
| `PERMISSION_DENIED`, کد13 | مجوز همان حساب روی دیتابیس برنامه و عملیات گزارش‌شده را اصلاح کنید. |
| `DNS_FAILED` | resolve شدن هاست عمومی از داخل برنامه و وضعیت شبکه/سرویس را بررسی کنید. |
| `CONNECTION_REFUSED` یا `NETWORK_UNAVAILABLE` | فعال و در دسترس بودن سرویس و host/port عمومی را بررسی کنید؛ این خروجی به‌تنهایی خطای رمز نیست. |
| `TLS_FAILED` | تنظیم موردنیاز TLS سرویس و CA معتبر را تطبیق دهید؛ اعتبارسنجی گواهی خاموش نشود. |
| `CONFIGURATION_INVALID` | گزینه‌ها و host/port/database URI و سازگاری driver/server بررسی شوند. |
| `TRANSACTION_UNSUPPORTED` | writable replica-set primary واقعی لازم است؛ standalone را با آمادگی ساختگی یا نوشتن غیراتمیک دور نزنید. |

در این برش هنوز اتصال زنده یا رفع تنظیمات سرور تأیید نشده است. تشخیص آفلاین دسته‌بندی، عدم افشای credential، بستن client، توقف probe پس از خطا و خواندنی‌بودن فرمان را با client تزریق‌شده بررسی می‌کند؛ این تست‌ها رفتار DB زنده را اثبات نمی‌کنند. راهنمای خطا بر مبنای مستندات رسمی PyMongo است: `https://pymongo.readthedocs.io/en/stable/api/pymongo/errors.html`.

نتیجهٔ آزمون این اصلاح:۱۱۰تست آفلاین موفق و۷تست Mongo زنده skip (Ran117)، شامل۹تست تازهٔ diagnostics. syntax پایتون موفق و ZIP سورس و مستندات بازسازی شدند. diagnose-db محلی بدون driver با exit1 متوقف شد؛ PyMongo قفل‌شده، اتصال زنده، build/run ایمیج و استقرار این اصلاح در این محیط اجرا نشده‌اند. تست‌های تزریقی تأیید اتصال واقعی نیستند.

## اصلاح تنظیمات احراز هویت پس از لاگ v12 — ۹ نوامبر ۲۰۲۶

لاگ ارائه‌شدهٔ مالک در `2026-11-09T23:01:23` خطای `AUTHENTICATION_FAILED (stage=ping, code=18)` دارد. در این اجرای لیارا، سرور درخواست احراز هویت را رد کرده است؛ این خطا با DNS ناموفق محیط توسعه فرق دارد. بدون خواندن تنظیمات زمان اجرای همان برنامه، اشتباه در رمز، کاربر یا authSource مشخص نمی‌شود. آدرس مقصد نیز صرفاً از این لاگ قابل اثبات نیست؛ Mongo باید همچنان از endpoint عمومی مالک استفاده کند.

فایل محرمانهٔ `.env` محلی شامل اطلاعات ورود endpoint عمومی است، اما عمداً وارد ZIP یا ایمیج نمی‌شود. تغییر این فایل یا آپلود دوبارهٔ سورس، متغیر قدیمی `MONGODB_URI` در تنظیمات لیارا را اصلاح نمی‌کند. ابزار اپراتوری زیر برای انتقال همان مقدار فایل محلی به **محیط زمان اجرای برنامهٔ `shadophena`** اضافه شده است:

```sh
python3 scripts/sync-liara-mongo.py
```

این فرمان به نشست فعلی `liara login` یا توکن `LIARA_API_TOKEN` در محیط اپراتور نیاز دارد. URI را صریحاً از `.env` می‌خواند؛ مقدار احتمالی قدیمی در shell بر فایل مقدم نمی‌شود. فقط `olympus.liara.cloud:34468/my-app` با کاربر `root`، رمز غیرخالی و `authSource=admin` پذیرفته می‌شود. اطلاعات ورود در خروجی یا آرگومان shell قرار نمی‌گیرد. ابزار ابتدا متغیرهای فعلی را می‌خواند، فقط کلید Mongo را جایگزین می‌کند و سپس مقدار ذخیره‌شده را مجدداً می‌خواند؛ `APP_ORIGIN`، کلید CSRF و سایر متغیرها حفظ می‌شوند. مقدار یکسان درخواست restart ندارد؛ تغییر مقدار ممکن است برنامه را طبق رفتار لیارا restart کند. برنامه باید همچنان یک نمونه و بدون overlap باشد.

برای مقایسه بدون تغییر از `--check` استفاده کنید؛ فایل جایگزین با `--env-file PATH` و تیم با `--team-id ID` انتخاب می‌شوند. خواندن/نوشتن محیط از همان مسیرهای HTTPS مورد استفادهٔ CLI رسمی نصب‌شدهٔ `@liara/cli 9.4.7` انجام می‌شود؛ redirect دنبال نمی‌شود و متن خام پاسخ خطا نمایش داده نمی‌شود. این ابزار مستقل از کانتینر است و برای اصلاح متغیر runtime به build یا upload تازه نیازی ندارد.

**نتیجهٔ اجرای واقعی ابزار در این محیط:** فایل محلی معتبر بود و نشست CLI توکن فعال داشت، اما نخستین درخواست خواندن محیط لیارا با خطای DNS متوقف شد (خروج۱). هیچ درخواست تغییر محیط ارسال نشد؛ اصلاح تنظیمات لیارا و رفع auth سرور هنوز تأیید نشده‌اند. خروج۰ CLI رسمی در شکست DNS نیز مشاهده شد؛ ابزار جدید موفقیت را از exit status آن استنتاج نمی‌کند.

۹ تست ابزار با پاسخ‌های تزریق‌شده، حفظ سایر secretها، حذف URIهای تکراری، تقدم صریح فایل، جلوگیری از آدرس خصوصی/placeholder، خطای DNS/HTTP، منع redirect و شکست readback را بررسی کردند و موفق شدند. ۸ تست تنظیمات و ۹ تست تشخیص اتصال نیز موفق شدند؛ مجموع۲۶تست هدفمند. این آزمون‌ها احراز هویت زنده نیستند.

پس از تغییر، کل مجموعهٔ بک‌اند نیز اجرا شد: `Ran 126 tests in 25.738s` و `OK (skipped=7)`؛ ۱۱۹تست موفق و هفت integration Mongo بدون opt-in در این اجرای کامل skip شدند. بررسی نبودن URI، رمز و کلید CSRF واقعی در فایل‌های تغییرکرده موفق بود. خطاهای هفت integration با opt-in در گزارش بازآزمایی سند24 ثبت شده‌اند؛ skip این اجرای کامل جای آن خطاها را نمی‌گیرد.

پس از اجرای موفق ابزار در محیط دارای شبکه، `python -m app.cli diagnose-db` و سپس `python -m app.cli check-db` در کنسول همان کانتینر، و `/api/v1/health/ready` بررسی شوند. تأیید ذخیره‌شدن URI به‌تنهایی تأیید رمز یا replica-set/transaction نیست. اگر با مقدار به‌روز همچنان code18 باقی باشد، اطلاعات ورود جاری دیتابیس باید از پنل Mongo تطبیق داده شود؛ تغییر fallback، مکانیزم auth یا حذف تراکنش راه‌حل این خطا نیست.

## اصلاح Origin دامنهٔ فعلی به درخواست مالک — ۹ نوامبر ۲۰۲۶

مالک رفع مانع Mongo را گزارش کرد و پیام «آدرس صفحه با تنظیمات سرور هماهنگ نیست؛ از آدرس محلی برنامه استفاده کن» را روی دامنهٔ فعلی مشاهده کرد. این پیام فقط از مقایسهٔ `Origin` درخواست با `settings.allowed_origins` می‌آید. در کد proxy نسخهٔ نصب‌شدهٔ Next، تغییر Host به API داخلی به‌تنهایی Origin مرورگر را عوض نمی‌کند. مقدار زندهٔ `APP_ORIGIN` در این محیط به‌علت DNS لیارا قابل خواندن نبود؛ مقدار اشتباه محیط زمان اجرا یا قالب غیرcanonical آن بدون خواندن محیط از هم تفکیک نشده‌اند.

دامنهٔ قطعی فعلی **`https://shadophena.liara.run`** است. این مقدار هم در Dockerfile و هم به‌عنوان پیش‌فرض loader در حالت production ثبت شد؛ development همچنان origin محلی خودش را دارد. loader فاصلهٔ دو سر مقدار، اسلش ریشه، بزرگی حروف hostname و پورت استاندارد443 را به origin مرورگر یکسان می‌کند. مسیر، query، fragment، credential و پورت نامعتبر رد می‌شوند. allowlist همچنان فقط origin صریح تنظیمات است؛ wildcard و اعتماد به Host یا X-Forwarded-* اضافه نشده‌اند. متن خطا دیگر نسخهٔ آنلاین را به آدرس محلی ارجاع نمی‌دهد. لاگ startup نیز فقط origin عمومی مؤثر و نام محیط را چاپ می‌کند تا تنظیمات استقرار قابل بررسی باشد.

**متغیر runtime لیارا بر پیش‌فرض ایمیج مقدم است.** اگر مقدار قدیمی در پنل وجود دارد، آپلود ZIP به‌تنهایی آن را اصلاح نمی‌کند. برای اصلاح برنامهٔ فعلی، با حساب واردشدهٔ CLI اجرا کنید:

```sh
liara env:set APP_ENV=production APP_ORIGIN=https://shadophena.liara.run --app shadophena --force
```

این تغییر تنظیمات ممکن است برنامه را restart کند؛ URI Mongo، رمز و کلید CSRF تغییر داده نشوند. معادل پنل آن، تعیین همین دو مقدار در متغیرهای محیطی برنامه است. در لاگ جدید باید `API startup: browser origin https://shadophena.liara.run (production)` دیده شود. پس از آماده‌شدن، صفحه را تازه کنید تا CSRF و کوکی مربوط به همین دامنه گرفته شوند.

تلاش برای خواندن و اصلاح مستقیم همین دو متغیر از محیط پیاده‌سازی، پیش از ارسال هر POST، در GET محیط لیارا با خطای DNS متوقف شد؛ مقدار زنده تغییر نکرده و موفقیت روی دامنهٔ واقعی تأیید نشده است. آزمون API با store تست تزریق‌شده روی **همین نام دامنهٔ HTTPS**، signup/login/logout، کوکی Secure/HttpOnly/host-only، canonicalشدن اسلش root و رد Originهای HTTP،localhost،دامنهٔ مشابه مهاجم،پورت دیگر،null و خالی را بررسی کرد؛ جعل headerهای proxy نیز مجوز نمی‌دهد. توکن CSRF نادرست حتی روی دامنهٔ درست رد می‌شود. ۱۱تست config و۱۰تست deployment موفق شدند. این نتایج smoke آنلاین یا اتصال زندهٔ Mongo نیستند.

آزمون نهایی کل بک‌اند: `Ran 129 tests in 25.888s` و `OK (skipped=7)`؛ ۱۲۲تست موفق و هفت تست Mongo زنده بدون opt-in در این اجرای آفلاین skip شدند. ZIP سورس با۷۵فایل دوباره ساخته شد. فرانت تغییری نداشت؛ build کامل Docker و smoke دامنهٔ آنلاین در این نوبت اجرا نشدند.

## منابع رسمی بررسی‌شده

- لیارا: `https://docs.liara.ir/paas/docker/getting-started/`
- استقرار و liara.json: `https://docs.liara.ir/paas/docker/how-tos/deploy-app/`
- متغیرهای محیطی: `https://docs.liara.ir/paas/docker/how-tos/set-envs/`
- سلامت و واحد زمان: `https://docs.liara.ir/paas/details/health-check/`
- توقف overlap: `https://docs.liara.ir/paas/details/zero-downtime-deployment/`
- Next standalone و کپی static/public: `https://nextjs.org/docs/app/api-reference/config/next-config-js/output`
- تگ‌های رسمی پایه: `https://raw.githubusercontent.com/docker-library/official-images/master/library/node` و `https://raw.githubusercontent.com/docker-library/official-images/master/library/python`
- نصب تمیز npm: `https://docs.npmjs.com/cli/v10/commands/npm-ci/`
- Sharp و lockfile چندپلتفرمی: `https://sharp.pixelplumbing.com/install/#cross-platform`
- ترتیب lifespan و بازشدن پورت Uvicorn: `https://github.com/encode/uvicorn/blob/master/uvicorn/server.py`
