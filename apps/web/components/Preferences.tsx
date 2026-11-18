import { useState } from "react";
import type { Preferences as PreferencesType } from "@/types";
import { Button, Choices } from "./ui";
import Personalization from "./Personalization";
import { goalOptions } from "@/lib/personalization";

export default function Preferences({
  initial,
  busy,
  save,
}: {
  initial: PreferencesType;
  busy: boolean;
  save: (v: PreferencesType) => void;
}) {
  const [value, setValue] = useState(initial);
  const p = value.preferences;
  const set = <K extends keyof typeof p>(key: K, v: (typeof p)[K]) =>
    setValue({ ...value, preferences: { ...p, [key]: v } });
  return (
    <section className="detail-column">
      <h1>چیزهایی که بهتره بدونیم</h1>
      <p className="intro">
        این انتخاب‌ها موقع هر پیشنهاد رعایت می‌شن.هر وقت خواستی می‌تونی عوضشون
        کنی.
      </p>
      <Choices
        legend="چقدر جابه‌جایی برات مناسبه؟"
        value={p.max_mobility}
        options={[
          ["seated", "نشسته"],
          ["light", "حرکت سبک"],
          ["active", "محدودیتی ندارم"],
        ]}
        onChange={(v) => set("max_mobility", v)}
      />
      <label className="check-label">
        <input
          type="checkbox"
          checked={p.requires_step_free}
          onChange={(e) => set("requires_step_free", e.target.checked)}
        />
        مسیر و فضای بدون پله می‌خوام.
      </label>
      <label className="check-label">
        <input
          type="checkbox"
          checked={p.requires_quiet}
          onChange={(e) => set("requires_quiet", e.target.checked)}
        />
        یه تجربهٔ ساکت می‌خوام.
      </label>
      <label className="check-label">
        <input
          type="checkbox"
          checked={p.allow_async_contact}
          onChange={(e) => set("allow_async_contact", e.target.checked)}
        />
        پیشنهاد تماس یا پیام‌دادن به آدم‌های آشنا هم می‌تونه باشه.
      </label>
      <Choices
        legend="معمولاً چه جور وقتی می‌خوای؟"
        value={p.default_goal}
        options={goalOptions}
        onChange={(v) => set("default_goal", v)}
      />
      <Personalization
        items={p.owned_items}
        interests={p.liked_tags}
        changeItems={(v) => set("owned_items", v)}
        changeInterests={(v) => set("liked_tags", v)}
      />
      <label className="check-label">
        <input
          type="checkbox"
          checked={p.show_gamification}
          onChange={(e) => set("show_gamification", e.target.checked)}
        />
        امتیاز و نشان‌های مسیرم رو ببینم.
      </label>
      <Button disabled={busy} onClick={() => save(value)}>
        {busy ? "داریم نگه می‌داریم…" : "انتخاب‌هام رو نگه دار"}
      </Button>
    </section>
  );
}
