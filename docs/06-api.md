# قرارداد HTTP نسخهٔ اول

**فاز جاری — ۹ نوامبر ۲۰۲۶:** API از MongoDB واقعی روی endpoint عمومی استفاده می‌کند. atomicهای دامنه و رسید idempotency در transaction واقعی مشترک‌اند؛ نسخه و مالکیت همچنان در backend کنترل می‌شوند. قطع DB پاسخ503 دارد و fallback حافظه‌ای وجود ندارد. [سند24](24-mongodb-storage.md) مقدم بر تصمیم ماک سند21 است.

Base path: `/api/v1`. همهٔ JSONها UTF-8، نام فیلدها snake_case. OpenAPI تولیدشدهٔ FastAPI مرجع type generation فرانت است؛ این سند رفتار مورد انتظار آن را تعیین می‌کند. همهٔ مسیرهای user مالکیت را از نشست می‌گیرند، نه `user_id` ورودی. شیء دیگران 404؛ نقش ناکافی 403. timestamp، enum و حدود طبق `05`.

**قرارداد جاری مالک — ۹ نوامبر ۲۰۲۶:** نتیجه یک پیشنهاد و حداکثر شش تعویض موفق در همان نوبت است. `items` صفر یا یک عضو و `partial` فقط در نتیجهٔ صفر true است؛ `empty_reason` فقط `null` یا `NO_MATCHES` است. پاسخ session شامل `replacement_count`, `replacement_limit`, `replacements_remaining`, `replacement_available` است. همچنین `suggestion_index` صفرمبنا و `suggestion_count` تعداد دیده‌شده‌ها را دارد؛ فقط کارت جاری برمی‌گردد. ساخت مجدد با همان check-in، همان session و شمارنده و جای مرور جاری را برمی‌گرداند. مرور قبلی/بعدی بدون مصرف سهمیه است و بعد از شش تعویض هم مجاز می‌ماند؛ گزینهٔ تازه فقط در انتهای تاریخچه گرفته می‌شود. POST تعویض علاوه بر این چهار فیلد، `replaced` را برای موفقیت همین درخواست می‌دهد؛ `replacement_available` امکان تعویض بعدی است. نبود گزینه 200 و `replaced:false`، بدون مصرف سهمیه؛ پس از شش موفقیت، تلاش بعدی 409 `REPLACEMENT_LIMIT` است. مالکیت، CSRF، idempotency و expected_version همچنان لازم‌اند. دو فیلد اختیاری `need_now` و `desired_outcome` از enum `Goal` به check-in اضافه شدند. [سند23](23-single-suggestion.md) بر جدول‌ها و مثال‌های قدیمی شش‌کارتی و سقف سه slate در ادامه مقدم است.

## قواعد عمومی

موفقیت: entity مستقیم؛ لیست `{items:[],next_cursor:null}`. pagination با cursor opaque و limit پیش‌فرض۲۰، سقف۱۰۰ و ترتیب پایدار `(created_at,id)` نزولی. فهرست عمومی همهٔ کاربران، کاتالوگ خام و jobها نداریم. پاسخ‌های شخصی `Cache-Control: no-store`. خطا:

```json
{"error":{"code":"VALIDATION_ERROR","message":"وقت آزاد رو بین ۵ تا ۴۸۰ دقیقه وارد کن.","fields":{"available_minutes":"out_of_range"},"request_id":"req-example"}}
```

کدهای مرجع: 400 `INVALID_REQUEST`، 401 `AUTH_REQUIRED`، 403 `FORBIDDEN/CSRF_FAILED/EMAIL_NOT_VERIFIED`، 404 `NOT_FOUND`، 409 `VERSION_CONFLICT/ACTIVE_EXPERIENCE/INVALID_STATE/IDEMPOTENCY_CONFLICT/REPLACEMENT_LIMIT/HISTORY_BOUNDARY/HISTORY_NOT_AT_END`، 410 `SESSION_EXPIRED/CONTENT_WITHDRAWN`، 422 `VALIDATION_ERROR`، 429 `RATE_LIMITED` با Retry-After، 503 `TEMPORARILY_UNAVAILABLE`. body خطا stack trace و اطلاعات provider ندارد. کمبود نتیجه 200 است.

برای همهٔ mutationهای authenticated، header `X-CSRF-Token` و Origin معتبر لازم است. `GET /auth/csrf` توکن نشست را می‌دهد؛ قبل از ورود هم pre-auth cookie و توکنِ وابسته صادر می‌شود، و signup/login/forgot/reset/verify هم CSRF می‌خواهند. نقش‌ها در `10`.

