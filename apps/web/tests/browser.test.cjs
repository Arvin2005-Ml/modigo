const {chromium, firefox} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const origin = process.env.WEB_TEST_ORIGIN || 'http://127.0.0.1:3100';
const artifacts = process.env.BROWSER_TEST_ARTIFACTS || path.join(os.tmpdir(), 'funilo-web-browser-tests');
fs.mkdirSync(artifacts, {recursive: true});

const content = {
  title: 'یه مکث آروم', teaser: 'چند دقیقه برای خودت وقت بذار.',
  first_step: 'یک جای راحت انتخاب کن.', steps: ['آروم بنشین.', 'به اطرافت نگاه کن.'],
  lighter_version: 'فقط یک دقیقه امتحان کن.', materials_note: 'وسیله‌ای لازم نیست.',
  accessibility_note: 'نشسته هم می‌شه.', conditions_note: 'یک جای امن انتخاب کن.',
  active_minutes: 10, setup_minutes: 0, travel_minutes: 0, safety_notes: [],
  primary_dimension: 'relaxation', cost: {kind: 'free', note: 'رایگان'},
};
const basePreferences = {
  version: 1, preferences: {
    liked_tags: [], blocked_tags: [], owned_items: [], max_mobility: 'active',
    requires_step_free: false, requires_quiet: false, allow_async_contact: false,
    default_goal: 'any', show_gamification: true, analytics_opt_in: false,
    analytics_policy_version: null,
  },
};
async function setup(browser, options = {}) {
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, serviceWorkers: 'block'});
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  const errors = [], missing = [], requests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (response.status() >= 400 && !new URL(response.url()).pathname.startsWith('/api/v1/')) {
      errors.push('HTTP ' + response.status() + ': ' + response.url());
    }
  });
  page.on('console', message => {
    if (message.type() === 'error' && !message.text().includes('Failed to load resource')) errors.push(message.text());
  });
  const state = {
    authenticated: options.authenticated !== false,
    user: {id:'user-1', email:'test@example.com', display_name:'تست', role:options.role || 'user', timezone:'Asia/Tehran'},
    preferences: structuredClone(basePreferences), saved:false, active:null, completed:[],
    index:0, count:1, version:1, replacements:0, checkin:null,
    drafts: [
      {id:'draft-2', revision_number:2, draft_version:1, state:'draft', content:structuredClone(content), origin:'human'},
      {id:'draft-1', revision_number:1, draft_version:1, state:'superseded', content:{...content,title:'نسخهٔ قبلی'}, origin:'human'},
    ],
  };
  const item = () => ({
    slot_id:'slot-1', activity_id:'activity-' + state.index, revision_id:'revision-' + state.index,
    title:state.index === 0 ? content.title : 'پیشنهاد تازه ' + state.index,
    teaser:content.teaser,total_minutes:10,cost_label:'رایگان',explanation:'متناسب با وقتت',unavailable:false,
  });
  const replacement = () => ({
    replacement_count:state.replacements,replacement_limit:6,replacements_remaining:6-state.replacements,
    replacement_available:state.replacements<6,suggestion_index:state.index,suggestion_count:state.count,
  });
  const slate = () => ({
    id:'session-1',check_in_id:'check-1',version:state.version,items:[item()],result_count:1,partial:false,
    context_summary:state.checkin || {available_minutes:30,social_mode:'solo',party_size:1,venue:'home',budget:{mode:'free',cap_toman:null}},
    ...replacement(),
  });
  const activity = () => ({id:'admin-1',raw_title:'بذر آزمایشی',seed_key:'D-001',primary_dimension:'relaxation',active:false,revisions:state.drafts});
  await context.route('**/api/v1/**', async route => {
    const request = route.request(), url = new URL(request.url());
    const endpoint = url.pathname.replace('/api/v1', ''), method = request.method();
    const body = request.postData() ? request.postDataJSON() : undefined;
    requests.push({endpoint, method, body});
    const send = (data, status=200) => route.fulfill({status, contentType:'application/json', body:status === 204 ? undefined : JSON.stringify(data)});
    if (endpoint === '/auth/csrf') return send({csrf_token:'test-token'});
    if (endpoint === '/auth/login' || endpoint === '/auth/signup') {state.authenticated=true;return send({user:state.user,csrf_token:'test-token'});}
    if (endpoint === '/auth/logout') {state.authenticated=false;return send(null,204);}
    if (endpoint === '/auth/forgot-password') return send({},202);
    if (!state.authenticated) return send({error:{code:'AUTH_REQUIRED',message:'دوباره وارد شو.'}},401);
    if (endpoint === '/me') return send(state.user);
    if (endpoint === '/me/preferences') {
      if(method==='PUT') state.preferences={...body,version:state.preferences.version+1};
      return send(state.preferences);
    }
    if (endpoint === '/discover') return send({items:[
      {activity_id:'activity-0', revision_id:'revision-0', title:content.title, primary_dimension:content.primary_dimension},
    ]});
    if (endpoint === '/saved') return send({items:state.saved ? [{activity_id:'activity-0',revision_id:'revision-0',content,unavailable:false}] : []});
    if (endpoint.startsWith('/saved/')) {state.saved=method==='PUT';return send(null,204);}
    if (endpoint === '/check-ins') {state.checkin=body;return send({id:'check-1'},201);}
    if (endpoint.endsWith('/replace')) {
      state.replacements++;state.index=state.replacements;state.count=state.index+1;state.version++;
      return send({session_version:state.version,item:item(),replaced:true,...replacement()});
    }
    if (endpoint.endsWith('/navigate')) {state.index+=body.direction==='previous' ? -1:1;state.version++;return send(slate());}
    if (endpoint.startsWith('/recommendation-sessions')) return send(slate(),method==='POST'?201:200);
    if (endpoint.startsWith('/activity-revisions/')) return send({
      id:endpoint.split('/').at(-1), activity_id:'activity-0', content, origin:'human',
      catalog_start:options.catalogStart || {min_people:1,max_people:1,checks:[]},
    });
    if (endpoint === '/experiences/active') return send({experience:state.active});
    if (endpoint === '/experiences' && method === 'POST') {
      state.active={id:'experience-1',activity_id:'activity-0',revision_id:body.revision_id,status:'active',started_at:'2026-11-17T09:00:00Z',content_snapshot:content,unavailable:false};
      return send(state.active,201);
    }
    if(endpoint.endsWith('/complete')) {
      const experience={...state.active,status:'completed'};state.completed.push(experience);state.active=null;
      return send({experience,award:{points:10,total_points:10,new_badges:['first_step'],reason:'AWARDED'}});
    }
    if(endpoint.endsWith('/feedback')) return send({});
    if(endpoint==='/experiences') return send({items:state.completed});
    if(endpoint==='/me/journey') return send({total_points:10,rewarded_completions:1,completed_dimensions:['relaxation'],badges:['first_step']});
    if(endpoint==='/admin/activities') return send({items:[activity()],total:1,next_offset:null});
    if(endpoint==='/admin/activities/admin-1') return send(activity());
    if(endpoint.startsWith('/admin/revisions/') && method==='PATCH') {
      const draft=state.drafts.find(draft=>endpoint.endsWith(draft.id));
      if(draft.draft_version!==body.expected_draft_version) return send({error:{code:'VERSION_CONFLICT',message:'نسخه تغییر کرده.'}},409);
      Object.assign(draft,{content:body.content,draft_version:draft.draft_version+1});
      return send(draft);
    }
    missing.push(method+' '+endpoint);
    return send({error:{code:'NOT_FOUND',message:'Unhandled test fixture'}},404);
  });
  const finish = async () => {
    assert.deepEqual(missing,[], 'All requests should use declared fixtures');
    assert.deepEqual(errors,[], 'No browser errors');
    await context.close();
  };
  return {context,page,state,requests,errors,finish};
}
async function visible(page, selector) { await page.locator(selector).waitFor({state:'visible'}); }
async function screen(page,name) {
  for(const width of [360,390,768,1440]) {
    await page.setViewportSize({width,height:1000});
    await page.evaluate(()=>document.fonts.ready);
    const size=await page.evaluate(()=>({page:document.documentElement.scrollWidth,viewport:window.innerWidth}));
    assert.ok(size.page<=size.viewport+1,name+' horizontal overflow at '+width+': '+JSON.stringify(size));
    if(width===390) await page.screenshot({path:path.join(artifacts,name+'.png'),fullPage:true});
  }
}

