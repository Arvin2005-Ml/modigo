import { useState } from "react";

import { number } from "@/lib/api";
import type { Revision } from "@/types";
import { Button } from "./ui";

type Props = {
  content: Revision["content"];
  options: NonNullable<Revision["catalog_start"]>;
  busy: boolean;
  onStart: (partySize: number, confirmed: boolean) => void;
};

export default function CatalogStart({ content, options, busy, onStart }: Props) {
  const [partySize, setPartySize] = useState(options.min_people);
  const [confirmed, setConfirmed] = useState(false);
  const { min_people: minPeople, max_people: maxPeople, checks } = options;
  const reminders = {
    venue: content.place
      ? `مقصد: ${content.place.name}، ${content.place.city}. باز بودن و امکان دسترسی رو بررسی کن.`
      : "امکان دسترسی به محل و شرایط اجرا رو بررسی کن.",
    cost: `هزینهٔ فعلی رو بررسی کن. ${content.cost.note}`,
    materials: `وسایل: ${content.materials_note}`,
    weather: "هوا برای انجام فعالیت مناسب باشه.",
    daylight: "فعالیت به روشنایی روز نیاز داره.",
    contact: "این فعالیت به تماس یا پیام دادن نیاز داره.",
  };

  return (
    <form
      className="catalog-start"
      onSubmit={(event) => {
        event.preventDefault();
        if (!busy && (!checks.length || confirmed)) onStart(partySize, confirmed);
      }}
    >
      {maxPeople > 1 && (
        <label>
          تعداد نفرات، با خودت
          <select
            value={partySize}
            onChange={(event) => setPartySize(Number(event.target.value))}
            disabled={busy}
          >
            {Array.from({ length: maxPeople - minPeople + 1 }, (_, index) => {
              const size = minPeople + index;
              return <option key={size} value={size}>{size === 1 ? "تنهایی" : `${number(size)} نفر`}</option>;
            })}
          </select>
        </label>
      )}
      {checks.length > 0 && (
        <div className="soft-note">
          <ul>
            {checks.map((check) => <li key={check}>{reminders[check]}</li>)}
          </ul>
          <label>
            <input
              type="checkbox"
              checked={confirmed}
              disabled={busy}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            شرایط بالا رو بررسی کردم و برای شروع آماده‌ام.
          </label>
        </div>
      )}
      <Button className="w-full" type="submit" disabled={busy || (checks.length > 0 && !confirmed)}>
        {busy ? "یه لحظه…" : "همین رو شروع می‌کنم"}
      </Button>
    </form>
  );
}
