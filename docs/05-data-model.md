# مدل داده و انواع مرجع

**فاز جاری — ۹ نوامبر ۲۰۲۶:** اسناد در collectionهای واقعی MongoDB روی endpoint عمومی ذخیره می‌شوند. UUID رشته‌ای به `_id`، زمان به BSON UTC با دقت میلی‌ثانیه و atomic به transaction واقعی نگاشت می‌شود. نسخهٔ عمومی store با شمارهٔ محتوایی `revision_number` و `draft_version` جداست. نام فیلدها و ایندکس‌های اجرایی در `app/core/mongo.py` و [سند24](24-mongodb-storage.md) ثبت شده‌اند؛ جدول پایین طرح دامنه است و برای قابلیت‌های پیاده‌نشده ادعای اجرا ندارد.

همهٔ زمان‌های ذخیره‌شده BSON UTC Date و در JSON رشتهٔ RFC3339 با `Z` هستند. timezone نمایشی/روز امتیاز از IANA profile، پیش‌فرض `Asia/Tehran`. شناسهٔ موجودیت‌ها UUID4 به‌شکل string؛ `seed_key` مانند `D001` جدا و یکتاست. مبلغ integer تومان است؛ float برای پول ممنوع. متن‌ها Unicode نرمال‌شده، سقف طول و `extra=forbid` در DTOهای ورودی.

## enumها

```text
Dimension = detachment | relaxation | autonomy | mastery | meaning | affiliation
Energy = low | medium | high | unknown
SocialMode = solo | together | either
CheckInVenue = home | away_from_home | any | outdoor | indoor_public
ActivityVenue = home | outdoor | indoor_public
BudgetMode = free | cap | flexible
Mood = tired | restless | bored | low | okay | skip
Goal = unwind | switch_off | learn | connect | meaning | choose | any
Mobility = seated | light | active
Weather = fair | adverse | unknown
Daylight = day | night | unknown
FeedbackRating = liked | neutral | disliked
FeedbackReason = time | cost | interest | access | too_hard | repeated
```

`seated < light < active` ترتیب نیاز به تحرک است؛ `max_mobility` پیش‌فرض active، نیاز حرکتی خاص تنها با اعلام کاربر. `requires_step_free` و `requires_quiet` boolean هستند. هیچ تشخیص پزشکی نگهداری نشود. tagهای علاقه/مسدود و itemها از واژگان کنترل‌شدهٔ نسخه‌دار بیایند؛ مثال `nature`, `music`, `drawing`, `walking`, `paper`, `pen`, `phone`, `internet`, `kitchen`. افزودن tag جدید در import با تأیید ادمین و migration واژگان، نه متن آزاد کاربر.

## Context؛ snapshot هر نوبت

**پرسش‌نامهٔ کوتاه — ۱۸ نوامبر ۲۰۲۶:** در ورودی و snapshot نوبت، `away_from_home` یعنی اجتماع `outdoor` و `indoor_public` و خانه را شامل نمی‌شود. دو مقدار تفکیک‌شده برای سازگاری با درخواست‌ها و snapshotهای قبلی معتبرند. `activity_intent` پاسخ واحد و یک `Goal` است؛ فرانت جدید آن را صریح می‌فرستد. مقدار صریح، حتی `any`، جای `mood`، `need_now` و `desired_outcome` را در رتبه‌بندی می‌گیرد. نبود فیلد یا `null` مسیر قبلی را حفظ می‌کند. `mood`ِ حذف‌شده `skip`، و دو پاسخ قبلیِ حذف‌شده `any` هستند. پاسخ جدید فقط در snapshot نوبت می‌ماند؛ قرارداد پروفایل و کاتالوگ تغییر نمی‌کنند. نمونهٔ [سند35](35-individual-questionnaire.md) برای کلاینت جدید است.

**تصمیم جاری مالک — ۹ نوامبر ۲۰۲۶:** دو فیلد `need_now` و `desired_outcome` از نوع `Goal` با پیش‌فرض `any` به context اضافه شدند. این‌ها پاسخ دو سؤال موقعیتی‌اند و در profile ذخیره نمی‌شوند. session پیشنهاد حداکثر یک item دارد و شامل `replacement_count=0` و `replacement_limit=6` است؛ `check_ins.recommendation_session_id` به تنها session آن نوبت اشاره می‌کند. `suggestion_history` حداکثر هفت snapshot مرتب از itemهای عرضه‌شده و `suggestion_index` اندیس صفرمبنای جاری است. مرور شمارنده را تغییر نمی‌دهد؛ فقط نسخه و item جاری عوض می‌شوند. DTO شامل `suggestion_index` و `suggestion_count` است و تاریخچهٔ داخلی را نمی‌دهد. سابقهٔ انتخاب بُعد از `primary_dimension_snapshot` تجربه‌های همان کاربر، با یک رأی برای هر recommendation session و نخستین شروع موفق آن، خوانده می‌شود؛ نمایش، تعویض، ذخیره و پایان مجدد رأی نیستند. مشخصات جاری در [23](23-single-suggestion.md) بر متن‌های قدیمی شش‌کارتی این سند مقدم است.