async function catalogFlow(browser) {
  const app = await setup(browser, {catalogStart:{min_people:2,max_people:4,checks:['materials']}});
  const {page} = app;
  await page.setViewportSize({width:360,height:800});
  await page.goto(origin + '/discover');
  const detail = page.getByRole('link', {name:/یه مکث آروم/});
  await detail.click();
  const start = page.getByRole('button', {name:'همین رو شروع می‌کنم'});
  await start.waitFor();
  assert.equal(await start.isDisabled(), true);
  await page.getByLabel('تعداد نفرات، با خودت').selectOption('3');
  await page.getByRole('checkbox', {name:/شرایط بالا رو بررسی کردم/}).check();
  await start.click();
  await page.waitForURL('**/experiences/experience-1');
  const request = app.requests.find(({method,endpoint}) => method === 'POST' && endpoint === '/experiences');
  assert.deepEqual(request.body, {source:'catalog',revision_id:'revision-0',party_size:3,conditions_confirmed:true});
  assert.equal(app.requests.some(({endpoint}) => endpoint === '/check-ins' || endpoint.startsWith('/recommendation-sessions')), false);

  await page.goto(origin + '/discover');
  await detail.click();
  await page.getByRole('button', {name:'ادامهٔ همین فعالیت'}).click();
  await page.waitForURL('**/experiences/experience-1');
  await page.goto(origin + '/discover');
  await page.getByRole('link', {name:'ادامهٔ فعالیت قبلی'}).click();
  await page.waitForURL('**/experiences/experience-1');
  await page.reload();
  await page.getByRole('button', {name:'تمومش کردم'}).click();
  await page.getByRole('button', {name:'چسبید',exact:true}).click();
  await page.getByText('بازخوردت ثبت شد.', {exact:true}).waitFor();

  app.state.saved = true;
  await page.goto(origin + '/saved');
  await page.getByRole('button', {name:'ببینمش'}).click();
  await page.getByRole('checkbox', {name:/شرایط بالا رو بررسی کردم/}).check();
  await start.click();
  await page.waitForURL('**/experiences/experience-1');
  assert.equal(app.requests.filter(({method,endpoint}) => method === 'POST' && endpoint === '/experiences').length, 2);
  await app.finish();
  console.log('PASS catalog flow: discovery, conditions, start, resume, complete, feedback, and saved.');
}

