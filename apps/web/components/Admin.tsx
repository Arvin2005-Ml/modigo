import {useCallback, useEffect, useState} from 'react';
import type {Content, User} from '@/lib/contracts';
import {api, number} from '@/lib/api';
import {Button} from './ui';

type Draft = {id: string; revision_number: number; draft_version: number; state: string; content: Content | null; origin: string};
type Activity = {id: string; raw_title: string; seed_key: string; primary_dimension: string; active: boolean; withdrawn?: boolean; revisions?: Draft[]};
type Job = {id:string; activity_id:string; state:string; provider:string; error_code:string|null};
type Listing = {items: Activity[]; total: number; next_offset: number | null};
const states: Record<string,string> = {draft:'پیش‌نویس',review:'منتظر بررسی',published:'منتشرشده',superseded:'نسخهٔ پیشین',archived:'کنارگذاشته‌شده',rejected:'برگشت‌خورده'};
const dimensions: Record<string,string> = {detachment:'فاصله از روزمرگی',relaxation:'آرامش',autonomy:'انتخاب آزاد',mastery:'یادگیری',meaning:'معنا',affiliation:'ارتباط'};

export default function Admin({user, report}: {user: User; report: (error: unknown) => void}) {
  const [list,setList] = useState<Listing|null>(null);
  const [offset,setOffset] = useState(0);
  const [filter,setFilter] = useState('draft');
  const [selected,setSelected] = useState<Activity|null>(null);
  const [draft,setDraft] = useState<Draft|null>(null);
  const [source,setSource] = useState('');
  const [busy,setBusy] = useState(false);
  const [message,setMessage] = useState('');
  const [job,setJob] = useState<Job|null>(null);
  const [reason,setReason] = useState('');
  const load = useCallback(async () => {
    setList(await api<Listing>(`/admin/activities?limit=20&offset=${offset}${filter ? '&state='+filter : ''}`));
  },[offset,filter]);
  useEffect(() => {load().catch(report);},[load,report]);
  useEffect(() => {
    if (!job || !['queued','running'].includes(job.state)) return;
    const timer = setInterval(() => {api<Job>('/admin/jobs/'+job.id).then(setJob).catch(report);}, 2000);
    return () => clearInterval(timer);
  },[job,report]);
  const open = async (id: string) => {
    const a = await api<Activity>('/admin/activities/'+id);
    setSelected(a);setDraft(a.revisions![0]);setSource(JSON.stringify(a.revisions![0].content,null,2));setMessage('');setReason('');
  };
  const perform = async (action: () => Promise<void>) => {setBusy(true);setMessage('');try {await action();} catch(e) {report(e);} finally {setBusy(false);}};
  const action = (name: string) => perform(async () => {
    if(!draft || !selected) return;
    await api(`/admin/revisions/${draft.id}/${name}`,'POST',{expected_draft_version:draft.draft_version});
    await open(selected.id);await load();setMessage(name === 'publish' ? 'نسخه منتشر شد.' : 'برای بررسی ثبت شد.');
  });
  return <section className="admin-layout"><aside className="admin-sidebar"><span className="eyebrow">کارگاه محتوا</span><h1>از ایده تا یه تجربه</h1><p className="muted">۴۵۰ بذر،هنوز محتوای آمادهٔ نمایش نیستن.نمونه‌های نمایشی هم تأیید انتشار عمومی ندارن.</p>
    <label className="label">وضعیت<select className="input" value={filter} onChange={e => {setFilter(e.target.value);setOffset(0);}}><option value="">همه</option>{Object.entries(states).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    {list && <p className="hint">{number(list.total)} فعالیت در این فهرست</p>}
    <div className="admin-items">{list?.items.map(a => <button key={a.id} aria-pressed={selected?.id === a.id} className="admin-row" onClick={() => perform(() => open(a.id))}><span>{a.raw_title}</span><small>{dimensions[a.primary_dimension]}</small></button>)}</div>
    <div className="inline-actions"><Button secondary disabled={busy || offset === 0} onClick={() => setOffset(Math.max(0,offset-20))}>قبلی</Button><Button secondary disabled={busy || !list?.next_offset} onClick={() => setOffset(list!.next_offset!)}>بعدی</Button></div>
  </aside><div className="admin-editor">
    {selected && draft ? <><span className="eyebrow">{states[draft.state]} · نسخهٔ {number(draft.revision_number)}</span><h2>{selected.raw_title}</h2><p className="hint">منبع: <bdi>{selected.seed_key}</bdi> · {draft.origin === 'demo' ? 'نمونهٔ نمایشی؛ تولید مدل نیست' : draft.origin === 'ai' ? 'پیش‌نویس تولید مدل؛ نیازمند بازبینی' : 'ویرایش انسانی'}</p>
      <label className="label">نسخه<select className="input" value={draft.id} onChange={e => {const r=selected.revisions!.find(r => r.id === e.target.value)!;setDraft(r);setSource(JSON.stringify(r.content,null,2));}}>{selected.revisions!.map(r => <option key={r.id} value={r.id}>{number(r.revision_number)} · {states[r.state]}</option>)}</select></label>
      {draft.content && <div className="admin-preview"><span className="eyebrow">پیش‌نمایش کارت</span><h3>{draft.content.title}</h3><p>{draft.content.teaser}</p><p>{draft.content.first_step}</p></div>}
      {!draft.content && <p className="soft-note">این بذر هنوز پخته نشده.محتوای کامل قرارداد را در ویرایشگر وارد کن؛بدون محتوای معتبر قابل ارسال به بررسی نیست.</p>}
      {['draft','rejected'].includes(draft.state) && <div className="soft-note"><p>می‌تونی برای این بذر پیش‌نویس آماده کنی؛ پیش از انتشار حتماً بررسی انسان لازمه.</p><Button secondary disabled={busy || !!(job && job.activity_id === selected.id && ['queued','running'].includes(job.state))} onClick={() => perform(async () => {setJob(await api<Job>(`/admin/activities/${selected.id}/cook`,'POST',{target_draft_id:draft.id,expected_draft_version:draft.draft_version,prompt_version:'cook_v1',editor_constraints:''}));})}>آماده‌کردن پیش‌نویس</Button>
      {job?.activity_id === selected.id && <div role="status"><p>{job.provider === 'demo' ? 'نمونهٔ محلی؛ تولید مدل نیست. ' : 'درخواست تولید محتوا. '}{({queued:'در صف',running:'در حال آماده‌سازی',succeeded:'آماده برای بازبینی',failed:job.error_code === 'DEMO_FIXTURE_UNAVAILABLE' ? 'برای این بذر نمونهٔ محلی نداریم.' : job.error_code === 'STALE_DRAFT' ? 'پیش‌نویس تغییر کرده؛ خروجی ذخیره نشد.' : 'آماده‌سازی انجام نشد؛ تنظیمات یا محتوای بذر را بررسی کن.',cancelled:'لغو شد'} as Record<string,string>)[job.state]}</p>
      {['queued','running'].includes(job.state) && <Button secondary disabled={busy} onClick={() => perform(async () => setJob(await api<Job>('/admin/jobs/'+job.id+'/cancel','POST',{})))}>لغو</Button>}
      {job.state === 'succeeded' && <Button secondary disabled={busy} onClick={() => perform(() => open(selected.id))}>بارگذاری پیش‌نویس آماده</Button>}</div>}</div>}
      <label className="label" htmlFor="content-json">محتوای کامل و شرایط اجرا</label><p id="json-hint" className="hint">ویرایشگر موقت برای اپراتور فنی؛فیلدها طبق قرارداد محتوا هستند.متن‌ها فارسی و شناسه‌های فنی انگلیسی بمانند.</p>
      <textarea id="content-json" aria-describedby="json-hint" className="input json-editor" dir="ltr" value={source} readOnly={!['draft','rejected'].includes(draft.state)} onChange={e => setSource(e.target.value)} spellCheck={false} />
      <div className="inline-actions wrap">
        {['draft','rejected'].includes(draft.state) && <><Button disabled={busy} onClick={() => perform(async () => {let content: unknown;try {content=JSON.parse(source);} catch {throw new Error('ساختار JSON درست نیست.');} const r=await api<Draft>(`/admin/revisions/${draft.id}`,'PATCH',{expected_draft_version:draft.draft_version,content});setDraft(r);setSource(JSON.stringify(r.content,null,2));setMessage('پیش‌نویس نگه داشته شد.');})}>ذخیرهٔ ویرایش</Button><Button secondary disabled={busy || !draft.content} onClick={() => action('submit')}>ارسال برای بررسی</Button></>}
        {draft.state === 'review' && user.role === 'admin' && <Button disabled={busy} onClick={() => action('publish')}>بررسی کردم؛منتشر کن</Button>}
        <Button secondary disabled={busy} onClick={() => perform(async () => {await api(`/admin/activities/${selected.id}/revisions`,'POST',{source_revision_id:draft.id});await open(selected.id);})}>ساخت نسخهٔ تازه</Button>
        {user.role === 'admin' && (selected.active || selected.withdrawn) && <><label className="label">دلیل تغییر وضعیت<input className="input" value={reason} onChange={e => setReason(e.target.value)} minLength={5} maxLength={240} /></label>{selected.active ? <Button secondary disabled={busy || reason.trim().length < 5} onClick={() => perform(async () => {await api(`/admin/activities/${selected.id}/withdraw`,'POST',{reason});await open(selected.id);await load();setMessage('محتوا از نمایش و شروع کنار گذاشته شد.');})}>کنارگذاشتن از نمایش</Button> : <Button secondary disabled={busy || reason.trim().length < 5 || draft.state !== 'published'} onClick={() => perform(async () => {await api(`/admin/activities/${selected.id}/reactivate`,'POST',{reason});await open(selected.id);await load();setMessage('محتوا دوباره فعال شد.');})}>فعال‌کردن نسخهٔ بازبینی‌شده</Button>}</>}
      </div><p role="status" className="success">{message}</p>
    </> : <div className="empty-state"><h2>یه بذر انتخاب کن</h2><p className="muted">عنوان خام،نسخه‌ها و وضعیت انتشارش رو اینجا می‌بینی.</p></div>}
  </div></section>;
}
