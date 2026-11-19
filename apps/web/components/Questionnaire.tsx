import { useEffect, useId, useRef, useState } from "react";
import type { Context, OutingOrigin } from "@/types";
import { digits, number } from "@/lib/api";
import { Button, Choices } from "./ui";
import Icon from "./Icon";
import Personalization from "./Personalization";
import { activityIntentOptions } from "@/lib/personalization";

const stepLabels = [
  "وقت و انرژی",
  "همراه و محیط",
  "هزینهٔ دلخواه",
  "تفریح دلخواه",
];
const stepTitles = [
  "الان چقدر وقت و انرژی داری؟",
  "چه‌جوری بهت می‌چسبه؟",
  "چقدر دوست داری خرج کنی؟",
  "الان چه جور تفریحی بهت می‌چسبه؟",
];
const stepIntros = [
  "همون‌قدر که هست؛لازم نیست بیشترش کنی.",
  "شرایط واقعی الانت رو بگو تا انتخاب به کارت بیاد.",
  "بی‌خرج‌بودن هم یه انتخاب خوبه.",
  "با این جواب، اولین پیشنهاد رو به خواستهٔ الانت نزدیک‌تر می‌کنیم.",
];
const originRequired = "شهر مبدأ رو انتخاب کن.";
const shortDurations = [
  [15, "یه ربع"],
  [30, "نیم ساعت"],
  [60, "یه ساعت"],
  [120, "دو ساعت"],
  [240, "چهار ساعت"],
] as const;
const allDurations = [...shortDurations, [1440, "یک روز کامل"], [2880, "دو روز"]] as const;

