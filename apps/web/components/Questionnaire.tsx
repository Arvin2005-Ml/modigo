import {useEffect, useRef, useState} from 'react';
import type {Context} from '@/lib/contracts';
import {digits, number} from '@/lib/api';
import {Button, Choices} from './ui';
import Icon from './Icon';
import Personalization from './Personalization';
import {needNowOptions, outcomeOptions} from '@/lib/personalization';

export const initialContext: Context = {available_minutes: 30, energy: 'low', social_mode: 'solo', party_size: 1,
  venue: 'home', budget: {mode: 'free', cap_toman: null}, mood: 'skip', need_now:'any', desired_outcome:'any'};

const stepLabels = ['وقت و انرژی','همراه و محیط','هزینهٔ دلخواه','حال‌وهوای الان','نیاز همین لحظه','از این وقت چی می‌خوای'];
const stepTitles = ['الان چقدر وقت و انرژی داری؟','چه‌جوری بهت می‌چسبه؟','چقدر دوست داری خرج کنی؟','الان حالت چطوره؟','الان بیشتر چی کم داری؟','دوست داری از این وقت چی با خودت ببری؟'];
const stepIntros = ['همون‌قدر که هست؛لازم نیست بیشترش کنی.','شرایط واقعی الانت رو بگو تا انتخاب به کارت بیاد.','بی‌خرج‌بودن هم یه انتخاب خوبه.','جواب درست و غلطی نداره؛ردکردنش هم آزاده.','هر کدوم به همین لحظه نزدیک‌تره؛ مطمئن‌نبودن هم یه جوابه.','با این جواب، اولین پیشنهاد رو به خواستهٔ الانت نزدیک‌تر می‌کنیم.'];

