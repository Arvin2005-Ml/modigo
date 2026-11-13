import {interestOptions, itemOptions} from '@/lib/personalization';

export default function Personalization({items, interests, changeItems, changeInterests}: {
  items: string[]; interests: string[];
  changeItems: (items: string[]) => void; changeInterests: (interests: string[]) => void;
}) {
  const groups = [
    {legend:'چی بیشتر بهت می‌چسبه؟', hint:'اختیاریه؛ می‌تونی چندتا انتخاب کنی.', options:interestOptions, values:interests, change:changeInterests},
    {legend:'چه چیزهایی همین حالا دم‌دستته؟', hint:'فقط چیزهایی که از قبل داری؛ هیچ وسیله‌ای رو خودکار فرض نمی‌کنیم.', options:itemOptions, values:items, change:changeItems},
  ];
  return <>{groups.map(group => <fieldset className="field" key={group.legend}>
    <legend>{group.legend}</legend><p className="hint">{group.hint}</p>
    <div className="choices">{group.options.map(([key,label]) => <label key={key} className="choice">
      <input type="checkbox" checked={group.values.includes(key)} onChange={e => group.change(e.target.checked ? [...group.values,key] : group.values.filter(v => v !== key))}/>
      <span>{label}</span>
    </label>)}</div>
  </fieldset>)}</>;
}
