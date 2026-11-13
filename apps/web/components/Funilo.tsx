'use client';

import {useCallback, useEffect, useRef, useState} from 'react';
import {api, ApiError, badgeNames, number, refreshCsrf} from '@/lib/api';
import type {User, Context, Slate, Slot, Revision, Experience, Award, Journey, Saved, ReplacementState, Preferences as PreferencesType} from '@/lib/contracts';
import Questionnaire, {initialContext} from './Questionnaire';
import Auth from './Auth';
import Admin from './Admin';
import Preferences from './Preferences';
import {ContentDetails} from './Activity';
import SingleSuggestion from './SingleSuggestion';
import {Button, Empty, Note} from './ui';
import Home from './Home';
import Icon from './Icon';
import Pwa from './Pwa';

type View = 'home'|'auth'|'questions'|'results'|'detail'|'active'|'complete'|'saved'|'journey'|'settings'|'admin';
const dimensionNames: Record<string,string> = {detachment:'فاصله از روزمرگی',relaxation:'یه مکث آروم',autonomy:'به سلیقهٔ خودت',mastery:'یه چیز تازه',meaning:'یه لحظهٔ باارزش',affiliation:'کنار هم'};

export default function Funilo() {
  const [view,setView] = useState<View>('home');
  const [boot,setBoot] = useState(true);
  const [user,setUser] = useState<User|null>(null);
  const [context,setContext] = useState<Context>(initialContext);
  const [slate,setSlate] = useState<Slate|null>(null);
  const [detail,setDetail] = useState<Revision|null>(null);
  const [slot,setSlot] = useState<Slot|null>(null);
  const [experience,setExperience] = useState<Experience|null>(null);
  const [award,setAward] = useState<Award|null>(null);
  const [journey,setJourney] = useState<Journey|null>(null);
  const [history,setHistory] = useState<Experience[]>([]);
  const [saved,setSaved] = useState<Saved[]>([]);
  const [preferences,setPreferences] = useState<PreferencesType|null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const [feedbackDone,setFeedbackDone] = useState(false);
  const [resetToken,setResetToken] = useState<string|null>(null);
  const returnView = useRef<View>('questions');
  const main = useRef<HTMLElement>(null);
  const lock = useRef(false);
  const checkIn = useRef<{fingerprint: string; id: string}|null>(null);
  const initialized = useRef(false);

  const navigate = useCallback((next: View) => {
    setView(next);setError('');setNotice('');
    const query = next === 'results' && slate ? '?slate='+slate.id : next === 'active' && experience ? '?experience='+experience.id : '';
    window.history.replaceState(null,'','/'+query);
  },[slate,experience]);
  const report = useCallback((e: unknown) => {
    setError(e instanceof Error ? e.message : 'یه مشکلی پیش اومد؛دوباره امتحان کن.');
    if(e instanceof ApiError && e.status === 401) {setUser(null);setView('auth');}
  },[]);
  const run = useCallback(async (work: () => Promise<void>) => {
    if(lock.current) return;
    lock.current = true;setBusy(true);setError('');setNotice('');
    try {await work();} catch(e) {report(e);} finally {lock.current=false;setBusy(false);}
  },[report]);

  useEffect(() => {
    if(initialized.current) return;
    initialized.current = true;
    (async () => {
      try {
        await refreshCsrf();
        const reset = new URLSearchParams(window.location.search).get('reset_password');
        if(reset) {setResetToken(reset);setView('auth');window.history.replaceState(null,'','/');return;}
        if(new URLSearchParams(window.location.search).has('verify_email')) window.history.replaceState(null,'','/');
        let current: User;
        try {current=await api<User>('/me');} catch(e) {if(e instanceof ApiError && e.status === 401) return;throw e;}
        setUser(current);
        const [active,prefs,saves] = await Promise.all([api<{experience: Experience|null}>('/experiences/active'),api<PreferencesType>('/me/preferences'),api<{items: Saved[]}>('/saved')]);
        setPreferences(prefs);setSaved(saves.items);
        const slateId = new URLSearchParams(window.location.search).get('slate');
        if(active.experience) {setExperience(active.experience);setView('active');}
        else if(slateId) {setSlate(await api<Slate>('/recommendation-sessions/'+slateId));setView('results');}
        else setView('questions');
      } catch(e) {report(e);} finally {setBoot(false);}
    })();
  },[report]);
  useEffect(() => {
    const heading = main.current?.querySelector('h1');
    if(heading) {heading.setAttribute('tabindex','-1');heading.focus({preventScroll:true});}
    window.scrollTo({top:0,behavior:'instant'});
  },[view]);

  const loadSaved = async () => setSaved((await api<{items: Saved[]}>('/saved')).items);
  const finishLogin = async (email: string,password: string) => {
    const response = await api<{user: User}>('/auth/login','POST',{email,password});
    setUser(response.user);
    const [active,prefs] = await Promise.all([api<{experience: Experience|null}>('/experiences/active'),api<PreferencesType>('/me/preferences')]);
    setExperience(active.experience);setPreferences(prefs);await loadSaved();
    navigate(active.experience ? 'active' : returnView.current);
  };
  const login = (email: string,password: string) => run(() => finishLogin(email,password));
  const recommend = () => run(async () => {
    const fingerprint = JSON.stringify(context);
    if(!checkIn.current || checkIn.current.fingerprint !== fingerprint) {
      const check = await api<{id: string}>('/check-ins','POST',context);
      checkIn.current = {fingerprint,id:check.id};
    }
    const result = await api<Slate>('/recommendation-sessions','POST',{check_in_id:checkIn.current.id});
    setSlate(result);setView('results');window.history.replaceState(null,'','/?slate='+result.id);
  });
  const open = (item: Slot) => run(async () => {
    setDetail(await api<Revision>('/activity-revisions/'+item.revision_id));setSlot(item);navigate('detail');
  });
  const replace = (item: Slot) => run(async () => {
    let result: ReplacementState & {session_version: number; item: Slot; replaced: boolean};
    try {
      result = await api(`/recommendation-sessions/${slate!.id}/slots/${item.slot_id}/replace`,'POST',{expected_version:slate!.version});
    } catch(e) {
      if(e instanceof ApiError && ['VERSION_CONFLICT','REPLACEMENT_LIMIT','HISTORY_NOT_AT_END'].includes(e.code)) {
        setSlate(await api<Slate>('/recommendation-sessions/'+slate!.id));
      }
      throw e;
    }
    const items=slate!.items.map(i => i.slot_id === item.slot_id ? result.item : i);
    const n=items.filter(i => !i.unavailable).length;
    setSlate({...slate!,version:result.session_version,items,result_count:n,partial:n===0,
      replacement_count:result.replacement_count,replacement_limit:result.replacement_limit,
      replacements_remaining:result.replacements_remaining,replacement_available:result.replacement_available,
      suggestion_index:result.suggestion_index,suggestion_count:result.suggestion_count});
    if(!result.replaced) setNotice('فعلاً گزینهٔ تازه‌ای با همین شرایط نداریم. سهمیهٔ تعویضت مصرف نشد.');
  });
  const browse = (direction: 'previous' | 'next') => run(async () => {
    try {
      setSlate(await api<Slate>(`/recommendation-sessions/${slate!.id}/navigate`,'POST',{
        direction,expected_version:slate!.version,
      }));
    } catch(e) {
      if(e instanceof ApiError && ['VERSION_CONFLICT','HISTORY_BOUNDARY'].includes(e.code)) {
        setSlate(await api<Slate>('/recommendation-sessions/'+slate!.id));
      }
      throw e;
    }
  });
  const toggleSave = (activityId: string) => run(async () => {
    const exists = saved.some(s => s.activity_id === activityId);
    await api('/saved/'+activityId,exists ? 'DELETE' : 'PUT',exists ? undefined : {});
    await loadSaved();setNotice(exists ? 'از ذخیره‌ها برداشته شد.' : 'برای بعد نگهش داشتیم.');
  });
  const start = () => run(async () => {
    const result = await api<Experience>('/experiences','POST',{recommendation_session_id:slate!.id,slot_id:slot!.slot_id,revision_id:slot!.revision_id});
    setExperience(result);setView('active');window.history.replaceState(null,'','/?experience='+result.id);
  });
  const complete = () => run(async () => {
    const result = await api<{experience: Experience; award: Award}>(`/experiences/${experience!.id}/complete`,'POST',{});
    setExperience(result.experience);setAward(result.award);setFeedbackDone(false);navigate('complete');
  });
  const showJourney = () => run(async () => {
    const [j,h] = await Promise.all([api<Journey>('/me/journey'),api<{items: Experience[]}>('/experiences?limit=100')]);
    setJourney(j);setHistory(h.items);navigate('journey');
  });
  const route = (next: View) => {
    if(!user) {returnView.current=next === 'home' ? 'questions' : next;return navigate('auth');}
    if(next === 'saved') run(async () => {await loadSaved();navigate('saved');});
    else if(next === 'journey') showJourney();
    else if(next === 'settings') run(async () => {setPreferences(await api<PreferencesType>('/me/preferences'));navigate('settings');});
    else navigate(next);
  };
  const returnHome = () => {checkIn.current=null;route('questions');};

  const summary = slate?.context_summary ?? context;
  return <>
    <a className="skip-link" href="#main">رفتن به محتوای اصلی</a>
    <div className="demo-bar"><span className="status-dot"/>نسخهٔ آزمایشی محلی <span className="demo-detail">· تجربه‌های تألیفی برای امتحان‌کردن</span></div>
    <header className="site-header"><button className="wordmark" onClick={() => navigate('home')} aria-label="فانیلو، صفحهٔ اول"><span className="brand-symbol"><Icon name="spark" size={25}/></span>فانیلو<span className="brand-dot" aria-hidden="true">.</span></button>
      <div className="header-caption">یه کم وقت برای خودت.</div>
      <div className="header-actions"><Pwa/>{experience?.status === 'active' && <button className="active-link" onClick={() => navigate('active')}><span className="status-dot"/>تجربهٔ بازت</button>}
        {user ? <><button className="account-button" onClick={() => route('settings')} aria-label="تنظیمات حساب"><Icon name="user" size={19}/><span>{user.display_name || 'حساب من'}</span></button>{user.role !== 'user' && <button className="text-button" onClick={() => route('admin')}>کارگاه محتوا</button>}</> : <button className="header-login" onClick={() => route('questions')}><Icon name="user" size={17}/>ورود <span className="login-extra">/ ساخت حساب</span></button>}</div>
    </header>
    <main id="main" ref={main} className={`page-shell ${view === 'admin' ? 'wide' : ''}`} aria-busy={busy}>
      {error && <div className="error-banner" role="alert"><p>{error}</p><button className="text-button" onClick={() => setError('')} aria-label="بستن پیام خطا">بستن</button></div>}
      <div className="status-region" role="status" aria-live="polite">{notice && <p className="notice-message">{notice}</p>}</div>
      {boot ? <div className="loading-state" role="status"><span className="loading-flower" aria-hidden="true"><Icon name="spark" size={42}/></span><p>یه لحظه، داریم آماده می‌شیم…</p></div> : <>
        {view === 'home' && <Home start={() => route('questions')}/>}
        {view === 'auth' && <Auth busy={busy} resetToken={!!resetToken} login={login}
          forgot={async email => {let ok=false;await run(async () => {await api('/auth/forgot-password','POST',{email});ok=true;});return ok;}}
          reset={password => run(async () => {await api('/auth/reset-password','POST',{token:resetToken,new_password:password});setResetToken(null);setUser(null);setNotice('رمزت عوض شد؛با رمز تازه وارد شو.');})} signup={(email,password,name) => run(async () => {await api('/auth/signup','POST',{email,password,display_name:name,adult_confirmed:true});await finishLogin(email,password);})} />}
        {view === 'questions' && <Questionnaire value={context} defaults={preferences?.preferences} change={v => {setContext(v);checkIn.current=null;}} submit={recommend} busy={busy} />}
        {view === 'results' && slate && <section><div className="section-heading"><div><span className="eyebrow">برای همین حال و همین وقت</span><h1>این یکی شاید الان بهت بچسبه.</h1><p className="intro">اگه به دلت ننشست، تا شش بار یه پیشنهاد تازه ببین.</p></div><button className="text-button" disabled={busy} onClick={returnHome}>شرایطم رو عوض کنم <span aria-hidden="true">↗</span></button></div>
          <div className="constraint-summary"><span>{number(summary.available_minutes)} دقیقه</span><span>{summary.social_mode === 'solo' ? 'تنهایی' : summary.social_mode === 'together' ? 'با همراه' : 'تنها یا با همراه'}</span><span>{({home:'خونه',outdoor:'هوای آزاد',indoor_public:'سرپوشیده',any:'هر جا شد'})[summary.venue]}</span><span>{summary.budget.mode === 'free' ? 'رایگان' : summary.budget.mode === 'cap' ? 'تا '+number(summary.budget.cap_toman!)+' تومان' : 'هزینهٔ منعطف'}</span></div>
          <SingleSuggestion slate={slate} busy={busy} saved={saved.some(s => s.activity_id === slate.items[0]?.activity_id)} open={open} save={item => toggleSave(item.activity_id!)} replace={replace} browse={browse} changeConditions={returnHome}/>
        </section>}
        {view === 'detail' && detail && <section className="detail-column"><button className="text-button back-button" onClick={() => navigate(slate && slot ? 'results' : 'saved')}><span aria-hidden="true">→</span> برگشت به انتخاب‌ها</button><ContentDetails content={detail.content} />{slate && slot ? <Button className="w-full" disabled={busy} onClick={start}>{busy ? 'یه لحظه…' : 'همین رو شروع می‌کنم'}</Button> : <><Note>برای شروع،شرایط همین الانت رو بگو تا مناسب‌بودن پیشنهاد بررسی بشه.</Note><Button onClick={returnHome}>برای الان پیشنهاد بگیرم</Button></>}</section>}
        {view === 'active' && experience && <section className="detail-column"><span className="experience-label"><span aria-hidden="true">●</span> وقتِ خودته</span>{experience.unavailable || !experience.content_snapshot ? <Empty title="دستور این تجربه دیگه در دسترس نیست."><p>می‌تونی تجربهٔ بازت رو تموم یا لغو کنی.</p></Empty> : <ContentDetails content={experience.content_snapshot} />}
          <p className="hint">زمان‌سنج و عجله‌ای در کار نیست.هر وقت برات کافی بود،همین‌جا تمومش کن.</p><div className="experience-actions"><Button onClick={complete} disabled={busy}>{busy ? 'یه لحظه…' : 'تمومش کردم'}</Button><button className="text-button" disabled={busy} onClick={() => run(async () => {await api(`/experiences/${experience.id}/cancel`,'POST',{});setExperience(null);returnHome();})}>این بار بی‌خیالش شدم</button></div>
        </section>}
        {view === 'complete' && experience && award && <section className="completion-column"><div className="completion-symbol" aria-hidden="true">✳</div><span className="eyebrow">یه وقت کوچیک برای خودت ساختی</span><h1>همین هم یه لحظهٔ خوب بود.</h1><p className="intro">هرقدرش که انجام دادی،کافیه.</p>
          {preferences?.preferences.show_gamification !== false && <div className="award-card"><strong>{award.points ? '+'+number(award.points)+' امتیاز' : 'تجربه‌ات ثبت شد'}</strong><p>{award.points ? 'یه قدم به مسیر تجربه‌هات اضافه شد.' : award.reason === 'RECENT_ACTIVITY' ? 'این تجربه رو همین هفته امتحان کردی؛امتیاز تازه‌ای اضافه نشد.' : 'سهم امتیاز این بازه پر شده؛این لحظه توی مسیرت می‌مونه.'}</p>{award.new_badges.map(key => <span className="earned-badge" key={key}>✧ {badgeNames[key]}</span>)}</div>}
          {!feedbackDone ? <div className="feedback"><h2>چقدر بهت چسبید؟</h2><p className="hint">اگه دوست داشتی بگو تا دفعهٔ بعد بهتر انتخاب کنیم.</p><div className="feedback-choices">{([['liked','چسبید'],['neutral','معمولی بود'],['disliked','برای من نبود']] as const).map(([rating,label]) => <Button secondary disabled={busy} key={rating} onClick={() => run(async () => {await api(`/experiences/${experience.id}/feedback`,'PUT',{rating,reason:null});setFeedbackDone(true);setNotice('بازخوردت ثبت شد.');})}>{label}</Button>)}</div><button className="text-button" disabled={busy} onClick={() => setFeedbackDone(true)}>الان نمی‌خوام بگم</button></div> : <p className="soft-note">هر وقت خواستی،یه تجربهٔ تازه منتظرته.</p>}
          <div className="inline-actions wrap"><Button onClick={returnHome}>یه پیشنهاد دیگه</Button><Button secondary onClick={showJourney}>مسیرم رو ببینم</Button></div>
        </section>}
        {view === 'saved' && <section><span className="eyebrow">برای یه وقت دیگه</span><h1>چیزهایی که نگه داشتی.</h1><p className="intro">لازم نیست نوبتشون همین امروز باشه.</p>{saved.length === 0 ? <Empty title="اینجا هنوز خلوت و آرومه."><p>هر پیشنهادی دوست داشتی،برای بعد نگهش دار.</p><Button onClick={returnHome}>یه پیشنهاد ببینم</Button></Empty> : <div className="saved-list">{saved.map(s => <article className="saved-card" key={s.activity_id}><div><h2>{s.unavailable ? 'فعلاً در دسترس نیست' : s.content?.title}</h2><p className="muted">{s.content?.teaser}</p></div><div className="inline-actions"><Button secondary disabled={busy || s.unavailable} onClick={() => run(async () => {setDetail(await api<Revision>('/activity-revisions/'+s.revision_id));setSlot(null);navigate('detail');})}>ببینمش</Button><button className="text-button" disabled={busy} onClick={() => toggleSave(s.activity_id)}>بردار</button></div></article>)}</div>}</section>}
        {view === 'journey' && journey && <section><span className="eyebrow">با ریتم خودت</span><h1>مسیر کوچیک تو.</h1><p className="intro">اینجا خبری از عقب‌افتادن نیست.فقط لحظه‌هایی که برای خودت ساختی.</p>
          {preferences?.preferences.show_gamification !== false && <><div className="journey-stats"><div><strong>{number(journey.total_points)}</strong><span>امتیاز اکتشاف</span></div><div><strong>{number(journey.rewarded_completions)}</strong><span>تجربهٔ امتیازدار</span></div></div><div className="badge-list">{journey.badges.map(key => <span key={key} className="earned-badge">✧ {badgeNames[key]}</span>)}</div><div className="dimension-list">{journey.completed_dimensions.map(key => <span key={key}>{dimensionNames[key]}</span>)}</div></>}
          <h2 className="history-title">لحظه‌های قبلی</h2>{history.length ? <div className="history-list">{history.map(e => <article key={e.id}><span aria-hidden="true">{e.status === 'completed' ? '✧' : '◌'}</span><div><h3>{e.unavailable ? 'تجربهٔ کنارگذاشته‌شده' : e.content_snapshot?.title}</h3><p className="hint">{new Intl.DateTimeFormat('fa-IR',{dateStyle:'medium'}).format(new Date(e.started_at))} · {({active:'در جریان',completed:'تموم‌شده',cancelled:'لغوشده',expired:'بسته‌شده'})[e.status]}</p></div></article>)}</div> : <Empty title="اولین لحظه هنوز در راهه."><p>هر وقت دلت خواست،یه تجربهٔ کوچیک انتخاب کن.</p><Button onClick={returnHome}>بریم انتخاب کنیم</Button></Empty>}
        </section>}
        {view === 'settings' && preferences && <><Preferences key={preferences.version} initial={preferences} busy={busy} save={v => run(async () => {setPreferences(await api<PreferencesType>('/me/preferences','PUT',v));checkIn.current=null;setNotice('انتخاب‌هات نگه داشته شد.');})} /><div className="account-footer"><p className="hint">{user?.email}</p><button className="text-button" disabled={busy} onClick={() => run(async () => {await api('/auth/logout','POST',{});setUser(null);setExperience(null);setSlate(null);setSaved([]);setPreferences(null);checkIn.current=null;navigate('home');})}>خروج از حساب</button></div></>}
        {view === 'admin' && user && <Admin user={user} report={report} />}
      </>}
    </main>
    {user && <nav className="bottom-nav" aria-label="صفحه‌های اصلی"><button aria-current={['questions','results','detail','active','complete'].includes(view) ? 'page' : undefined} onClick={returnHome}><Icon name="spark"/>امروز</button><button aria-current={view === 'saved' ? 'page' : undefined} onClick={() => route('saved')}><Icon name="bookmark"/>ذخیره‌ها</button><button aria-current={view === 'journey' ? 'page' : undefined} onClick={() => route('journey')}><Icon name="journey"/>مسیر من</button></nav>}
    <footer className={`site-footer ${user ? 'with-navigation' : ''}`}><span className="footer-brand"><Icon name="spark" size={17}/>فانیلو <span>· با ریتم تو</span></span><span>یه کم وقت برای خودت، بدون باید.</span><span className="footer-local">نسخهٔ آزمایشی</span></footer>
  </>;
}

