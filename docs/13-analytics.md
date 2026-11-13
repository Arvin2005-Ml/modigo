# سنجش و رویدادها

دادهٔ عملیاتی برای اجرا و سوابق لازم است؛ analytics رفتار رابط اختیاری و پیش‌فرض خاموش است. toggle consent در profile با `analytics_opt_in` و version سیاست ثبت شود. endpoint analytics در opt-out داده را نپذیرد و204 بازگرداند؛ پاسخ202 سندAPI فقط وقتی opt-in است. هیچ third-party tracker در نسخهٔ اول نیاز نیست.

## قرارداد allowlist

| event name | properties مجاز | منبع |
| --- | --- | --- |
| `check_in_opened` | flow_version | client opt-in |
| `check_in_step_completed` | flow_version,step_number | client opt-in؛ بدون answer |
| `recommendations_impressed` | session_id,slot_ids | client opt-in؛ حداقل۵۰٪نمایان برای۱ثانیه، dedupe/session/slot |
| `activity_opened` | session_id,slot_id,revision_id | client opt-in |
| `slot_replaced` | session_id,slot_id | server operational |
| `activity_saved` | activity_id | server operational |
| `experience_started` | experience_id,activity_id,algorithm_version | server operational |
| `experience_completed` | experience_id,primary_dimension | server operational |
| `experience_cancelled` | experience_id | server operational |
| `feedback_submitted` | experience_id,rating,reason | server operational، گزارش فقط تجمیعی |
| `badge_earned` | badge_key | server operational |

رویدادهای server operational از writeهای دامنه استخراج شوند و به collection analytics_eventsِ اختیاری وابسته نیستند. ارسال client نمی‌تواند completion،XP یا badge ایجاد کند؛ نام server-only از endpoint عمومی رد شود. session/slot/revision ارسالی باید متعلق به خود کاربر و سازگار با هم باشند؛ properties اضافی و متن آزاد422. timestamp کلاینت حداکثر۲۴ساعت فاصله و۵دقیقه آینده؛ زمان اعتماد received_at است. event_id تکراری به‌عنوان duplicate شمرده شود.

## شاخص‌ها با مخرج روشن

| شاخص | تعریف |
| --- | --- |
| تکمیل سؤال‌ها | check-in created تقسیم check_in_opened، فقط cohort opt-in؛ تحلیل drop-off قابل تعمیم به همه نیست |
| شروع از پیشنهاد | sessionهایی با start طی۲۴ساعت تقسیم sessionهای ایجادشده؛ operational و برای همه، impression واقعی ادعا نشود |
| پذیرش بین دیده‌ها | start از slot impressed تقسیم slot impressions، فقط opt-in |
| پایان تجربه | completed تا۲۴ساعت از start تقسیم started؛ خوداظهاری، نه تأیید انجام واقعی |
| رضایت صریح | liked تقسیم feedbackهای ثبت‌شده؛ با response rate کنار آن |
| کمبود نتیجه | session با count<6 تقسیم همهٔ sessionها؛ صفر جدا گزارش شود |
| تنوع | تعداد primaryهای متمایز هر slate؛ با constraints و partial همراه |
| پوشش محتوا | تعداد eligible در ماتریس contextهای آزمون، بدون دادهٔ فردی |
| کیفیت AI | pass schema،قبولی انسان،repair rate،latency،usage و unknown cost |

اهداف اولیه را پس از پایلوت با دادهٔ واقعی تعیین کن. شاخص اصلی صرفاً CTR نیست. ادعای افزایش سلامت روان یا رضایت زندگی از completion این محصول استنتاج نشود. cohort جدید/بازگشتی و نسخهٔ algorithm/prompt در گزارش جدا؛ هیچ نموداری برای cohort کمتر از۱۰کاربر منتشر نشود. فیلتر mood فردی یا خروجی قابل شناسایی در admin نداریم.

## آزمایش

نسخهٔ اول rules_v1 پایدار باشد. بعداً تخصیص variant با hash user و experiment_id، rollout کم‌دامنه و stop criteria برای افزایش zero-result،خطا یا شکایت. توزیع constraints دو گروه کنترل شود. بدون دادهٔ کافی «برنده» اعلام نکن. یک recommendation session وسط کار variant عوض نکند.