async function questionnaireFromDiscover(browser) {
  const app = await setup(browser);
  const {page} = app;
  await page.goto(origin + '/discover');
  await page.getByRole('link', {name:'پیشنهاد برای همین الان'}).click();
  await page.waitForURL('**/individual');
  await page.getByRole('radio', {name:'چهار ساعت'}).check();
  const next = page.getByRole('button', {name:'بریم بعدی'});
  await next.click();

  const venue = page.getByRole('group', {name:'کجا می‌خوای باشی؟'});
  assert.equal(await venue.getByRole('radio').count(), 3);
  const outside = venue.getByRole('radio', {name:'بیرون از خونه'});
  await outside.check();
  await page.getByRole('checkbox', {name:'آره، پیشنهاد جا هم می‌خوام'}).check();
  await next.click();
  await page.getByRole('alert').filter({hasText:'اسم شهرت رو وارد کن'}).waitFor();
  await page.getByRole('textbox', {name:'شهر برای همین نوبت'}).fill('تهران');
  await page.getByRole('checkbox', {name:'هوا روشنه و برای قدم‌زدن مناسبه'}).check();
  await screen(page,'questionnaire-outing');
  await next.click();
  await page.getByRole('radio', {name:'منعطفم'}).check();
  await page.getByRole('button', {name:'قدم قبلی'}).click();
  assert.equal(await outside.isChecked(), true);
  assert.equal(await page.getByRole('textbox', {name:'شهر برای همین نوبت'}).inputValue(), 'تهران');
  await next.click();
  assert.equal(await page.getByRole('radio', {name:'منعطفم'}).isChecked(), true);
  await next.click();
  await page.getByRole('radio', {name:'یه چالش یا کشف تازه'}).check();
  await page.getByRole('button', {name:'پیشنهادم رو ببینم'}).click();
  await visible(page,'.single-suggestion');
  assert.deepEqual(app.state.checkin, {
    available_minutes:240, energy:'low', social_mode:'solo', party_size:1,
    venue:'away_from_home', budget:{mode:'flexible',cap_toman:null}, activity_intent:'learn',
    allow_venue_planning:true, city:'تهران', weather:'fair', daylight:'day',
  });
  const summary = page.locator('.constraint-summary');
  await summary.getByText('بیرون از خونه', {exact:true}).waitFor();
  await summary.getByText('تهران', {exact:true}).waitFor();
  await page.getByText('بعد از این پیشنهاد، ۲۳۰ دقیقه از وقتت می‌مونه.', {exact:true}).waitFor();
  await app.finish();
  console.log('PASS questionnaire from Discover: four steps, location opt-in, conditions, intent, and result summary.');
}

