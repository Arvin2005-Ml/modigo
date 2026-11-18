# اجرا، پیکربندی و عملیات

تصمیم جاری اتصال MongoDB واقعی روی endpoint عمومی، حتی در localhost است. [سند24](24-mongodb-storage.md) جای سند21 را گرفته و جزئیات adapter، تراکنش، محدودیت‌ها و آزمون زنده را تعیین می‌کند. یک API process و job runner داخل همان process حفظ می‌شوند؛ Redis، worker مستقل یا Mongo محلی لازم نیستند.

## اجرای فعلی

Python 3.14 و Node.js 22 یا بالاتر؛ وابستگی‌ها در requirements.lock و package-lock.json ثابت‌اند. `.env` ریشه فقط برای سرور و از git خارج است؛ `MONGODB_URI` و `CSRF_HMAC_SECRET` ثابت لازم‌اند. فایل نمونه رمز واقعی ندارد. متغیرهای محیط فرایند بر فایل مقدم‌اند. کلید مدل برای اجرای عادی لازم نیست؛ `LLM_PROVIDER=demo` خروجی محلی صریح است و دادهٔ Mongo واقعی را به ماک تبدیل نمی‌کند.

```sh
.venv/bin/python -m pip install -r apps/api/requirements.lock
PYTHONPATH=apps/api .venv/bin/python -m app.cli check-db
PYTHONPATH=apps/api .venv/bin/python -m app.cli
```

وب در ترمینال دیگر:

```sh
cd apps/web
npm ci
npm run dev
```

اسکریپت `bash scripts/run-local.sh dev` هر دو سرویس را بالا می‌آورد و توقف یکی دیگری را می‌بندد؛ حالت `production` فقط build بهینهٔ فرانت برای اجرای محلی است. در محیط این تغییر، نصب driver و اتصال زنده با DNS ناموفق‌اند؛ فرمان‌ها نباید به‌عنوان اجرای موفق این محیط گزارش شوند.

## متغیرهای اجرایی

```dotenv
APP_ENV=development
APP_ORIGIN=http://127.0.0.1:3000
DATA_BACKEND=mongo
MONGODB_URI=mongodb://root:YOUR_PASSWORD@olympus.liara.cloud:34468/my-app?authSource=admin
CSRF_HMAC_SECRET=REPLACE_WITH_A_STABLE_RANDOM_SECRET_AT_LEAST_32_CHARACTERS
API_WORKERS=1
JOB_RUNNER_MODE=in_process
DEMO_CONTENT=true
LLM_PROVIDER=demo
GAPGPT_BASE_URL=https://api.gapgpt.app/v1
GAPGPT_MODEL=gapgpt-deepseek-v4.1-flash
GAPGPT_API_KEY=
```

برای تنظیم اختیاری GapGPT، key فقط در محیط API قرار گیرد؛ مدل/endpoint خودسرانه عوض نشوند. secretها وارد `NEXT_PUBLIC_*` یا bundle مرورگر نشوند. کلید CSRF پس از restart ثابت بماند. فقط یکی از نام‌های مرورگر `localhost`/`127.0.0.1` را برای نشست جاری استفاده کنید؛ cookieهای آن‌ها جداست.

## راه‌اندازی، shutdown و recovery

startup اتصال و writable replica-set primary را بررسی، ایندکس‌ها را idempotent ایجاد و یک transaction واقعی commit می‌کند. سپس بذرها در batchهای کوتاه بدون overwrite محتوای موجود وارد می‌شوند. standalone یا خطای شبکه/auth جلوی startup را می‌گیرد؛ fallback ندارد. client در shutdown یا شکست initialization بسته می‌شود.

در Docker، launcher ابتدا `python -u -m app.cli serve` را شروع و API مستقیم را تا ready شدن بررسی می‌کند؛ سپس Next اجرا می‌شود. args لیارا همان launcher است. تا قبل از آمادگی API، probe از مسیر Next انجام نمی‌شود. startup API مراحل Mongo، import و runner را بدون credential log می‌کند؛ شکست یا timeout جلوی شروع Web را می‌گیرد. جزئیات اصلاح race در سند25 است.

