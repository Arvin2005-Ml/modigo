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
  const activityContent = options.activityContent ?? content;
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
    outingOriginsStatus: options.outingOriginsStatus || 200,
    authenticated: options.authenticated !== false,
    user: {id:'user-1', email:'test@example.com', display_name:'تست', role:options.role || 'user', timezone:'Asia/Tehran'},
    preferences: structuredClone(basePreferences), saved:false, active:null, completed:[],
    historyUnavailable:false,
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
    if (endpoint === '/outing-origins') {
      if (state.outingOriginsStatus !== 200) return send({},state.outingOriginsStatus);
      return send({cities:['تهران','مشهد','اصفهان','شیراز','تبریز']});
    }
    if (endpoint === '/me/preferences') {
      if(method==='PUT') state.preferences={...body,version:state.preferences.version+1};
      return send(state.preferences);
    }
    if (endpoint === '/discover') return send({items:[
      {activity_id:'activity-0', revision_id:'revision-0', title:activityContent.title,
        teaser:activityContent.teaser, primary_dimension:activityContent.primary_dimension,
        venue:activityContent.place ? 'indoor_public' : 'home',
        place:activityContent.place ? {name:activityContent.place.name, city:activityContent.place.city} : null},
      {activity_id:'activity-1', revision_id:'revision-1', title:'یه طرح کوچیک برای خودت',
        teaser:'با کاغذ و قلم، یه چیز ساده از دوروبرت بکش.', primary_dimension:'mastery', venue:'home', place:null},
      {activity_id:'activity-2', revision_id:'revision-2', title:'یه مسیر تازه برای قدم‌زدن',
        teaser:'یه مسیر آشنا رو از کوچه‌ای که کمتر رفتی ادامه بده و به اطرافت دقت کن.', primary_dimension:'detachment', venue:'outdoor', place:null},
      {activity_id:'activity-3', revision_id:'revision-3', title:'یه چیدمان تازه برای میز',
        teaser:'چند وسیلهٔ روی میز رو با سلیقهٔ خودت دوباره بچین.', primary_dimension:'autonomy', venue:'home', place:null},
      {activity_id:'activity-4', revision_id:'revision-4', title:'یادداشت برای خودِ فردا',
        teaser:'یک چیز مهم از امروز رو برای فردا یادداشت کن.', primary_dimension:'meaning', venue:'home', place:null},
      {activity_id:'activity-5', revision_id:'revision-5', title:'چای و گپ دونفره',
        teaser:'با یکی از نزدیکانت چای بخور و از روزش بپرس.', primary_dimension:'affiliation', venue:'home', place:null},
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
      id:endpoint.split('/').at(-1), activity_id:'activity-0', content:activityContent, origin:'human',
      catalog_start:options.catalogStart || {min_people:1,max_people:1,checks:[]},
    });
    if (endpoint === '/experiences/active') return send({experience:state.active});
    if (endpoint === '/experiences' && method === 'POST') {
      state.active={id:'experience-1',activity_id:'activity-0',revision_id:body.revision_id,status:'active',started_at:'2026-11-17T09:00:00Z',content_snapshot:activityContent,unavailable:false};
      return send(state.active,201);
    }
    if(endpoint.endsWith('/complete')) {
      const experience={...state.active,status:'completed'};state.completed.push(experience);state.active=null;
      return send({experience,award:{points:10,total_points:10,new_badges:['first_step'],reason:'AWARDED'}});
    }
    if(endpoint.endsWith('/feedback')) return send({});
    if(endpoint==='/experiences') {
      if (state.historyUnavailable) return send({error:{code:'UNAVAILABLE',message:'Try again'}},503);
      return send({items:state.completed});
    }
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

async function dashboardFlow(browser) {
  const app = await setup(browser, {authenticated:false});
  const {page, state, requests} = app;
  await page.goto(origin + '/dashboard');
  await page.waitForURL('**/login?next=%2Fdashboard');
  assert.equal(requests.some(({endpoint}) =>
    ['/saved', '/experiences', '/experiences/active'].includes(endpoint)), false);

  await page.getByLabel('ایمیل', {exact:true}).fill('test@example.com');
  await page.getByLabel('رمز عبور', {exact:false}).fill('a-test-password');
  await page.getByRole('button', {name:'وارد بشم',exact:true}).click();
  await page.waitForURL('**/dashboard');
  await page.getByRole('heading', {name:'پنل کاربری',level:1}).waitFor();
  await page.getByText('هنوز فعالیتی در سابقه‌ات ثبت نشده.', {exact:true}).waitFor();
  await page.getByText('فعالیت‌هایی که برای بعد ذخیره می‌کنی، اینجا می‌مونن.', {exact:true}).waitFor();
  await screen(page, 'dashboard-empty');

  state.saved = true;
  state.active = {
    id:'active-1', activity_id:'activity-1', revision_id:'revision-1',
    status:'active', started_at:'2026-11-19T09:00:00Z',
    content_snapshot:{...content,title:'فعالیت امروز'}, unavailable:false,
  };
  state.completed = [{...state.active,id:'past-1',status:'completed',unavailable:true}];
  state.historyUnavailable = true;
  await page.reload();
  const saved = page.getByRole('region', {name:'ذخیره‌ها',exact:true});
  await saved.getByRole('link', {name:content.title}).waitFor();
  const recent = page.getByRole('region', {name:'فعالیت‌های اخیر'});
  await recent.getByRole('alert').waitFor();
  state.historyUnavailable = false;
  await recent.getByRole('button', {name:'تلاش دوباره'}).click();
  await recent.getByText('فعالیت کنارگذاشته‌شده', {exact:true}).waitFor();
  assert.equal(await recent.getByText('فعالیت امروز', {exact:true}).count(), 0);
  const resume = page.getByRole('link', {name:'ادامهٔ فعالیت',exact:true});
  await resume.waitFor();
  assert.equal(await resume.getAttribute('href'), '/experiences/active-1');
  await screen(page, 'dashboard');
  await page.screenshot({path:path.join(artifacts,'dashboard-desktop.png'),fullPage:true});

  await saved.getByRole('link', {name:content.title}).click();
  await page.waitForURL('**/activities/revision-0?from=saved');
  await page.getByRole('link', {name:'پنل کاربری',exact:true}).click();
  await page.waitForURL('**/dashboard');
  await page.getByRole('link', {name:'تنظیمات',exact:true}).click();
  await page.waitForURL('**/settings');
  await app.finish();
  console.log('PASS dashboard: private access, empty and populated states, partial failure and retry, links, and four viewport widths.');
}

async function catalogFlow(browser) {
  const program = {
    url:'https://www.tiwall.com/roudaki',
    label:'دیدن برنامه‌های بنیاد رودکی در تیوال',
    scope:'collection',
  };
  const app = await setup(browser, {
    catalogStart:{min_people:2,max_people:4,checks:['materials']},
    activityContent:{...content, requires_venue_check:true, place:{
      name:'تالار رودکی', city:'تهران', source_name:'بنیاد رودکی',
      source_url:'https://roudakifoundation.com/', program,
    }},
  });
  const {page} = app;
  await app.context.route(program.url, route => route.fulfill({body:'Seller fixture'}));
  await page.setViewportSize({width:360,height:800});
  await page.goto(origin + '/discover');
  const detail = page.getByRole('link', {name:/یه مکث آروم/});
  const card = page.getByRole('article').filter({has:detail});
  await card.getByText(content.teaser, {exact:true}).waitFor();
  await card.getByText('آرامش', {exact:true}).waitFor();
  await card.getByText('تالار رودکی، تهران', {exact:true}).waitFor();
  await page.getByRole('article').getByText('در خانه', {exact:true}).first().waitFor();
  await page.getByRole('article').getByText('فضای باز', {exact:true}).waitFor();
  assert.equal(await page.getByRole('article').locator('img, picture, .moment-art').count(), 0);
  const colors = await page.locator('[data-dimension]').evaluateAll(
    badges => badges.map(badge => getComputedStyle(badge).backgroundColor),
  );
  assert.equal(new Set(colors).size, 6);
  const header = page.getByRole('banner');
  const search = header.getByRole('searchbox', {name:'جست‌وجوی فعالیت'});
  const filters = page.getByRole('group', {name:'فیلتر فعالیت‌ها'});
  assert.equal(await page.getByRole('link', {name:'پیشنهاد برای همین الان'}).count(), 0);
  assert.equal(await page.getByRole('link', {name:'فعالیت‌های ذخیره‌شده'}).count(), 0);
  assert.equal(await filters.getByRole('button').count(), 12);
  assert.equal(await filters.locator('button svg').count(), 12);
  assert.equal(await filters.evaluate(element =>
    element.scrollWidth > element.clientWidth &&
    getComputedStyle(element).scrollbarWidth === 'none' &&
    new Set([...element.children].map(button => button.offsetTop)).size === 1), true);
  await search.fill('قدم‌زدن');
  await page.getByRole('article').nth(1).waitFor({state:'hidden'});
  await page.getByRole('heading', {name:'یه مسیر تازه برای قدم‌زدن'}).waitFor();
  assert.equal(await page.getByRole('article').count(), 1);
  await search.fill('');
  await filters.getByRole('button', {name:'وقت گذراندن با دیگران'}).click();
  await page.getByRole('heading', {name:'چای و گپ دونفره'}).waitFor();
  assert.equal(await page.getByRole('article').count(), 1);
  for (const [label, title, count] of [
    ['در خانه', 'یه طرح کوچیک برای خودت', 4],
    ['فضای باز', 'یه مسیر تازه برای قدم‌زدن', 1],
    ['سرپوشیده', content.title, 1],
    ['مکان مشخص', content.title, 1],
  ]) {
    await filters.getByRole('button', {name:label, exact:true}).click();
    await filters.getByRole('button', {name:label, exact:true, pressed:true}).waitFor();
    await page.getByRole('heading', {name:title, exact:true}).waitFor();
    assert.equal(await page.getByRole('article').count(), count);
  }
  const allActivities = filters.getByRole('button', {name:'همه', exact:true});
  await allActivities.click();
  await card.waitFor();
  await screen(page, 'discover-search-mobile');
  await page.setViewportSize({width:1440,height:1200});
  const headerBox = await header.boundingBox();
  const searchBox = await header.getByRole('search').boundingBox();
  assert.ok(Math.abs(headerBox.x + headerBox.width / 2 - searchBox.x - searchBox.width / 2) <= 1);
  await page.screenshot({path:path.join(artifacts,'discover-search-desktop.png'),fullPage:true});
  await page.setViewportSize({width:360,height:800});
  const bookmark = card.getByRole('button', {name:/ذخیره برای بعد/});
  await bookmark.click();
  await bookmark.and(page.locator('[aria-pressed=true]')).waitFor();
  await filters.getByRole('button', {name:'ذخیره‌شده‌ها', exact:true}).click();
  await filters.getByRole('button', {name:'ذخیره‌شده‌ها', pressed:true}).waitFor();
  assert.equal(await page.getByRole('article').count(), 1);
  await bookmark.click();
  await page.getByText('فعالیتی پیدا نشد.', {exact:true}).waitFor();
  await allActivities.click();
  await detail.click();
  const programLink = page.getByRole('link', {name:program.label,exact:true});
  await programLink.waitFor();
  assert.equal(await programLink.getAttribute('href'), program.url);
  assert.equal(await programLink.getAttribute('rel'), 'noopener noreferrer');
  await page.getByText('سانس و امکان خرید بلیت رو در سایت مقصد بررسی کن.').waitFor();
  await page.getByText(/قبل از رفتن، باز بودن، هزینه، رزرو/).waitFor();
  const [seller] = await Promise.all([page.waitForEvent('popup'), programLink.click()]);
  await seller.waitForURL(program.url);
  await seller.close();
  const start = page.getByRole('button', {name:'همین رو شروع می‌کنم'});
  await start.waitFor();
  assert.equal(await start.isDisabled(), true);
  await page.getByLabel('تعداد نفرات، با خودت').selectOption('3');
  await page.getByRole('checkbox', {name:/شرایط بالا رو بررسی کردم/}).check();
  await start.click();
  await page.waitForURL('**/experiences/experience-1');
  await programLink.waitFor();
  const request = app.requests.find(({method,endpoint}) => method === 'POST' && endpoint === '/experiences');
  assert.deepEqual(request.body, {source:'catalog',revision_id:'revision-0',party_size:3,conditions_confirmed:true});
  assert.equal(app.requests.some(({endpoint}) => endpoint === '/check-ins' || endpoint.startsWith('/recommendation-sessions')), false);

  await page.goto(origin + '/discover');
  await detail.click();
  await page.getByRole('button', {name:'ادامهٔ همین فعالیت'}).click();
  await page.waitForURL('**/experiences/experience-1');
  await page.goto(origin + '/discover');
  await page.getByRole('link', {name:'تجربهٔ بازت'}).click();
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
  await page.getByRole('navigation', {name:'صفحه‌های اصلی'}).getByRole('link', {name:'Individual'}).click();
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
  assert.equal(app.requests.some(({endpoint}) => endpoint === '/outing-origins'), false);
  const summary = page.locator('.constraint-summary');
  await summary.getByText('بیرون از خونه', {exact:true}).waitFor();
  await summary.getByText('تهران', {exact:true}).waitFor();
  await page.getByText('بعد از این پیشنهاد، ۲۳۰ دقیقه از وقتت می‌مونه.', {exact:true}).waitFor();
  await app.finish();
  console.log('PASS questionnaire from Discover: four steps, location opt-in, conditions, intent, and result summary.');
}

async function fullDayQuestionnaire(browser) {
  for (const days of [1, 2]) {
    const app = await setup(browser, {outingOriginsStatus:503});
    const {page, state} = app;
    await page.goto(origin + '/individual');
    const duration = page.getByRole('radio', {name:days === 1 ? 'یک روز کامل' : 'دو روز',exact:true});
    const minutes = page.getByRole('textbox', {name:'یا به دقیقه بنویس'});
    const next = page.getByRole('button', {name:'بریم بعدی'});
    await minutes.fill(String(days * 1440));
    await next.click();
    await page.getByRole('alert').filter({hasText:'بین ۵ تا ۴۸۰'}).waitFor();
    await duration.check();
    assert.equal(await minutes.count(), 0);
    await next.click();

    const venue = page.getByRole('group', {name:'کجا می‌خوای باشی؟'});
    const home = venue.getByRole('radio', {name:'توی خونه',exact:true});
    assert.equal(await home.isDisabled(), true);
    assert.equal(await venue.getByRole('radio', {name:'هر جا شد',exact:true}).isDisabled(), true);
    assert.equal(await venue.getByRole('radio', {name:'بیرون از خونه',exact:true}).isChecked(), true);
    const cities = page.getByRole('combobox', {name:/از کدوم شهر راه می‌افتی/});
    const weather = page.getByRole('checkbox', {name:/بازدیدها رو به روشنایی روز/});
    assert.equal(await weather.isChecked(), false);

    if (days === 2) {
      assert.equal(await cities.count(), 0);
      await next.click();
      await page.getByRole('alert').filter({hasText:'تمایلت به سفر رو مشخص کن'}).waitFor();
      await page.getByRole('radio', {name:'نه، این بار سفر نمی‌خوام'}).check();
      await page.getByRole('button', {name:'تغییر مدت',exact:true}).click();
      await page.getByRole('radio', {name:'نیم ساعت',exact:true}).check();
      await next.click();
      assert.equal(await home.isEnabled(), true);
      assert.equal(await cities.count(), 0);
      await home.check();
      await page.getByRole('button', {name:'قدم قبلی'}).click();
      await duration.check();
      await next.click();
      await page.getByRole('radio', {name:'آره، مبدأ رو انتخاب می‌کنم'}).check();
    }

    await page.getByRole('alert').filter({hasText:'فهرست شهرها دریافت نشد'}).waitFor();
    state.outingOriginsStatus = 200;
    await page.getByRole('button', {name:'دریافت دوبارهٔ شهرها'}).click();
    await cities.waitFor();
    assert.deepEqual(await cities.locator('option').evaluateAll(options => options.slice(1).map(option => option.value)),
      ['تهران','مشهد','اصفهان','شیراز','تبریز']);
    await next.click();
    await page.getByRole('alert').filter({hasText:'شهر مبدأ رو انتخاب کن'}).waitFor();
    assert.equal(await cities.getAttribute('aria-invalid'), 'true');
    assert.equal(state.checkin, null);
    await cities.selectOption('اصفهان');
    await weather.check();
    if (days === 2) {
      const previous = page.getByRole('button', {name:'قدم قبلی'});
      await previous.click();
      await page.getByRole('radio', {name:'یک روز کامل',exact:true}).check();
      await next.click();
      assert.equal(await cities.inputValue(), 'اصفهان');
      assert.equal(await weather.isChecked(), false);
      await previous.click();
      await duration.check();
      await next.click();
      assert.equal(await cities.count(), 0);
      await page.getByRole('radio', {name:'آره، مبدأ رو انتخاب می‌کنم'}).check();
      assert.equal(await cities.inputValue(), 'اصفهان');
      await weather.check();
    }
    if (days === 2) {
      await page.evaluate(() => window.scrollTo({top:0,behavior:'instant'}));
      await screen(page,'questionnaire-two-days');
    }
    await next.click();
    assert.equal(await page.getByRole('radio', {name:'رایگان باشه'}).isChecked(), true);
    await page.getByRole('radio', {name:'منعطفم'}).check();
    await next.click();
    await page.getByRole('button', {name:'پیشنهادم رو ببینم'}).click();
    await page.waitForURL('**/individual/results?slate=*');
    await visible(page,'.single-suggestion');
    assert.deepEqual(state.checkin, {
      available_minutes:days * 1440, outing_days:days, energy:'low', social_mode:'solo', party_size:1,
      venue:'away_from_home', budget:{mode:'flexible',cap_toman:null}, activity_intent:'any',
      allow_venue_planning:true, city:'اصفهان', weather:'fair', daylight:'day',
    });
    await app.finish();
  }

  const app = await setup(browser, {outingOriginsStatus:401});
  await app.page.goto(origin + '/individual');
  await app.page.getByRole('radio', {name:'دو روز',exact:true}).check();
  await app.page.waitForURL('**/login?next=%2Findividual');
  await app.finish();
  console.log('PASS full-day questionnaire: duration, travel consent, rejected inputs, cities, retry, session expiry, and payload.');
}

async function main() {
  const browserType=process.env.WEB_TEST_BROWSER === 'firefox' ? firefox : chromium;
  const browser=await browserType.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE_PATH || undefined});
  try {
    if (process.argv.includes('--dashboard')) {
      await dashboardFlow(browser);
      return;
    }
    if (process.argv.includes('--questionnaire')) {
      await questionnaireFromDiscover(browser);
      await fullDayQuestionnaire(browser);
      return;
    }
    await catalogFlow(browser);
    if (process.argv.includes('--discover')) return;
    await questionnaireFromDiscover(browser);
    await fullDayQuestionnaire(browser);
    await dashboardFlow(browser);
    {
      const app=await setup(browser,{authenticated:false});
      const {page}=app;
      await page.goto(origin);
      await visible(page,'.hero');
      await screen(page,'home');
      await page.getByRole('button',{name:'ببینیم چی می‌چسبه'}).click();
      await page.getByLabel('ایمیل',{exact:true}).fill('test@example.com');
      await page.getByLabel('رمز عبور',{exact:false}).fill('a-test-password');
      await page.getByRole('button',{name:'وارد بشم',exact:true}).click();
      await visible(page,'.question-layout');
      await page.getByRole('button',{name:'نصب مودیگو روی دستگاه'}).click();
      await visible(page,'dialog[open]');
      await page.keyboard.press('Escape');
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
      await page.getByRole('link',{name:'پنل کاربری',exact:true}).click();
      await page.getByRole('link',{name:'تنظیمات',exact:true}).click();
      await page.getByRole('checkbox',{name:'یه تجربهٔ ساکت می‌خوام.'}).check();
      await page.getByRole('button',{name:'انتخاب‌هام رو نگه دار'}).click();
      await page.getByText('انتخاب‌هات نگه داشته شد.',{exact:true}).waitFor();
      assert.equal(app.state.preferences.preferences.requires_quiet,true);
      await page.getByRole('link',{name:'ذخیره‌ها',exact:true}).click();
      await visible(page,'.saved-card');
      await page.getByRole('button',{name:'بردار',exact:true}).click();
      await page.getByRole('heading',{name:'اینجا هنوز خلوت و آرومه.'}).waitFor();
      await page.getByRole('link',{name:'پنل کاربری',exact:true}).click();
      await page.getByRole('link',{name:'تنظیمات',exact:true}).click();
      await page.getByRole('button',{name:'خروج از حساب',exact:true}).click();
      await visible(page,'.hero');
      await app.finish();
      console.log('PASS user flow: login, Persian validation, recommendations, browsing, save, start, complete, feedback, journey, preferences, logout; four viewport widths.');
    }
    {
      const app=await setup(browser,{role:'admin'});
      const {page}=app;
      await page.goto(origin);
      await page.getByRole('heading',{name:'پنل کاربری',level:1}).waitFor();
      await page.getByRole('link',{name:'کارگاه محتوا',exact:true}).click();
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

