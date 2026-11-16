# منابع و حدود اطمینان

بررسی در۶نوامبر۲۰۲۶. این بسته طراحی تألیفی محصول است؛ وزن‌های recommender،بانک۴۵۰تایی و قوانین گیمیفیکیشن یافتهٔ پژوهشی یا ابزار بالینی نیستند. نشانی منابع برای مراجعهٔ ایجنت به‌صورت code آمده‌اند؛ منبع را پیش از تصمیم نسخه‌ای دوباره بررسی کند.

## چارچوب DRAMMA

S1. Newman،Tay و Diener، «Leisure and Subjective Well-Being: A Model of Psychological Mechanisms as Mediating Factors»،Journal of Happiness Studies 15،۵۵۵–۵۷۸،۲۰۱۴؛ انتشار آنلاین۱۶آوریل۲۰۱۳. DOI: `10.1007/s10902-013-9435-x`.

نسخهٔ مقاله روی وب‌سایت نویسنده: `https://www.davidbenjaminnewman.com/uploads/1/3/2/7/132771163/johs-2014-leisure_and_swb.pdf`.

در صورت‌بندی اولیه،detachment-recovery باهم آمده و پنج سازوکار اصلی شرح داده شده است. برای این محصول مدل شش‌نیازیِ به‌کاررفته در S2 را مبنا می‌گیریم؛ تعداد۷۵فعالیت در هر بُعد تصمیم بانک محتوایی است و از مقاله استخراج نشده است.

S2. Kujanpää و همکاران، «Need Satisfaction and Optimal Functioning at Leisure and Work: A Longitudinal Validation Study of the DRAMMA Model»،انتشار آنلاین۲۶مارس۲۰۲۰،جلد۲۲ صفحات۶۸۱–۷۰۷ در۲۰۲۱. DOI: `10.1007/s10902-020-00247-3`؛ صفحهٔ ناشر: `https://link.springer.com/article/10.1007/s10902-020-00247-3`.

این پژوهش شش نیاز detachment،relaxation،autonomy،mastery،meaning،affiliation را عملیاتی کرده است. از چارچوب برای سازمان‌دهی محتوا استفاده می‌کنیم؛ اثر این اپ،دقت پیشنهاد برای فارسی‌زبانان و اثر هر بذر باید مستقل سنجیده شوند. این شش سبد یک تقسیم‌بندی قطعی و انحصاری از تفریح نیستند.

## منابع فنی اولیه

| مرجع | نشانی | استفاده در طراحی |
| --- | --- | --- |
| S3 OpenAI Responses Python API Reference | `https://developers.openai.com/api/reference/python/resources/responses/methods/create` | قرارداد Responses سمت OpenAI،نه تضمین provider ثالث |
| S4 OpenAI Python SDK در مستند رسمی | `https://developers.openai.com/api/reference/python` | تنظیم base_url،timeout،retry و API client؛ قابلیت مدل جدا آزموده می‌شود |
| S5 FastAPI Bigger Applications | `https://fastapi.tiangolo.com/tutorial/bigger-applications/` | APIRouter و جداسازی فایل‌ها؛ مرزهای دامنه تصمیم این پروژه‌اند |
| S6 Next.js App Router | `https://nextjs.org/docs/app/getting-started` | مبنای مسیرها و ساختار frontend؛ نسخه هنگام ساخت pin شود |
| S7 MongoDB Transactions | `https://www.mongodb.com/docs/manual/core/transactions/` | اتمیک‌بودن چندسندی با transaction روی replica set |
| S8 MongoDB TTL Indexes | `https://www.mongodb.com/docs/manual/core/index-ttl/` | پاک‌سازی تأخیری،بدون اتکا به TTL برای انقضای امنیتی |
| S9 OWASP Session Management | `https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html` | opaque sessions،cookie flags،rotation و انقضای سمت سرور |

حدودِ توصیهٔ طراحی را از قابلیت مستندشده جدا کن: مقدار عمر نشست،وزن‌ها،کپ امتیاز،۲۴نمونهٔ demo و budget caps انتخاب‌های این بسته‌اند. استقرار یا انطباق حقوقی با خواندن این منابع احراز نمی‌شود.

## GapGPT

مبنای مطمئن فعلی،نمونهٔ ارسال‌شدهٔ خود مالک است: OpenAI client،base_url=`https://api.gapgpt.app/v1`،Responses،مدل=`deepseek-v4.1-flash` و reasoning high. صفحهٔ عمومی `https://gapgpt.app/` هنگام بررسی محتوای مستندات فنی این مدل را در خروجی قابل خواندن ارائه نکرد؛ جست‌وجوی نام دقیق نیز سند عمومی قابل اتکای کافی نداد. بنابراین موجودبودن مدل،پشتیبانی strict schema و Responses،سقف توکن،نرخ،سیاست نگهداری و کیفیت واقعی **تأیید زنده نشده‌اند**. adapter و smoke test سند08 برای حل همین عدم قطعیت‌اند؛ هیچ call پولی یا استفاده از کلید واقعی در تهیهٔ این بسته انجام نشده است.