`Idempotency-Key` رشتهٔ تصادفی ۱۶..۱۲۸ کاراکتر برای create check-in، create slate، replace، navigate، start، complete و enqueue cook لازم است. Scope ترکیب user/route/resource؛ hash canonical payload ذخیره شود. تکرار کلید با payload یکسان همان status/body، payload متفاوت409. receipt و mutation در یک transaction؛ کلید جدید مجوز تکرار اثر نیست، قیدهای دامنه جدا اعمال می‌شوند. GET، PUT و DELETE ذاتاً idempotent مطابق جدول‌اند. در ادمین نیز کلید وابسته به actor است.

## هویت و پروفایل

| Method / path | درخواست | پاسخ |
| --- | --- | --- |
| GET `/auth/csrf` | بدون body | 200 `{csrf_token}` و pre-auth/session cookie لازم |
| POST `/auth/signup` | `{email,password,display_name?,adult_confirmed:true}` | 202 پیام عمومی «اگه این نشانی قابل استفاده باشه، ایمیل راهنما می‌رسه»؛ ایمیل تازه verification، موجود ایمیل راهنمای ورود با rate limit؛ هنوز session صادر نشود |
| POST `/auth/verify-email` | `{token}` | 200 `{verified:true}`؛ token یک‌بارمصرف؛ سپس ورود |
| POST `/auth/resend-verification` | `{email}` | 202 عمومی و rate-limited |
| POST `/auth/login` | `{email,password}` | 200 `{user,csrf_token}` و cookie نشست؛ عدم تطبیق401 عمومی، حساب معتبر تأییدنشده403 |
| POST `/auth/logout` | `{}` | 204؛ نشست باطل و cookie حذف؛ تکرار بی‌اثر |
| POST `/auth/logout-all` | `{password}` | 204؛ همهٔ نشست‌ها باطل |
| POST `/auth/forgot-password` | `{email}` | 202 پیام عمومی مستقل از وجود ایمیل |
| POST `/auth/reset-password` | `{token,new_password}` | 204؛ token مصرف و همهٔ نشست‌ها باطل |
| GET `/me` | — | 200 `{id,display_name,email,role,email_verified,timezone,status}` |
| PATCH `/me` | `{display_name?,timezone?}` | 200 user؛ role/email/status قابل نوشتن نیست |
| GET `/me/preferences` | — | 200 `{version,preferences}` طبق05 |
| PUT `/me/preferences` | `{version,preferences}` کامل طبق05 | 200 `{version,preferences}` جدید؛ conflict409 |
| POST `/me/change-password` | `{current_password,new_password}` | 204؛ نشست‌ها باطل؛ ورود مجدد |
| GET `/me/export` | — | 200 فایل JSON از دادهٔ خود کاربر؛ حداکثر۱ درخواست در روز |
| DELETE `/me` | `{password,confirmation:"DELETE"}` | 202 `{status:"deleting"}`؛ فوری revoke، purge حداکثر۷روز |

برای logout تکراری بدون نشست، همان204 برگردد؛ Origin همچنان کنترل شود. محدودیت‌های مهم login و SMTP در `10` و `15` است.

## پیشنهاد و تجربه

| Method / path | درخواست / پاسخ اصلی |
| --- | --- |
| POST `/check-ins` | context طبق05؛ 201 `{id,context,created_at}` |
| POST `/recommendation-sessions` | `{check_in_id}`؛ 201 session؛ یک session برای هر check-in، درخواست تکراری حتی با کلید تازه همان session جاری را می‌دهد |
| GET `/recommendation-sessions/{id}` | 200 session مالک؛ expired→410 با امکان ساخت check-in جدید |
| POST `/recommendation-sessions/{id}/slots/{slot_id}/replace` | `{expected_version:1}`؛ 200 `{session_version,item,replaced,replacement_count,replacement_limit,replacements_remaining,replacement_available,suggestion_index,suggestion_count}`؛ نبود گزینه200 با item قبلی و `replaced:false`، بدون مصرف سهمیه/نسخه؛ سقف409 `REPLACEMENT_LIMIT`، میانهٔ تاریخچه409 `HISTORY_NOT_AT_END` |
| POST `/recommendation-sessions/{id}/navigate` | `{direction:"previous"\|"next",expected_version}`؛ 200 session کامل با کارت جاری؛ مرور نسخه را زیاد می‌کند، سهمیه ثابت؛ مرز409 `HISTORY_BOUNDARY`؛ CSRF و idempotency لازم |
| GET `/activity-revisions/{id}` | 200 content کامل منتشرشده/superseded به‌همراه activity_id؛ withdrawn410؛ draft404 برای user |
| GET `/saved` | لیست آخرین revision فعال هر activity؛ مورد inactive با `{unavailable:true,activity_id}`، بدون محتوای ممنوع |
| PUT `/saved/{activity_id}` | `{}`؛ 204؛ فقط activity منتشرشده و فعال |
| DELETE `/saved/{activity_id}` | 204، حتی اگر قبلاً نبود |
| POST `/experiences` | `{recommendation_session_id,slot_id,revision_id}`؛ 201 experience active |
| GET `/experiences/active` | 200 `{experience:...}` یا `{experience:null}`؛ قبل از پاسخ active منقضی شود |
| GET `/experiences` | history با filter status و cursor |
| GET `/experiences/{id}` | 200 experience مالک؛ content_snapshot تاریخی |
| POST `/experiences/{id}/complete` | `{}`؛ 200 `{experience,award:{points,total_points,new_badges,reason}}` |
| POST `/experiences/{id}/cancel` | `{}`؛ 200 experience cancelled؛ تکرار همان200، completed409 |
| PUT `/experiences/{id}/feedback` | `{rating,reason:null}`؛ 200 feedback؛ فقط completed؛ ویرایش مجاز، XP ندارد |
| DELETE `/experiences/{id}/feedback` | 204؛ حذف اثر از شخصی‌سازی خواندن بعد |
| GET `/me/journey` | 200 `{total_points,rewarded_completions,completed_dimensions,badges}` |
| POST `/analytics/events` | `{events:[{event_id,name,occurred_at,properties}]}`؛ 202 `{accepted,duplicates}`؛ سقف۲۰ در batch، allowlist13 |

