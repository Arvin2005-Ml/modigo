import type { Content, Slot } from "@/types";
import { number } from "@/lib/api";
import { Button } from "./ui";
import Icon from "./Icon";

export function ActivityCard({
  item,
  busy,
  saved,
  open,
  save,
}: {
  item: Slot;
  busy: boolean;
  saved: boolean;
  open: () => void;
  save: () => void;
}) {
  if (item.unavailable) {
    return (
      <article className="activity-card">
        <p className="muted">این پیشنهاد فعلاً در دسترس نیست.</p>
      </article>
    );
  }

  return (
    <article className="activity-card">
      <div className="card-top">
        <span className="card-symbol symbol-0">
          <Icon name="leaf" size={25} />
        </span>

        <span className="card-meta">
          <Icon name="clock" size={14} />
          {number(item.total_minutes!)} دقیقه · {item.cost_label}
        </span>
      </div>

      <h2>
        <button className="title-button" onClick={open} disabled={busy}>
          {item.title}
        </button>
      </h2>

      <p className="teaser">{item.teaser}</p>
      <p className="explanation">{item.explanation}</p>

      <div className="card-actions">
        <Button secondary onClick={open} disabled={busy}>
          ببینمش
          <Icon name="arrow" size={18} />
        </Button>

        <div className="minor-actions">
          <button
            className="icon-button"
            title={saved ? "حذف از ذخیره‌ها" : "ذخیره برای بعد"}
            aria-label={
              saved
                ? "حذف از ذخیره‌ها: " + item.title
                : "ذخیره برای بعد: " + item.title
            }
            aria-pressed={saved}
            disabled={busy}
            onClick={save}
          >
            <Bookmark filled={saved} />
          </button>
        </div>
      </div>
    </article>
  );
}
function Bookmark({ filled }: { filled: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <path d="M6 4h12v17l-6-4-6 4z" />
    </svg>
  );
}

export function ContentDetails({
  content,
  children,
}: {
  content: Content;
  children?: React.ReactNode;
}) {
  const total =
    content.active_minutes + content.setup_minutes + content.travel_minutes;
  return (
    <>
      <span className="eyebrow">یه تجربهٔ کوچیک،با ریتم خودت</span>
      <h1>{content.title}</h1>
      <p className="intro">{content.teaser}</p>
      <div className="detail-meta">
        <span>{number(total)} دقیقه با آماده‌سازی</span>
        <span>{content.cost.kind === "free" ? "رایگان" : "هزینهٔ متغیر"}</span>
      </div>
      <div className="first-step">
        <span className="eyebrow">از اینجا شروع کن</span>
        <p>{content.first_step}</p>
      </div>
      <ol className="steps">
        {content.steps.map((step, i) => (
          <li key={i}>
            <span aria-hidden="true">{number(i + 1)}</span>
            <p>{step}</p>
          </li>
        ))}
      </ol>
      <div className="lighter">
        <h2>اگه یه نسخهٔ سبک‌تر بخوای</h2>
        <p>{content.lighter_version}</p>
      </div>
      <details className="practical">
        <summary>وسایل و شرایطش رو بدونم</summary>
        <dl>
          <dt>وسایل</dt>
          <dd>{content.materials_note}</dd>
          <dt>دسترسی</dt>
          <dd>{content.accessibility_note}</dd>
          <dt>شرایط</dt>
          <dd>{content.conditions_note}</dd>
          <dt>هزینه</dt>
          <dd>{content.cost.note}</dd>
        </dl>
        {content.safety_notes.map((s, i) => (
          <p key={i}>{s}</p>
        ))}
      </details>
      {children}
    </>
  );
}