```json
{
  "available_minutes": 30,
  "energy": "low",
  "social_mode": "solo",
  "party_size": 1,
  "venue": "home",
  "budget": {"mode": "free", "cap_toman": null},
  "activity_intent": "unwind",
  "goal": "any",
  "owned_items": [],
  "max_mobility": "light",
  "requires_step_free": false,
  "requires_quiet": false,
  "weather": "unknown",
  "daylight": "unknown",
  "allow_async_contact": false,
  "liked_tags": [],
  "blocked_tags": []
}
```

حدود: وقت ۵..۴۸۰ دقیقه، اندازهٔ گروه ۱..۱۲، cap حداکثر ۱۰۰٬۰۰۰٬۰۰۰ تومان. برای solo، party_size=1؛ برای together حداقل۲؛ either با party_size=1 فقط solo،و با party_size>=2 هم solo و هم گروهی را می‌پذیرد. در حالت either تعداد واقعی اجرای هر candidate برابر۱برای solo و party_size برای together است؛ هزینه و min/max با همان تعداد محاسبه شوند. در UI انتخاب either کنترل تعداد همراه احتمالی را اختیاری با توضیح نشان دهد. free به cap=0 نرمال شود؛ cap مثبت لازم؛ flexible مقدار cap ندارد. فیلدهای شش سؤال اصلی لازم،بقیه optional‌اند. goal از default_goal پروفایل یا any،weather/daylight از unknown،allow_async_contact از پروفایل یا false پیش‌فرض می‌گیرند؛ درخواست صریح تماس async رضایت همان نوبت است. ارسال صریح owned_items=[] یعنی هیچ ابزاری در این نوبت در دسترس نیست؛ حذف فیلد یعنی ترجیح profile. blocked_tags اتحادیهٔ profile و context است؛requires_step_free و requires_quiet با OR و max_mobility با کمینهٔ نیاز پروفایل و context ادغام شوند. پاسخ موقعیتی فقط می‌تواند محدودیت سختِ ماندگار را بیشتر کند؛ برای کمترکردنش کاربر وارد تنظیمات شود.

## قرارداد Preferences

`GET /me/preferences` یک object شامل `version` integer و `preferences` می‌دهد. `PUT` همان دو فیلد را کامل می‌گیرد و version را اتمیک افزایش می‌دهد. preferences شامل `liked_tags:[]`, `blocked_tags:[]`, `owned_items:[]`, `max_mobility:active`, `requires_step_free:false`, `requires_quiet:false`, `allow_async_contact:false`, `default_goal:any`, `show_gamification:true`, `analytics_opt_in:false`, `analytics_policy_version:null` است. opt-in همراه policy_version جاری معتبر باشد؛ تغییر policy نیازمند درخواست رضایت تازه است. enumها و واژگان همین سند و content/README؛ max هر مجموعه۵۰مقدار،تکرار حذف و مجموعه‌ها مرتب نرمال شوند. default_goal فقط پیش‌فرض قابل تغییر در پرسش‌هاست. budget،mood،social و energy ماندگار نشوند. timezone در user است و `timezone_changed_at` برای قاعدهٔ۳۰روز نگه داشته شود.

## Activity و ActivityRevision

`activities`: `id`, `seed_key`, `primary_dimension`, `raw_title`, `raw_intent`, `active`, `published_revision_id|null`, `next_revision_version`, `start_guard_version`, `created_at`, `updated_at`. primary_dimension پس از انتشار فقط با فرآیند اصلاح محتوایی و audit تغییر کند. هیچ عنوان خام مستقیم به کاربر نمایش داده نشود. شمارهٔ revision با افزایش اتمیک counter رزرو شود؛ فاصله در شماره‌ها مجاز و تکرار ممنوع. start_guard_version فقط برای هماهنگی race شروع و انتشار در06 است،نسخهٔ محتوا نیست.

`activity_revisions`: `id`, `activity_id`, `version` integer، `state` از draft/review/rejected/published/superseded/archived، `draft_version` برای ویرایش هم‌زمان، `content` طبق قرارداد زیر، `origin` از human/llm/demo، `prompt_version|null`, `model|null`, `validation_report`, `reviewed_by|null`, `reviewed_at|null`, `published_at|null`, `created_at`. محتوای نسخهٔ منتشرشده immutable است؛ اصلاح نسخهٔ جدید می‌سازد. تغییر state عملیاتی مجاز است. archived برای نسخهٔ ممنوع‌نمایش است؛ superseded برای نسخهٔ قبلی هنوز قابل استناد در تاریخچه.