حساب، نقش، نشست، سوابق و صف در Mongo باقی می‌مانند. queued پس از restart قابل پردازش است؛ running از فرایند متوقف با `WORKER_INTERRUPTED` failed می‌شود تا مدل ناخواسته دوباره صدا نخورد. اپراتور پس از بررسی می‌تواند job تازه enqueue کند. چند process/instance هنوز تحویل نشده‌اند.

تغییر role فقط از CLI است: در کنسول API توسعه `role EMAIL admin` و در shell خصوصی کانتینر `python -m app.cli role EMAIL admin`. فرمان مستقل role از Mongo مشترک استفاده و نشست‌های قبلی را revoke می‌کند؛ API/worker دوم نمی‌سازد. بازیابی رمز به mailbox توسعهٔ همان فرایند می‌رود و `mailbox EMAIL` آن را نشان می‌دهد؛ این صندوق همچنان موقت است و ایمیل خارجی ارسال نمی‌شود. launcher کانتینر stdin console ندارد. ادعای مالکیت ایمیل یا SMTP واقعی وجود ندارد.

## سلامت

- `/api/v1/health/live`: فقط زنده‌بودن process.
- `/api/v1/health/ready`: ping واقعی Mongo؛ قطع DB→503 و بدون URI/credential.
- `python -m app.cli check-db` با PYTHONPATH مناسب: اتصال، ایندکس و commit واقعی را بررسی می‌کند؛ بدون driver یا DB exit غیرصفر دارد.
- `python -m app.cli diagnose-db` با PYTHONPATH مناسب: ping، primary و read محدود را بدون نوشتن داده بررسی و خطای امنِ دارای دسته/مرحله/کد گزارش می‌کند؛ runner یا API دیگری نمی‌سازد و موفقیت آن تأیید index/write/transaction نیست.

محتوای منتشرشده به آنلاین‌بودن provider وابسته نیست. exception، cookie، رمز، token، متن سؤال‌ها و URI در پاسخ/log قرار نگیرند. قابلیت JSON logging و metrics کامل هنوز کار باز است.

## کارهای عملیاتی باقی‌مانده برای عرضه

Mongo واقعی جایگزین backup و حریم خصوصی نمی‌شود. پیش از عرضه باید backup رمزگذاری‌شده با retention۳۰روز، restore drill واقعی، کنترل دسترسی سرویس و redaction/حذف حساب اجرا و آزمون شوند؛ این برش آن‌ها را انجام نداده است. TTLهای امنیتی cleanup هستند و جای بررسی اعتبار در API را نمی‌گیرند. purge پیشنهادی۹۰روز با purge_at جدا از اعتبار۲۴ساعته انجام می‌شود؛ redaction context_snapshot تجربه هنوز کار باز است.

چرخهٔ مورد انتظار انتشار: build و آزمون ثابت، backup قابل restore، migration/index additive، استقرار backend سازگار، وب، smoke ورود/پیشنهاد/پایان/انتشار، و rollout محدود. تغییر schema باید با قرارداد05/06 و نسخهٔ migration هماهنگ شود؛ rollback دادهٔ زنده با حذف ledger/revision انجام نشود. restore باید حذف‌های تأییدشده و ابطال نشست بازیابی‌شده را اعمال کند. فرمان backup/restore آزمایش‌شده هنوز در این مخزن تحویل نشده است.

با درخواست بعدی مالک، `APP_ENV=production` با HTTPS و کوکی امن در [سند25](25-liara-docker.md) فعال و Dockerfile، liara.json، health check و ZIP آمادهٔ آپلود اضافه شدند. فقط یک نمونه اجرا شود و استقرار بدون اختلال در لیارا خاموش باشد تا نسخه‌ها هم‌زمان worker اجرا نکنند. Mongo عمومی حفظ می‌شود. SMTP، export/purge حساب، CI، E2E و پایش تکمیل نشده‌اند؛ بسته‌بندی آن‌ها را کامل نمی‌کند. گزارش آزمون‌های هر برش در README و سند24/25 است.
