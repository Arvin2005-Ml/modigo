# هویت، مجوز و حریم خصوصی

**ذخیره‌سازی جاری — ۹ نوامبر ۲۰۲۶:** حساب، hash نشست، token و limiter در MongoDB واقعی‌اند. کلید CSRF ثابت از تنظیمات محرمانهٔ سرور خوانده می‌شود تا restart نشست را خراب نکند. TTL جای کنترل زمان در API را نمی‌گیرد. یک API process و worker داخل همان process؛ mailbox توسعه همچنان موقت و بدون ارسال ایمیل واقعی است. [سند24](24-mongodb-storage.md) جاری است؛ ثبت‌نام بدون verify طبق تصمیم ثبت‌شدهٔ مالک در سند18 است.

## احراز هویت

ایمیل و رمز؛ رمز حداقل۱۲ و حداکثر۱۲۸ نویسه، paste/password manager مجاز، بدون الزام ساختگی نماد و حروف. hash با Argon2id و تنظیمات کتابخانهٔ معتبر، پارامترهای benchmark‌شده و امکان rehash در login. رمز یا token خام هیچ‌وقت log یا ذخیرهٔ قابل برگشت نشود. عادی‌سازی ایمیل با سیاست ثابت trim و lowercase برای حساب‌های این محصول؛ آدرس اصلی برای ارسال جدا نگه داشته شود؛ رفتار در راهنمای حساب روشن باشد.

ثبت‌نام تا verify ایمیل session صادر نمی‌کند. token ایمیل با CSPRNG حداقل۲۵۶bit، hash در DB؛ verify با اعتبار۲۴ساعت، reset با۳۰دقیقه. یک‌بارمصرف و مصرف در transaction. درخواست بازیابی پاسخ عمومی دارد؛ token قدیمی با صدور جدید باطل شود. لینک در ایمیل فقط از APP_ORIGIN تنظیم‌شده ساخته شود، نه Host ورودی.

نشست opaque تصادفی۲۵۶bit؛ hash کامل token برای lookup سمت سرور. cookie production: `__Host-funilo_session; HttpOnly; Secure; SameSite=Lax; Path=/` بدون Domain. dev روی HTTP نام جدا `funilo_session_dev` و Secure=false؛ این استثنا در production fail-fast شود. عمر مطلق۱۴روز و idle۷روز؛ expires_at و last_seen_at در سرور سنجیده شوند. برای editor/admin عمر مطلق۸ساعت و idle۳۰دقیقه. login نشست قبلی را rotate می‌کند. نشست در localStorage، URL یا JWT قابل خواندن فرانت نباشد.

CSRF هم برای login و mutationها: pre-auth cookie تصادفی HttpOnly و توکن وابستهٔ HMAC کوتاه‌عمر از `/auth/csrf`؛ پس از ورود synchronizer token نشست، hash در DB. فرانت توکن را فقط در حافظه نگه دارد، در header بفرستد. Origin allowlist دقیق و Fetch Metadata کمک‌کننده؛ درخواست Origin غایب از client غیرمرورگری فقط با policy صریح و CSRF معتبر، نه bypass عمومی. GET تغییر وضعیت نمی‌دهد.

rate limit اولیه قابل تنظیم: login۵تلاش/۱۵دقیقه برای کلید hash ایمیل و۲۰/IP؛ signup و forgot۳/ساعت به‌ازای ایمیل و۱۰/IP؛ resend۳/ساعت؛ check-in و slate۲۰/دقیقه/user، replace۳۰/دقیقه/user، cook۱۰/دقیقه/editor با یک job فعال/activity؛ ایمیل‌های فرستاده‌شده سقف روزانه داشته باشند. دادهٔ limiter به‌صورت bucket hash با TTL در Mongo و proxy limit مکمل؛ در چند process به شمارندهٔ حافظهٔ محلی تکیه نکن. trusted proxyها محدود تا X-Forwarded-For جعل نشود.

## نقش‌ها و دسترسی