شروع فقط از slot فعلی session معتبر، مالک، activity فعال و **همان revision که هنوز published_revision_id جاری است**؛ اگر نسخهٔ تازه منتشر شده409 `VERSION_CONFLICT` و دعوت به تازه‌کردن پیشنهاد. شرایط واقعی محتوا با snapshot دوباره hard-filter شوند چون قیمت/انتشار ممکن است عوض شده باشد؛ excludeهای تاریخچه و «قبلاً در همین slate دیده‌شده» در این بررسی اعمال نشوند. محدودیت‌های ماندگارِ تازه مثل blocked_tags و الزام دسترسی نیز سخت‌گیرانه با snapshot union شوند. اگر slot عوض شده VERSION_CONFLICT. تجربهٔ فعال دیگر409 با id خودش. پیش از start، active منقضی همان کاربر در transaction بسته شود. سابقهٔ ذخیره‌ها برای شروع از مسیر check-in با شرایط تازه عبور کند، نه bypass فیلتر.

create slate در transaction با CAS روی check_ins.version،افزایش created_slate_count و union شناسه‌های activity نمایش‌داده‌شده انجام شود؛ دو درخواست هم‌زمان همان یک session را دریافت می‌کنند. مرور نیز session.version را کنترل می‌کند؛ هم‌زمانی فقط یک حرکت اعمال می‌کند. شروع از کارت قبلی پس از بازگشت صریح مجاز است؛ کارت غیرجاری رد می‌شود. replace نیز session.version و check_in.version را همراه تغییر یک slot اتمیک عوض می‌کند. start برای رقابت با replace،write روی session با شرط version/slot جاری و برای رقابت با withdraw/publish،write محافظ روی activity با شرط active و published_revision_id انجام دهد؛ write محافظ counter داخلی `start_guard_version` را افزایش می‌دهد،نه محتوای revision را. فقط read در snapshot transaction جلوی همهٔ raceها را نمی‌گیرد. ترتیب دستیابی به اسناد مشترک در application service ثابت باشد و خطای conflict با retry محدود مدیریت شود.

نمونهٔ session؛ مقدار شناسه‌ها در این نمونه فقط برای خوانایی کوتاه است، دادهٔ واقعی UUID است:

```json
{
  "id":"session-example","check_in_id":"checkin-example","version":1,
  "expires_at":"2026-11-07T10:00:00Z",
  "items":[{
    "slot_id":"slot-example","activity_id":"activity-example","revision_id":"revision-example",
    "rank":1,"execution_social_mode":"solo","execution_people":1,
    "title":"صدای خونه رو پیدا کن","teaser":"چند دقیقه فقط شنوندهٔ صداهای همین اطرافت باش.",
    "total_minutes":10,"cost_label":"رایگان","explanation":"با وقت و انرژی الانت جور درمیاد."
  }],
  "result_count":1,"partial":false,"empty_reason":null,
  "replacement_count":0,"replacement_limit":6,"replacements_remaining":6,"replacement_available":true,
  "suggestion_index":0,"suggestion_count":1
}
```

برای یک کارت قابل نمایش `partial:false,empty_reason:null`؛ صفر کارت مجاز `partial:true,empty_reason:"NO_MATCHES"`. تاریخچهٔ مرور می‌تواند کارت withdrawn بدون متن را در slot جاری نگه دارد؛ با قبلی/بعدی همچنان جابه‌جا می‌شود. مدل یا score از خروجی حذف می‌شود. `content_snapshot` تجربهٔ مالک پس از withdrawal با برچسب unavailable و حذف دستورالعمل ممنوع پاسخ داده شود، هرچند snapshot داخلی برای audit حفظ است.