async function main() {
  const browserType=process.env.WEB_TEST_BROWSER === 'firefox' ? firefox : chromium;
  const browser=await browserType.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE_PATH || undefined});
  try {
    if (process.argv.includes('--questionnaire')) {
      await questionnaireFromDiscover(browser);
      return;
    }
    await catalogFlow(browser);
    if (process.argv.includes('--discover')) return;
    await questionnaireFromDiscover(browser);
    {
      const app=await setup(browser,{authenticated:false});
      const {page}=app;
      await page.goto(origin);
      await visible(page,'.hero');
      await screen(page,'home');
      await page.getByRole('button',{name:'نصب فانیلو روی دستگاه'}).click();
      await visible(page,'dialog[open]');
      await page.keyboard.press('Escape');
      await page.getByRole('button',{name:'ببینیم چی می‌چسبه'}).click();
      await page.getByLabel('ایمیل',{exact:true}).fill('test@example.com');
      await page.getByLabel('رمز عبور',{exact:false}).fill('a-test-password');
      await page.getByRole('button',{name:'وارد بشم',exact:true}).click();
      await visible(page,'.question-layout');
      await screen(page,'questions');
      await page.locator('.number-input').fill('۴');
      await page.getByRole('button',{name:'بریم بعدی'}).click();
      await page.getByRole('alert').filter({hasText:'بین ۵ تا ۴۸۰'}).waitFor();
      await page.locator('.number-input').fill('۳۰');
      for(let i=0;i<3;i++) await page.getByRole('button',{name:'بریم بعدی'}).click();
      await page.getByRole('button',{name:'پیشنهادم رو ببینم'}).click();
      await visible(page,'.single-suggestion');
      assert.equal(app.state.checkin.available_minutes,30);
      assert.equal(app.state.checkin.activity_intent,'any');
      assert.equal('mood' in app.state.checkin,false);
      await screen(page,'suggestion');
      await page.getByRole('button',{name:'ذخیره برای بعد: '+content.title,exact:true}).click();
      await page.getByRole('button',{name:'حذف از ذخیره‌ها: '+content.title,exact:true}).waitFor();
      await page.getByRole('button',{name:'یه پیشنهاد دیگه',exact:true}).click();
      await page.getByRole('button',{name:'پیشنهاد قبلی',exact:true}).click();
      await page.getByRole('button',{name:'پیشنهاد بعدی',exact:true}).click();
      await page.getByRole('button',{name:'ببینمش',exact:true}).click();
      await visible(page,'.detail-column');
      await screen(page,'detail');
      await page.getByRole('button',{name:'همین رو شروع می‌کنم'}).click();
      await page.getByRole('button',{name:'تمومش کردم'}).click();
      await visible(page,'.completion-column');
      await page.getByRole('button',{name:'چسبید',exact:true}).click();
      await page.getByRole('button',{name:'مسیرم رو ببینم'}).click();
      await visible(page,'.journey-stats');
      await page.getByRole('button',{name:'تنظیمات حساب',exact:true}).click();
      await page.getByRole('checkbox',{name:'یه تجربهٔ ساکت می‌خوام.'}).check();
      await page.getByRole('button',{name:'انتخاب‌هام رو نگه دار'}).click();
      await page.getByText('انتخاب‌هات نگه داشته شد.',{exact:true}).waitFor();
      assert.equal(app.state.preferences.preferences.requires_quiet,true);
      await page.getByRole('button',{name:'ذخیره‌ها',exact:true}).click();
      await visible(page,'.saved-card');
      await page.getByRole('button',{name:'بردار',exact:true}).click();
      await page.getByRole('heading',{name:'اینجا هنوز خلوت و آرومه.'}).waitFor();
      await page.getByRole('button',{name:'تنظیمات حساب',exact:true}).click();
      await page.getByRole('button',{name:'خروج از حساب',exact:true}).click();
      await visible(page,'.hero');
      await app.finish();
      console.log('PASS user flow: login, Persian validation, recommendations, browsing, save, start, complete, feedback, journey, preferences, logout; four viewport widths.');
    }
    {
      const app=await setup(browser,{role:'admin'});
      const {page}=app;
      await page.goto(origin);
      await visible(page,'.question-layout');
      await page.getByRole('button',{name:'کارگاه محتوا',exact:true}).click();
      await page.getByRole('button',{name:/بذر آزمایشی/}).click();
      await visible(page,'.json-editor');
      await page.locator('#content-json').fill(JSON.stringify({...content,title:'ویرایش تازه'}));
      await page.getByRole('button',{name:'ذخیرهٔ ویرایش',exact:true}).click();
      await page.getByText('پیش‌نویس نگه داشته شد.',{exact:true}).waitFor();
      await page.locator('.admin-editor select').selectOption('draft-1');
      await page.locator('.admin-editor select').selectOption('draft-2');
      assert.equal(JSON.parse(await page.locator('#content-json').inputValue()).title,'ویرایش تازه','Saved draft must remain current after switching revisions');
      await page.getByRole('button',{name:'ذخیرهٔ ویرایش',exact:true}).click();
      await page.getByText('پیش‌نویس نگه داشته شد.',{exact:true}).waitFor();
      assert.equal(app.state.drafts[0].draft_version,3);
      await screen(page,'admin');
      await app.finish();
      console.log('PASS admin edit: saved content and version survive switching revisions.');
    }
    console.log('Screenshots: ' + artifacts);
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});