| عمل | user | editor | admin |
| --- | --- | --- | --- |
| داده و تجربهٔ خود | بله | بله | بله |
| خام/پیش‌نویس محتوا، cook و submit | خیر | بله | بله |
| publish،reject،withdraw،reactivate | خیر | خیر | بله |
| preview import | خیر | بله | بله |
| commit import، مدیریت کاربران، audit و metrics | خیر | خیر | بله |
| مشاهدهٔ mood،feedback و تاریخچهٔ فرد دیگر | خیر | خیر | خیر |
| تغییر role | خیر | خیر | فقط CLI امن اپراتور |

ادمین حساب را از CLI با شناسه/ایمیل موجود ارتقا دهد؛ secret پیش‌فرض یا «اولین ثبت‌نام ادمین می‌شود» ممنوع. CLI نقش تغییرکرده را audit و sessionهای قبلی را revoke کند. تعلیق/حذف آخرین admin فعال مسدود، self-suspend در UI مسدود. suspend کاربر فوراً نشست‌ها را revoke می‌کند. همهٔ endpointها status فعلی user را می‌سنجند، نه role ذخیره‌شده در کلاینت.

## حریم خصوصی و نگهداری

حال انتخابی فقط برای موقعیت فعلی است و تشخیص سلامت نیست. پاسخ‌ندادن به آن مجاز است. operational data ضروری برای تجربه از analytics اختیاری جدا شود. toggle «کمک به بهترشدن مودیگو با دادهٔ استفاده» پیش‌فرض خاموش؛ روشن/خاموش‌کردن مستقل از auth و پیشنهاد است. حتی در opt-out، سوابق عملیاتی و امنیتی ضروری با توضیح روشن نگه داشته می‌شوند.

| داده | نگهداری پیش‌فرض |
| --- | --- |
| check-in و recommendation session با context | ۹۰روز؛ اعتبار session پیشنهاد۲۴ساعت |
| context_snapshot تجربه، شامل mood | mood و budget خام پس از۹۰روز redact؛ dimension و content reference برای سابقه باقی |
| feedback و سابقهٔ فعالیت | تا حذف توسط کاربر/حذف حساب؛ برای personalization فقط۹۰روز اخیر |
| analytics اختیاری | raw۹۰روز؛ aggregate بدون شناسه تا۱۲ماه، گروه کمتر از۱۰ نفر نمایش نده |
| security log بدون payload و رمز/token | ۳۰روز |
| audit ادمین پالایش‌شده | ۱۸۰روز؛ actor حذف‌شده pseudonymized |
| backup رمزگذاری‌شده | چرخه۳۰روزه؛ کلید و secret خارج backup application |

حذف حساب نیازمند رمز فعلی و متن تأیید صریح؛ بلافاصله status=deleting و revoke. job پاک‌سازی حداکثر۷روز همهٔ داده‌های user_id و پیوندهای analytics را purge می‌کند؛ مدرک حداقلی عدم‌بازگردانی در restore checklist نگه داشته شود. در UI توضیح داده شود backupها با چرخه۳۰روزه خارج می‌شوند. حذف وسط درخواست complete/import با کنترل status و transaction ایمن باشد. export رمز/توکن/یادداشت داخلی و اطلاعات دیگران ندارد و no-store است.

## امنیت اجرایی

HTML از LLM به UI تزریق نشود؛ متن سادهٔ escape‌شده. CSP محدود، HTTPS، HSTS پس از آماده‌شدن دامنه، عدم cache مشترکِ پاسخ شخصی. ورودی Mongo به filter مستقیم تبدیل نشود؛ اپراتورهایی مانند `$ne` از کاربر قبول نکن. body limit، query allowlist و schema strict. access log URLهای verify/reset را redact کند؛ صفحهٔ token از Referrer-Policy=no-referrer و بدون اسکریپت تحلیلی بیرونی استفاده کند. کلید GapGPT فقط secret server و قابل rotate باشد. الزامات حقوقی عمومی و متن شرایط در زمان عرضه بر اساس حوزهٔ واقعی فعالیت بررسی شوند؛ این سند ادعای انطباق حقوقی ندارد.