قرارداد کامل `content`:

| فیلد | نوع / محدودیت |
| --- | --- |
| `title` | فارسی، ۵..۶۰ نویسه |
| `teaser` | ۱۵..۱۴۰ نویسه، توصیف ملموس |
| `first_step` | ۵..۱۸۰ نویسه، یک عمل |
| `steps` | ۲..۵ رشته؛ هرکدام ۵..۲۴۰ نویسه |
| `lighter_version` | ۱۰..۲۴۰ نویسه، همان تجربه با تلاش کمتر؛ نسخهٔ مستقل eligible نیست |
| `materials_note` | ۱..۲۴۰ نویسه؛ «وسیلهٔ خاصی لازم نیست» معتبر |
| `accessibility_note` | ۱..۲۴۰ نویسه؛ محدودیت یا سازگاری واقعی |
| `conditions_note` | ۱..۲۴۰ نویسه؛ فرض‌های اجرا |
| `primary_dimension` | همان بُعد activity |
| `secondary_dimensions` | حداکثر۳ مورد متمایز از primary |
| `tags` | ۱..۸ tag کنترل‌شده |
| `active_minutes`, `setup_minutes`, `travel_minutes` | integer؛ active>=1، بقیه>=0؛ جمع ۵..۴۸۰ |
| `energy_required` | low/medium/high؛ unknown مجاز نیست |
| `mobility_required` | seated/light/active |
| `supported_social_modes` | زیرمجموعهٔ غیرخالی از solo/together؛ either مقدار کاتالوگ نیست |
| `min_people`, `max_people` | ۱..۱۲؛ حداقل سازگار با social modes |
| `venue` | home/outdoor/indoor_public؛ any مقدار کاتالوگ نیست |
| `required_items` | مجموعهٔ itemهای کنترل‌شده؛ اقلام اختیاری در توضیح، نه این مجموعه |
| `requires_async_contact` | boolean؛ تماس async حتی برای solo رضایت جدا می‌خواهد |
| `step_free` | boolean|null؛ null یعنی تأییدنشده |
| `quiet_compatible` | boolean|null |
| `weather_requirement` | any/fair |
| `daylight_requirement` | any/day |
| `cost` | قرارداد زیر |
| `safety_notes` | ۰..۳ رشتهٔ کوتاه و مرتبط؛ هشدار کلی نامرتبط نده |

`total_minutes` فیلد مشتق‌شده از سه زمان است، فقط server محاسبه می‌کند. نسخهٔ سبک‌تر زمان و وسایل نسخهٔ اصلی را برای ranking تغییر نمی‌دهد؛ اگر قرار است قابل پیشنهاد مستقل باشد باید revision/variant مستقل با metadata معتبر شود.

قواعد گروه: اگر solo در supported_social_modes است،min_people باید۱باشد؛ اگر فقط together است min_people حداقل۲. همراه با solo می‌توان max_people بالاتر داشت اما تنها اگر together هم پشتیبانی شود. برای together،execution_people حداقل۲است حتی اگر min_people=1 در نسخهٔ دوحالته باشد. نسخهٔ تک‌نفره نباید وجود همراه را در قدم‌ها لازم داشته باشد. قیمت estimated فقط با مدرک ویراستار در `validation_report.cost_evidence` شامل توضیح،منبع/روش تأیید و actor_id پذیرفته شود؛ verified_at آینده و valid_until<=verified_at رد شوند.

```json
{
  "kind": "free",
  "min_toman": 0,
  "max_toman": 0,
  "basis": "per_person",
  "verified_at": null,
  "valid_until": null,
  "note": "با وسایلی که از قبل داری؛ خرید لازم نیست."
}
```

`kind`: free/estimated/unknown. estimated به min<=max، `verified_at` و `valid_until` معتبر و حداکثر۳۰ روز پس از verified_at نیاز دارد. قیمت ساختگی از مدل ممنوع. unknown اعداد و تاریخ null دارد و فقط در budget flexible eligible است. basis per_person/per_group؛ هزینهٔ کل برای per_person در تعداد گروه ضرب می‌شود. free فقط وقتی خرید، بلیت، سفر پولی یا اشتراک تازه نیاز نیست؛ وسایل از قبل موجود می‌توانند required_items باشند. اینترنت/برق موجود هزینهٔ حاشیه‌ای محاسبه‌شده ندارند ولی نیازشان مشخص باشد. برآورد منقضی معادل unknown است.

