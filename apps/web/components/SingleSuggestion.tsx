import type {Slate, Slot} from '@/lib/contracts';
import {number} from '@/lib/api';
import {ActivityCard} from './Activity';
import {Button, Empty} from './ui';

export default function SingleSuggestion({slate, busy, saved, open, save, replace, browse, changeConditions}: {
  slate: Slate; busy: boolean; saved: boolean;
  open: (item: Slot) => void; save: (item: Slot) => void; replace: (item: Slot) => void;
  browse: (direction: 'previous' | 'next') => void;
  changeConditions: () => void;
}) {
  const item = slate.items[0];
  const hasPrevious = slate.suggestion_index > 0;
  const hasNext = slate.suggestion_index < slate.suggestion_count - 1;
  if(!item) return <Empty title="با این شرایط فعلاً چیزی پیدا نکردیم.">
    <p>اگه دوست داشتی یه انتخاب رو تغییر بده تا دوباره بگردیم. برای کارهای عملی، وسایل موجودت رو هم در سؤال آخر مشخص کن؛ برای مکان‌های شهری، شهر و اجازهٔ بررسی محل لازمه.</p>
    <Button onClick={changeConditions}>برگردم به سؤال‌ها</Button>
  </Empty>;
  return <div className="single-suggestion">
    <ActivityCard key={item.revision_id ?? item.slot_id} item={item} index={0} busy={busy} saved={saved} open={() => open(item)} save={() => save(item)}/>
    {slate.suggestion_count > 1 && <nav className="suggestion-history" aria-label="مرور پیشنهادهای دیده‌شده">
      <Button secondary disabled={busy || !hasPrevious} onClick={() => browse('previous')}>پیشنهاد قبلی</Button>
      <span role="status" aria-live="polite">پیشنهاد {number(slate.suggestion_index + 1)} از {number(slate.suggestion_count)}</span>
      <Button secondary disabled={busy || !hasNext} onClick={() => browse('next')}>پیشنهاد بعدی</Button>
    </nav>}
    <div className="suggestion-replacement">
      <p role="status" aria-live="polite">{hasNext
        ? 'این پیشنهاد رو قبلاً دیدی. مرور پیشنهادهای قبلی سهمیهٔ تعویضت رو کم نمی‌کنه.'
        : slate.replacements_remaining === 0
        ? 'شش بار پیشنهاد رو عوض کردی. می‌تونی از بین پیشنهادهای دیده‌شده انتخاب کنی یا شرایط تازه‌ای بگی.'
        : slate.replacement_available
          ? `${number(slate.replacements_remaining)} بار دیگه می‌تونی پیشنهاد رو عوض کنی.`
          : 'فعلاً پیشنهاد تازه‌ای با همین شرایط نداریم. برای این تلاش، سهمیهٔ تعویض کم نمی‌شه.'}</p>
      {!hasNext && <Button secondary disabled={busy || !slate.replacement_available || slate.replacements_remaining === 0} onClick={() => replace(item)}>
        {busy ? 'یه لحظه…' : 'یه پیشنهاد دیگه'}
      </Button>}
    </div>
  </div>;
}