GET یک session قدیمی،کارت withdrawn یا archived را با `{slot_id,unavailable:true}` بدون متن محتوا پاسخ دهد؛ slot حفظ شود تا کاربر replace کند. `result_count` تعداد کارت‌های قابل نمایش است. جایگزینی خودکار و بی‌خبر انجام نشود؛برای نسخهٔ superseded ولی هنوز مجاز،جزئیات تاریخی قابل دیدن است و شروع نیازمند پیشنهاد تازه طبق قاعدهٔ بالا. expiry پیشنهاد،expiry تجربهٔ شروع‌شده نیست؛تجربه از started_at خود۲۴ساعت فرصت دارد.

## ادمین؛ همه با audit و مجوز سرور

| Method / path | نقش | رفتار |
| --- | --- | --- |
| GET `/admin/activities` | editor/admin | فیلتر dimension/state/active/seed_key؛ pagination |
| POST `/admin/activities` | editor/admin | raw_title,raw_intent,primary_dimension؛ 201 draft activity |
| GET `/admin/activities/{id}` | editor/admin | نسخه‌ها، metadata و validation |
| POST `/admin/activities/{id}/revisions` | editor/admin | clone از نسخهٔ مشخص یا draft خالی؛ 201 |
| PATCH `/admin/revisions/{id}` | editor/admin | `{expected_draft_version,content}`؛ فقط draft/rejected |
| POST `/admin/revisions/{id}/submit` | editor/admin | `{expected_draft_version}`؛ draft→review، validator باید pass باشد |
| POST `/admin/revisions/{id}/reject` | admin | `{expected_draft_version,note}`؛ review→rejected |
| POST `/admin/revisions/{id}/publish` | admin | `{expected_draft_version}`؛ review→published؛ pointer جابه‌جا و قدیمی superseded، transaction |
| POST `/admin/activities/{id}/withdraw` | admin | `{reason}`؛ active=false و همهٔ revisionهای قابل نمایش archived؛ فوراً از پیشنهاد/شروع حذف |
| POST `/admin/activities/{id}/reactivate` | admin | `{reason}`؛ فقط وقتی review تازه و publish معتبر دارد؛ در غیر این صورت409 |
| POST `/admin/activities/{id}/cook` | editor/admin | `{prompt_version,expected_draft_version,target_draft_id?}`؛ 202 `{job_id,state}`؛ یک job فعال برای هر activity |
| GET `/admin/jobs` و `/admin/jobs/{id}` | editor/admin | وضعیت و خطای پالایش‌شده، نه کلید یا chain-of-thought |
| POST `/admin/jobs/{id}/cancel` | editor/admin | idempotent؛ خروجی دیررس ذخیره نشود |
| POST `/admin/content/import/preview` | editor/admin | فایل JSON حداکثر۱MB و۵۰۰رکورد؛ 200 گزارش و preview_id با TTL یک‌ساعته |
| POST `/admin/content/import/commit` | admin | `{preview_id,expected_checksum}`؛ 202 job importer؛ conflict با تغییر بانک |
| GET `/admin/users` | admin | جست‌وجوی دقیق ایمیل یا id؛ PII محدود؛ cursor |
| POST `/admin/users/{id}/suspend` و `/unsuspend` | admin | `{reason}`؛ revoke فوری؛ self/last-admin محدود |
| GET `/admin/coverage` | editor/admin | ماتریس coverage از metadata عمومی منتشرشده؛ بدون دادهٔ شخصی |
| GET `/admin/metrics` | admin | date range حداکثر۹۰روز و گزارش تجمیعی |
| GET `/admin/audit` | admin | فیلتر actor/action/target/date و pagination |

previewها در collection `import_previews` با actor_id، checksum، parsed_rows، errors، expires_at و قید id ذخیره شوند؛ jobs نوع `kind: cook|import` دارند. import نیازی به provider ندارد. هیچ endpoint عمومی تغییر role یا مدل دلخواه/base_url دلخواه ندارد. مقدار مدل و URL از config سرور است. برای cook،expected_draft_version=0 یعنی هنوز target draft نداریم؛ enqueue یک draft جدید با draft_version=1 رزرو می‌کند و target_draft_id آن را در job می‌گذارد. برای draft موجود،id از activity با قرارداد «حداکثر یک draft باز برای cook هر activity» مشخص و version باید برابر باشد؛ ویرایش حین job نسخه را افزایش می‌دهد و خروجی دیررس با409 در گزارش job شکست می‌خورد،نه overwrite. draftهای انسانی دیگر باید id صریح داشته باشند؛ اگر چند draft باز هست،cook422 با درخواست انتخاب draft و فیلد اختیاری target_draft_id می‌خواهد. حداکثر یک job cook فعال برای activity،مستقل از کلید idempotency.