## collectionها

| collection | فیلدهای مهم / قید |
| --- | --- |
| users | email_normalized،email_original، password_hash، role user/editor/admin، email_verified_at،adult_confirmed_at، status active/suspended/deleting، timezone،timezone_changed_at، display_name،created_at؛ unique email_normalized |
| auth_sessions | token_hash unique، user_id، csrf_hash، created_at، expires_at، last_seen_at، revoked_at؛ index user_id، TTL expires_at |
| account_tokens | token_hash unique، user_id، purpose verify_email/reset_password، expires_at، consumed_at؛ TTL expires_at |
| profiles | user_id unique، preferences شامل goal/tags/owned_items/constraints، updated_at |
| activities | seed_key unique sparse، active، primary_dimension، published_revision_id |
| activity_revisions | unique(activity_id,version)، index state و activity_id |
| check_ins | user_id، context،recommendation_session_id=null،created_slate_count=0،shown_activity_ids=[]،version، created_at، expires_at؛ index(user_id,created_at)، TTL expires_at=۹۰روز |
| recommendation_sessions | user_id، check_in_id، context_snapshot، items، suggestion_history،suggestion_index=0،replacement_count=0،replacement_limit=6،shown_activity_ids، version، algorithm_version، seed، created_at، expires_at=۲۴ساعت،purge_at=۹۰روز؛ index(user_id,created_at) |
| experiences | user_id، activity_id، revision_id، recommendation_session_id، slot_id، content_snapshot، context_snapshot، status active/completed/cancelled/expired، started_at، completed_at، completion_local_date، timezone_at_start، award_result؛ unique partial(user_id) where status=active |
| feedback | experience_id unique، user_id، rating، reason|null، updated_at؛ index(user_id,updated_at) |
| saved_activities | unique(user_id,activity_id)، saved_at؛ ذخیره به activity است، نه revision |
| reward_ledger | user_id،experience_id unique،activity_id،primary_dimension_snapshot،points،reason،award_date،rules_version،created_at؛index(user_id,award_date)،index(user_id,activity_id,created_at) |
| user_badges | unique(user_id,badge_key)، earned_at، source_experience_id |
| user_progress | user_id unique، total_points، rewarded_completions، completed_dimensions، version؛ projection قابل بازسازی |
| content_jobs | unique(idempotency_scope,key)،kind=cook/import،activity_id nullable،target_draft_id nullable،base_draft_version،state queued/running/succeeded/failed/cancelled،lease_owner،lease_until،attempts،next_run_at،model،prompt_version،usage،error_code،import_row_results؛ partial unique activity_id برای cook فعال |
| import_previews | actor_id،checksum،parsed_rows،errors،expires_at؛TTL expires_at،commit_job_id nullable برای commit یکتا |
| admin_audit | actor_id، action، target_id، diff_sanitized، request_id، created_at؛ append-only، index(target_id,created_at) |
| analytics_events | unique(user_id,event_id)، event_name، properties allowlist، occurred_at، received_at؛ TTL received_at=۹۰روز |
| idempotency_receipts | unique(user_id,route_scope,key)، request_hash، response_status، response_body_sanitized، expires_at=۲۴ساعت؛ TTL |
| rate_limit_buckets | bucket_hash، window_end، count؛ unique bucket_hash، TTL window_end |
| schema_migrations | migration_id unique، applied_at، checksum |

Session document item: `{slot_id, activity_id, revision_id, rank, execution_social_mode, execution_people, explanation, score_internal}`. یک slot حداکثر؛ slot_id در تعویض و مرور ثابت می‌ماند و revision جاری عوض می‌شود. snapshotهای قبلی در suggestion_history حفظ می‌شوند؛ حداکثر هفت، بدون مصرف سهمیه برای مرور. برای audit نسخهٔ الگوریتم و score ثبت شود، ولی score در DTO کاربر حذف است. شناسه‌های دیده‌شدهٔ همان check_in در تولید گزینهٔ تازه حذف می‌شوند؛ مرور snapshot قبلی این حذف را دور نمی‌زند چون تولید تازه نیست. experience نیز execution_social_mode و execution_people و primary_dimension_snapshot را مستقل ذخیره کند.

مجموعهٔ recommendation_sessions بعد از ۹۰ روز پاک شود (`purge_at` جدا از expires_at)؛ تجربه snapshot لازم را دارد. reward_ledger، user_badges و feedback تا حذف حساب نگه داشته شوند؛ aggregateها بی‌هویت و بدون گروه کوچک باقی می‌مانند. دادهٔ operational و analytics از یکدیگر برای authorization استفاده نکنند.