export default function Questionnaire({value, change, submit, busy, defaults}: {
  value: Context; change: (v: Context) => void; submit: () => void; busy: boolean;
  defaults?: {owned_items: string[]; liked_tags: string[]; default_goal: NonNullable<Context['goal']>};
}) {
  const [step, setStep] = useState(0);
  const [minutes, setMinutes] = useState(String(value.available_minutes));
  const [cap, setCap] = useState(value.budget.cap_toman ? String(value.budget.cap_toman) : '');
  const [party, setParty] = useState(String(value.party_size));
  const [error, setError] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {heading.current?.focus({preventScroll:true});}, [step]);
  const set = <K extends keyof Context>(key: K, next: Context[K]) => change({...value, [key]: next});
  const advance = () => {
    if (step === 0 && (!/^\d+$/.test(digits(minutes)) || +digits(minutes) < 5 || +digits(minutes) > 480)) {setError('وقت آزاد رو بین ۵ تا ۴۸۰ دقیقه بنویس.'); return;}
    if (step === 1 && value.social_mode !== 'solo' && (!/^\d+$/.test(digits(party)) || +digits(party) < (value.social_mode === 'together' ? 2 : 1) || +digits(party) > 12)) {setError('تعداد نفرها رو درست وارد کن؛حداکثر ۱۲ نفر.'); return;}
    if (step === 2 && value.budget.mode === 'cap' && (!/^\d+$/.test(digits(cap)) || +digits(cap) < 1 || +digits(cap) > 100000000)) {setError('یه سقف هزینهٔ معتبر به تومان بنویس.');return;}
    setError('');
    if (step < stepLabels.length - 1) setStep(step + 1); else submit();
  };
  return <div className="question-layout"><aside className="question-aside"><span className="eyebrow">وقتِ خودته</span><h2>یه انتخاب کوچیک.<br/>به اندازهٔ حالِ الانت.</h2><p>از همین جایی که هستی شروع می‌کنیم. با همون وقت و انرژی‌ای که داری.</p><ol className="flow-steps">{stepLabels.map((label,i)=><li key={label} aria-current={i === step ? 'step' : undefined} className={i < step ? 'is-done' : ''}><span>{i < step ? <Icon name="check" size={15}/> : number(i+1)}</span>{label}</li>)}</ol><div className="aside-note"><Icon name="leaf" size={20}/><span>هیچ جوابی درست یا غلط نیست.<br/>این چند دقیقه، با سلیقهٔ توئه.</span></div></aside><section className="question-column" aria-labelledby="question-title">
    <div className="step-heading"><span><Icon name="spark" size={17}/>یه آشنایی کوتاه</span><span>قدم {number(step + 1)} از {number(stepLabels.length)}</span></div>
    <div className="step-progress" role="progressbar" aria-label="پیشرفت سؤال‌ها" aria-valuemin={0} aria-valuemax={stepLabels.length} aria-valuenow={step+1} aria-valuetext={`قدم ${number(step+1)} از ${number(stepLabels.length)}`}><span style={{width: `${(step + 1) / stepLabels.length * 100}%`}} /></div>
    <h1 id="question-title" ref={heading} tabIndex={-1}>{stepTitles[step]}</h1>
    <p className="intro">{stepIntros[step]}</p>
    {step === 0 && <>
      <Choices legend="چقدر وقت آزادی؟" value={value.available_minutes} options={[[15,'یه ربع'],[30,'نیم ساعت'],[60,'یه ساعت'],[120,'دو ساعت']]} onChange={v => {set('available_minutes',v);setMinutes(String(v));}} />
      <label className="label">یا خودت بنویس،به دقیقه<input inputMode="numeric" className="input number-input" value={minutes} onChange={e => {setMinutes(e.target.value);set('available_minutes',+digits(e.target.value));}} /></label>
      <Choices legend="انرژیت چقدره؟" value={value.energy} options={[["low","یه کار سبک"],["medium","معمولی‌ام"],["high","انرژی دارم"],["unknown","مطمئن نیستم"]]} onChange={v => set('energy',v)} />
    </>}
    {step === 1 && <>
      <Choices legend="تنهایی یا با هم؟" value={value.social_mode} options={[["solo","برای خودم"],["together","با همراه"],["either","فرقی نداره"]]} onChange={v => {change({...value,social_mode:v,party_size:v === 'solo' ? 1 : v === 'together' ? Math.max(2,value.party_size) : value.party_size});setParty(v === 'solo' ? '1' : v === 'together' ? String(Math.max(2,value.party_size)) : String(value.party_size));}} />
      {value.social_mode !== 'solo' && <label className="label">با خودت چند نفر می‌شین؟<input className="input number-input" inputMode="numeric" value={party} onChange={e => {setParty(e.target.value);set('party_size',+digits(e.target.value));}} /><span className="hint">اگه فرقی نداره و کسی کنارت نیست،۱ رو انتخاب کن.</span></label>}
      <Choices legend="کجا می‌خوای باشی؟" value={value.venue} options={[["home","توی خونه"],["outdoor","هوای آزاد"],["indoor_public","یه جای سرپوشیده"],["any","هر جا شد"]]} onChange={v => set('venue',v)} />
      {value.venue !== 'home' && <p className="hint">پیشنهادهای بیرون برای جایی‌ان که همین حالا بهش دسترسی امن و مجاز داری؛ مسیر، بلیت یا محل تازه‌ای رو حدس نمی‌زنیم.</p>}
    </>}
    {step === 2 && <>
      <Choices legend="بودجه‌ات چقدره؟" value={value.budget.mode} options={[["free","رایگان باشه"],["cap","یه سقف دارم"],["flexible","منعطفم"]]} onChange={mode => set('budget',{mode,cap_toman:mode === 'cap' ? +digits(cap) : null})} />
      {value.budget.mode === 'cap' && <label className="label">سقف هزینه برای همه،تومان<input className="input number-input" inputMode="numeric" value={cap} onChange={e => {setCap(e.target.value);set('budget',{mode:'cap',cap_toman:+digits(e.target.value)});}} /></label>}
      <p className="hint">برای پیشنهادهای رایگان،خرید و رفت‌وآمد پولی لازم نیست.</p>
    </>}
    {step === 3 && <>
      <Choices legend="کدوم به حالت نزدیک‌تره؟" value={value.mood} options={[["tired","خسته‌ام"],["restless","ذهنم شلوغه"],["bored","حوصله‌ام سر رفته"],["low","یه کم بی‌حالم"],["okay","خوبم"],["skip","نمی‌خوام بگم"]]} onChange={v => set('mood',v)} />
      <p className="soft-note">یه پیشنهاد کوچیک برای همین حال‌وهوا پیدا می‌کنیم؛هر وقت نچسبید،انتخابش با توئه.</p>
    </>}
    {step === 4 && <Choices legend="کدوم به نیاز الانت نزدیک‌تره؟" value={value.need_now ?? 'any'} options={needNowOptions} onChange={v => set('need_now',v)} />}
    {step === 5 && <>
      <Choices legend="دوست داری آخرش چی بهت چسبیده باشه؟" value={value.desired_outcome ?? 'any'} options={outcomeOptions} onChange={v => set('desired_outcome',v)} />
      <details className="personalization"><summary>اگه دوست داری، سلیقه و وسایل رو هم بگو</summary>
        <p className="hint">اختیاری و فقط برای همین نوبته؛ انتخاب‌های قبلی حساب هم اینجا در دسترسن.</p>
        <Personalization items={value.owned_items ?? defaults?.owned_items ?? []} interests={value.liked_tags ?? defaults?.liked_tags ?? []}
          changeItems={v => set('owned_items',v)} changeInterests={v => set('liked_tags',v)} />
        {value.venue !== 'home' && <>
          <Choices legend="هوای جایی که هستی مناسبه؟" value={value.weather ?? 'unknown'} options={[["unknown","مطمئن نیستم"],["fair","برای بیرون مناسبه"],["adverse","نامساعده"]]} onChange={v => set('weather',v)} />
          <Choices legend="الان روشنایی روز داری؟" value={value.daylight ?? 'unknown'} options={[["unknown","مطمئن نیستم"],["day","روزه"],["night","شبه"]]} onChange={v => set('daylight',v)} />
        </>}
      </details>
    </>}
    {error && <p role="alert" className="error">{error}</p>}
    <div className="question-actions"><Button onClick={advance} disabled={busy}>{busy ? 'داریم انتخاب می‌کنیم…' : step === stepLabels.length - 1 ? 'پیشنهادم رو ببینم' : 'بریم بعدی'} <span aria-hidden="true">←</span></Button>{step > 0 && <button className="text-button" disabled={busy} onClick={() => {setStep(step-1);setError('');}}>قدم قبلی</button>}</div>
  </section></div>;
}