export default function Questionnaire({
  value,
  change,
  submit,
  busy,
  defaults,
  outings,
  submitMessage,
}: {
  value: Context;
  change: (v: Context) => void;
  submit: () => void;
  busy: boolean;
  outings?: {
    origins?: readonly OutingOrigin[];
    unavailable: boolean;
    retry: () => void;
  };
  submitMessage?: string;
  defaults?: {
    owned_items: string[];
    liked_tags: string[];
  };
}) {
  const outingDays = outings ? value.outing_days : undefined;
  const origins = outings?.origins;
  const [step, setStep] = useState(0);
  const [minutes, setMinutes] = useState(outingDays ? "30" : String(value.available_minutes));
  const [cap, setCap] = useState(
    value.budget.cap_toman ? String(value.budget.cap_toman) : "",
  );
  const [party, setParty] = useState(String(value.party_size));
  const [error, setError] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);
  const originHintId = useId();
  const originErrorId = useId();
  const showOrigins = outingDays === 1 || (outingDays === 2 && value.allow_venue_planning);
  const originInvalid = error === originRequired;
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    heading.current?.scrollIntoView({ block: "nearest", behavior: "instant" });
  }, [step]);
  const set = <K extends keyof Context>(key: K, next: Context[K]) =>
    change({ ...value, [key]: next });
  const selectDuration = (availableMinutes: number) => {
    setError("");
    const days = availableMinutes === 1440 ? 1 : availableMinutes === 2880 ? 2 : undefined;
    if (outings && days) {
      if (days === outingDays) return;
      change({
        ...value,
        available_minutes: availableMinutes,
        outing_days: days,
        venue: "away_from_home",
        allow_venue_planning: days === 1 ? true : undefined,
        city: outingDays ? value.city : null,
        weather: "unknown",
        daylight: "unknown",
      });
      return;
    }
    setMinutes(String(availableMinutes));
    change(outingDays
      ? { ...value, available_minutes: availableMinutes, outing_days: undefined,
          city: null, allow_venue_planning: false, weather: "unknown", daylight: "unknown" }
      : { ...value, available_minutes: availableMinutes });
  };
  const advance = () => {
    if (
      step === 0 &&
      !outingDays &&
      (!/^\d+$/.test(digits(minutes)) ||
        +digits(minutes) < 5 ||
        +digits(minutes) > 480)
    ) {
      setError("وقت آزاد رو بین ۵ تا ۴۸۰ دقیقه بنویس.");
      return;
    }
    if (
      step === 1 &&
      value.social_mode !== "solo" &&
      (!/^\d+$/.test(digits(party)) ||
        +digits(party) < (value.social_mode === "together" ? 2 : 1) ||
        +digits(party) > 12)
    ) {
      setError("تعداد نفرها رو درست وارد کن؛حداکثر ۱۲ نفر.");
      return;
    }
    if (
      step === 2 &&
      value.budget.mode === "cap" &&
      (!/^\d+$/.test(digits(cap)) ||
        +digits(cap) < 1 ||
        +digits(cap) > 100000000)
    ) {
      setError("یه سقف هزینهٔ معتبر به تومان بنویس.");
      return;
    }
    if (outingDays && (step === 1 || step === stepLabels.length - 1)) {
      if (!value.allow_venue_planning || !origins?.some((city) => city === value.city)) {
        setStep(1);
        setError(!value.allow_venue_planning
          ? "برای ادامه، تمایلت به سفر رو مشخص کن یا مدت رو تغییر بده."
          : !origins
            ? "برای ادامه، اول باید فهرست شهرها دریافت بشه."
            : originRequired);
        return;
      }
    }
    if (step === 1 && !outingDays && value.venue !== "home" && value.allow_venue_planning && !value.city?.trim()) {
      setError("برای پیشنهاد جای مشخص، اسم شهرت رو وارد کن.");
      return;
    }
    setError("");
    if (step < stepLabels.length - 1) setStep(step + 1);
    else submit();
  };
  return (
    <div className="question-layout">
      <aside className="question-aside">
        <span className="eyebrow">وقتِ خودته</span>
        <h2>
          یه انتخاب کوچیک.
          <br />
          به اندازهٔ حالِ الانت.
        </h2>
        <p>
          از همین جایی که هستی شروع می‌کنیم. با همون وقت و انرژی‌ای که داری.
        </p>
        <ol className="flow-steps">
          {stepLabels.map((label, i) => (
            <li
              key={label}
              aria-current={i === step ? "step" : undefined}
              className={i < step ? "is-done" : ""}
            >
              <span>
                {i < step ? <Icon name="check" size={15} /> : number(i + 1)}
              </span>
              {label}
            </li>
          ))}
        </ol>
        <div className="aside-note">
          <Icon name="leaf" size={20} />
          <span>
            هیچ جوابی درست یا غلط نیست.
            <br />
            این چند دقیقه، با سلیقهٔ توئه.
          </span>
        </div>
      </aside>
      <fieldset className="question-column min-w-0" aria-labelledby="question-title" disabled={busy}>
        <div className="step-heading">
          <span>
            <Icon name="spark" size={17} />
            یه آشنایی کوتاه
          </span>
          <span>
            قدم {number(step + 1)} از {number(stepLabels.length)}
          </span>
        </div>
        <div
          className="step-progress"
          role="progressbar"
          aria-label="پیشرفت سؤال‌ها"
          aria-valuemin={0}
          aria-valuemax={stepLabels.length}
          aria-valuenow={step + 1}
          aria-valuetext={`قدم ${number(step + 1)} از ${number(stepLabels.length)}`}
        >
          <span
            style={{ width: `${((step + 1) / stepLabels.length) * 100}%` }}
          />
        </div>
        <h1 id="question-title" ref={heading} tabIndex={-1}>
          {stepTitles[step]}
        </h1>
        <p className="intro">{stepIntros[step]}</p>
        {step === 0 && (
          <>
            <Choices
              legend="چقدر وقت آزادی؟"
              value={outingDays || value.available_minutes <= 480 ? value.available_minutes : null}
              options={outings ? allDurations : shortDurations}
              onChange={selectDuration}
            />
            {!outingDays && <label className="label">
              یا به دقیقه بنویس
              <input
                inputMode="numeric"
                className="input number-input"
                value={minutes}
                onChange={(e) => {
                  setMinutes(e.target.value);
                  set("available_minutes", +digits(e.target.value));
                }}
              />
            </label>}
            <Choices
              legend="انرژیت چقدره؟"
              value={value.energy}
              options={[
                ["low", "یه کار سبک"],
                ["medium", "معمولی‌ام"],
                ["high", "انرژی دارم"],
                ["unknown", "مطمئن نیستم"],
              ]}
              onChange={(v) => set("energy", v)}
            />
          </>
        )}
        {step === 1 && (
          <>
            <Choices
              legend="تنهایی یا با هم؟"
              value={value.social_mode}
              options={[
                ["solo", "برای خودم"],
                ["together", "با همراه"],
                ["either", "فرقی نداره"],
              ]}
              onChange={(v) => {
                change({
                  ...value,
                  social_mode: v,
                  party_size:
                    v === "solo"
                      ? 1
                      : v === "together"
                        ? Math.max(2, value.party_size)
                        : value.party_size,
                });
                setParty(
                  v === "solo"
                    ? "1"
                    : v === "together"
                      ? String(Math.max(2, value.party_size))
                      : String(value.party_size),
                );
              }}
            />
            {value.social_mode !== "solo" && (
              <label className="label">
                با خودت چند نفر می‌شین؟
                <input
                  className="input number-input"
                  inputMode="numeric"
                  value={party}
                  onChange={(e) => {
                    setParty(e.target.value);
                    set("party_size", +digits(e.target.value));
                  }}
                />
                <span className="hint">
                  اگه فرقی نداره و کسی کنارت نیست،۱ رو انتخاب کن.
                </span>
              </label>
            )}
            <Choices
              legend="کجا می‌خوای باشی؟"
              value={value.venue}
              disabledValues={outingDays ? ["home", "any"] : undefined}
              hint={outingDays ? "گردش یک‌روزه و دوروزه فقط بیرون از خونه‌ست." : undefined}
              options={[
                ["home", "توی خونه"],
                ["away_from_home", "بیرون از خونه"],
                ["any", "هر جا شد"],
              ]}
              onChange={(venue) => {
                setError("");
                change(venue === "home"
                  ? { ...value, venue, allow_venue_planning: false, city: null, weather: "unknown", daylight: "unknown" }
                  : { ...value, venue });
              }}
            />
            {outingDays === 2 && (
              <>
                <Choices<"yes" | "no">
                  legend="دوست داری برای این دو روز از یکی از شهرهای پیشنهادی راه بیفتی؟"
                  value={value.allow_venue_planning === undefined ? null : value.allow_venue_planning ? "yes" : "no"}
                  options={[
                    ["yes", "آره، مبدأ رو انتخاب می‌کنم"],
                    ["no", "نه، این بار سفر نمی‌خوام"],
                  ]}
                  onChange={(answer) => {
                    setError("");
                    change({
                      ...value,
                      allow_venue_planning: answer === "yes",
                      city: answer === "yes" ? value.city : null,
                    });
                  }}
                />
                {value.allow_venue_planning === false && (
                  <button type="button" className="text-button" onClick={() => {
                    setError("");
                    setStep(0);
                  }}>
                    تغییر مدت
                  </button>
                )}
              </>
            )}
            {showOrigins && (
              outings?.unavailable ? (
                <div>
                  <p className="error" role="alert">فهرست شهرها دریافت نشد.</p>
                  <Button type="button" secondary onClick={outings.retry}>دریافت دوبارهٔ شهرها</Button>
                </div>
              ) : !origins ? (
                <p className="hint" role="status">در حال دریافت شهرها…</p>
              ) : (
                <label className="label">
                  از کدوم شهر راه می‌افتی؟
                  <select
                    className="input"
                    value={origins.some((city) => city === value.city) ? value.city ?? "" : ""}
                    aria-required="true"
                    aria-invalid={originInvalid}
                    aria-describedby={originInvalid ? `${originHintId} ${originErrorId}` : originHintId}
                    onChange={(event) => {
                      setError("");
                      set("city", event.target.value || null);
                    }}
                  >
                    <option value="" disabled>شهر مبدأ رو انتخاب کن</option>
                    {origins.map((city) => <option key={city} value={city}>{city}</option>)}
                  </select>
                  <span className="hint" id={originHintId}>ممکنه برنامه داخل شهر مبدأ یا در یک مقصد نزدیک باشه.</span>
                  {originInvalid && <span className="error" role="alert" id={originErrorId}>{error}</span>}
                </label>
              )
            )}
            {!outingDays && value.venue !== "home" && (
              <fieldset className="field">
                <legend>دوست داری یه جای مشخص هم پیشنهاد بدیم؟</legend>
                <label className="choice">
                  <input
                    type="checkbox"
                    checked={value.allow_venue_planning ?? false}
                    onChange={(e) => {
                      setError("");
                      change({
                        ...value,
                        allow_venue_planning: e.target.checked,
                        city: e.target.checked ? value.city : null,
                      });
                    }}
                  />
                  <span>آره، پیشنهاد جا هم می‌خوام</span>
                </label>
                {value.allow_venue_planning && (
                  <label className="label">
                    شهر برای همین نوبت
                    <input
                      className="input"
                      maxLength={100}
                      value={value.city ?? ""}
                      placeholder="مثلاً تهران"
                      onChange={(e) => {
                        setError("");
                        set("city", e.target.value);
                      }}
                    />
                  </label>
                )}
                <p className="hint">
                  {value.allow_venue_planning
                    ? "قبل از رفتن، باز بودن و هزینه رو با خود محل چک کن."
                    : "پیشنهاد برای جاییه که همین حالا امن و در دسترسته."}
                </p>
              </fieldset>
            )}
            {value.venue !== "home" && (
              <label className="choice">
                <input
                  type="checkbox"
                  checked={value.weather === "fair" && value.daylight === "day"}
                  onChange={(e) => change({
                    ...value,
                    weather: e.target.checked ? "fair" : "unknown",
                    daylight: e.target.checked ? "day" : "unknown",
                  })}
                />
                <span>{outingDays
                  ? "می‌تونم بازدیدها رو به روشنایی روز و هوای مناسب موکول کنم"
                  : "هوا روشنه و برای قدم‌زدن مناسبه"}</span>
              </label>
            )}
            {outingDays && (
              <p className="hint">اگه این شرایط رو نداری یا هنوز مطمئن نیستی، ممکنه پیشنهادی پیدا نشه. قبل از حرکت دوباره هوا رو بررسی کن.</p>
            )}
          </>
        )}
        {step === 2 && (
          <>
            <Choices
              legend="بودجه‌ات چقدره؟"
              value={value.budget.mode}
              options={[
                ["free", "رایگان باشه"],
                ["cap", "یه سقف دارم"],
                ["flexible", "منعطفم"],
              ]}
              onChange={(mode) =>
                set("budget", {
                  mode,
                  cap_toman: mode === "cap" ? +digits(cap) : null,
                })
              }
            />
            {outingDays ? (
              <p className="hint">
                هزینهٔ رفت‌وآمد، ورودی و اقامت رو قبل از حرکت بررسی کن. برای دیدن گردش‌های با هزینهٔ نامعلوم، بودجهٔ «منعطفم» رو انتخاب کن.
              </p>
            ) : value.allow_venue_planning && value.budget.mode !== "flexible" && (
              <p className="hint">
                جاهایی که هزینه‌شون مشخص نیست فقط با بودجهٔ منعطف پیشنهاد می‌شن.
              </p>
            )}
            {value.budget.mode === "cap" && (
              <label className="label">
                سقف هزینه برای همه، به تومان
                <input
                  className="input number-input"
                  inputMode="numeric"
                  value={cap}
                  onChange={(e) => {
                    setCap(e.target.value);
                    set("budget", {
                      mode: "cap",
                      cap_toman: +digits(e.target.value),
                    });
                  }}
                />
                <span className="hint">تا جای ممکن گزینه‌ای نزدیک به این مبلغ پیشنهاد می‌دیم.</span>
              </label>
            )}
            {!outingDays && <p className="hint">
              برای پیشنهادهای رایگان،خرید و رفت‌وآمد پولی لازم نیست.
            </p>}
          </>
        )}
        {step === 3 && (
          <>
            <Choices
              legend="یه گزینه رو انتخاب کن"
              value={value.activity_intent}
              options={activityIntentOptions}
              onChange={(v) => set("activity_intent", v)}
            />
            <details className="personalization">
              <summary>اگه دوست داری، سلیقه و وسایل رو هم بگو</summary>
              <p className="hint">
                اختیاری و فقط برای همین نوبته.
                {outings && " انتخاب‌های قبلی حساب هم اینجا در دسترسن."}
              </p>
              <Personalization
                items={value.owned_items ?? defaults?.owned_items ?? []}
                interests={value.liked_tags ?? defaults?.liked_tags ?? []}
                changeItems={(v) => set("owned_items", v)}
                changeInterests={(v) => set("liked_tags", v)}
              />
            </details>
          </>
        )}
        {error && !originInvalid && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {step === stepLabels.length - 1 && submitMessage && (
          <p role="alert" className="error">{submitMessage}</p>
        )}
        <div className="question-actions">
          <Button onClick={advance} disabled={busy}>
            {busy
              ? "داریم انتخاب می‌کنیم…"
              : step === stepLabels.length - 1
                ? "پیشنهادم رو ببینم"
                : "بریم بعدی"}{" "}
            <span aria-hidden="true">←</span>
          </Button>
          {step > 0 && (
            <button
              className="text-button"
              disabled={busy}
              onClick={() => {
                setStep(step - 1);
                setError("");
              }}
            >
              قدم قبلی
            </button>
          )}
        </div>
      </fieldset>
    </div>
  );
}
