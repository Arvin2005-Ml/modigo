# پنل ادمین

## اطلاعات روی صفحهٔ اول

چهار عدد کاربردی: منتشرشده‌ها، در انتظار بررسی، jobهای شکست‌خورده و پوشش کم‌محتوا. یک CTA «افزودن ایده» و یک جدول کوچک از صف بررسی. نمودارهای تزئینی و نمایش اطلاعات حساس فردی حذف. editor فقط محتوای مجازش را می‌بیند؛ دکمه‌های admin علاوه بر UI در API هم محدودند.

| مسیر | محتوا و عمل |
| --- | --- |
| `/admin` | خلاصه و کار بعدی |
| `/admin/activities` | جست‌وجو، بُعد، وضعیت، فعال/غیرفعال؛ جدول صفحه‌بندی‌شده |
| `/admin/activities/[id]` | raw، نسخه‌ها، منشأ، validation و audit مربوط به محتوا |
| `/admin/revisions/[id]` | ویرایش metadata و متن، preview موبایل، diff و submit |
| `/admin/review` | نسخه‌های review و تصمیم admin |
| `/admin/jobs` | نوع job، وضعیت، attempts، usage، خطا و زمان |
| `/admin/import` | فایل، preview، خطاهای ردیفی و commit |
| `/admin/coverage` | جدول پوشش contextها از متادیتای عمومی منتشرشده |
| `/admin/users` | admin؛ جست‌وجوی حساب و وضعیت، suspend/unsuspend |
| `/admin/metrics` | admin؛ funnel تجمیعی و feedback aggregate با حداقل گروه |
| `/admin/audit` | admin؛ actor/action/target/time |

## ویرایش تجربه

سه بخش واضح: «محتوای تجربه»، «شرایط واقعی اجرا»، «بررسی و پیش‌نمایش». فیلدهای فنی schema با label انسانی، نه textarea عظیم JSON به‌عنوان راه اصلی. title، teaser،first_step،steps،lighter_version و noteها در بخش اول؛ زمان،هزینه،وسایل،محیط،همراه و دسترسی در دوم؛ خطاها و checklist در سوم.

preview همان کامپوننت کارت و جزئیات user را با دادهٔ draft به‌کار ببرد؛ route نمایش draft فقط پشت مجوز editor/admin باشد. warning price unknown یا accessibility null پنهان نشود. submit نیازمند validation pass؛ publish نیازمند review state و expected_draft_version. اگر همکار ویرایش کرده conflict نشان بده و reload/merge دستی؛ overwrite بی‌صدا ممنوع.

publish و withdraw نام محتوا و نتیجهٔ دقیق را در dialog نشان دهند؛ برای withdraw دلیل لازم و اثر روی پیشنهادهای جاری روشن باشد. انتشار برگشت‌پذیر از طریق نسخهٔ تازه است، حذف فیزیکی ندارد. bulk publish در نسخهٔ اول نداریم. cook جدید نسخهٔ منتشرشده را ویرایش نکند و draft ویرایش‌شده را overwrite نکند؛ job نتیجهٔ پیشنهادی جدید یا conflict می‌سازد.

job cancel به معنی جلوگیری از ذخیرهٔ نتیجه است؛ لغو provider لزوماً تضمین قطع هزینه نیست. API key و base_url از صفحهٔ وب قابل تغییر نیستند. اپراتور فقط نام مدل و قابلیت‌های تأییدشده را می‌بیند؛ جزئیات تنظیمات در محیط سرور است.

## کاربران و حریم خصوصی

جدول ایمیل masked، نام، وضعیت و تاریخ عضویت؛ جست‌وجوی دقیق ایمیل برای پشتیبانی مجاز. صفحهٔ کاربر تاریخچهٔ حال، سؤال‌ها، feedback شخصی یا فعالیت‌ها را نمایش نمی‌دهد. تغییر رمز از طرف ادمین نداریم؛ ارسال لینک بازیابی با مسیر rate-limited معمول و پیام عمومی. تغییر role فقط CLI. audit علت اقدام، actor و target را ثبت می‌کند؛ password/token/full prompt شخصی ندارد.

## پذیرش ادمین

یک editor بذر را وارد کند، cook را ببیند، draft را اصلاح و submit کند؛ admin preview را ببیند و publish کند؛ user آن تجربه را در شرایط سازگار دریافت کند؛ withdraw باید بدون restart از همهٔ انتخاب‌های تازه حذف شود. تلاش editor برای publish مستقیم403 و تلاش user برای دیدن draft404 باشد.
