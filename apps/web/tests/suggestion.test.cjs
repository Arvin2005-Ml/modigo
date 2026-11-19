const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');

// Render the real TSX components using the installed React runtime.
const cache = new Map();
function load(filename) {
  filename = path.resolve(filename);
  if(cache.has(filename)) return cache.get(filename).exports;
  const source = fs.readFileSync(filename, 'utf8');
  const code = ts.transpileModule(source, {compilerOptions: {
    module:ts.ModuleKind.CommonJS, jsx:ts.JsxEmit.ReactJSX, esModuleInterop:true,
  }}).outputText;
  const loaded = {exports:{}};
  cache.set(filename,loaded);
  const localRequire = name => {
    if(!name.startsWith('.') && !name.startsWith('@/')) return require(name);
    const base = name.startsWith('@/') ? path.resolve(name.slice(2)) : path.resolve(path.dirname(filename),name);
    const target = [base+'.tsx',base+'.ts'].find(p => fs.existsSync(p));
    if(!target) throw new Error('Missing test module: '+name);
    return load(target);
  };
  vm.runInNewContext(code, {module:loaded,exports:loaded.exports,require:localRequire,Intl,Map,Response}, {filename});
  return loaded.exports;
}
const SingleSuggestion = load('components/SingleSuggestion.tsx').default;
const {ContentDetails} = load('components/Activity.tsx');
const {guestActivities} = load('lib/guest/catalog.ts');
const {recommendGuestActivity} = load('lib/guest/recommendation.ts');
const {initialContext} = load('lib/individual/initialContext.ts');
const item = {slot_id:'slot',activity_id:'activity',revision_id:'revision',title:'پیشنهاد اول',
  teaser:'یک تجربهٔ کوتاه و قابل انجام',total_minutes:10,cost_label:'رایگان',explanation:'متناسب با شرایطت',unavailable:false};
const slate = {id:'session',check_in_id:'check',version:1,items:[item],result_count:1,partial:false,
  replacement_count:0,replacement_limit:6,replacements_remaining:6,replacement_available:true,
  suggestion_index:0,suggestion_count:1};
function render(changes={}) {
  const noop = () => {};
  return renderToStaticMarkup(React.createElement(SingleSuggestion, {
    slate:{...slate,...changes},busy:false,saved:false,open:noop,save:noop,replace:noop,browse:noop,changeConditions:noop,
  }));
}

test('the result page renders exactly one activity even for an outdated multi-item payload', () => {
  const html = render({items:[item,{...item,title:'پیشنهاد دوم',slot_id:'second'}]});
  assert.equal((html.match(/class="activity-card"/g)||[]).length,1);
  assert.ok(html.includes('پیشنهاد اول'));
  assert.ok(!html.includes('پیشنهاد دوم'));
  assert.ok(html.includes('۶ بار دیگه'));
  assert.doesNotMatch(html, /<button[^>]*disabled=""[^>]*>یه پیشنهاد دیگه/);
});

test('a named outing shows its city and the venue check before opening the activity', () => {
  const html = render({items:[{...item, place:{name:'پردیس تماشا', city:'تهران'},
    venue_check_message:'پیش از رفتن، باز بودن و رزرو را بررسی کن.'}]});
  assert.match(html, /پردیس تماشا.*تهران/);
  assert.match(html, /پیش از رفتن، باز بودن و رزرو را بررسی کن/);
});

test('program links stay in activity details and are omitted without an HTTPS destination', () => {
  const program = {url:'https://cinematicket.org/cinema/detail/42', label:'دیدن سانس‌های این سینما'};
  const place = {name:'پردیس تماشا', city:'تهران', source_url:'https://example.com/', source_name:'معرفی سالن'};
  const details = (program) => renderToStaticMarkup(React.createElement(ContentDetails, {
    content:{...item, place:{...place, program}, cost:{kind:'unknown'}, steps:[], safety_notes:[]},
  }));
  assert.match(details(program), /href="https:\/\/cinematicket\.org\/cinema\/detail\/42" target="_blank" rel="noopener noreferrer"/);
  for (const unavailable of [undefined, {...program,url:'http://cinematicket.org/'}]) {
    assert.doesNotMatch(details(unavailable), /دیدن سانس‌ها|امکان خرید بلیت/);
  }
  assert.doesNotMatch(render({items:[{...item, place:{...place, program}}]}), /cinematicket\.org/);
});

test('after six changes the replace action is disabled while the current card remains usable', () => {
  const html = render({replacement_count:6,replacements_remaining:0,replacement_available:false});
  assert.match(html, /<button[^>]*disabled=""[^>]*>یه پیشنهاد دیگه/);
  assert.ok(html.includes('پیشنهاد اول'));
  assert.ok(html.includes('شش بار پیشنهاد رو عوض کردی'));
  assert.match(html, /<button class="title-button">پیشنهاد اول/);
});

test('catalog exhaustion disables replacement without replacing or hiding the current card', () => {
  const html = render({replacement_count:2,replacements_remaining:4,replacement_available:false});
  assert.ok(html.includes('پیشنهاد اول'));
  assert.ok(html.includes('فعلاً پیشنهاد تازه‌ای'));
  assert.match(html, /<button[^>]*disabled=""[^>]*>یه پیشنهاد دیگه/);
});

test('withdrawn content keeps the slot replaceable and empty results offer new conditions', () => {
  const withdrawn = render({items:[{slot_id:'slot',unavailable:true}],result_count:0,partial:true});
  assert.ok(!withdrawn.includes('پیشنهاد اول'));
  assert.ok(withdrawn.includes('این پیشنهاد فعلاً در دسترس نیست'));
  assert.doesNotMatch(withdrawn, /<button[^>]*disabled=""[^>]*>یه پیشنهاد دیگه/);
  const empty = render({items:[],result_count:0,partial:true,replacement_available:false});
  assert.ok(empty.includes('برگردم به سؤال‌ها'));
  assert.ok(!empty.includes('class="activity-card"'));
});

test('previous and next browse seen suggestions even when all six new suggestions are used', () => {
  const html = render({suggestion_count:7,suggestion_index:3,
    replacement_count:6,replacements_remaining:0,replacement_available:false});
  assert.ok(html.includes('پیشنهاد ۴ از ۷'));
  assert.ok(html.includes('سهمیهٔ تعویضت رو کم نمی‌کنه'));
  assert.doesNotMatch(html, /<button[^>]*disabled=""[^>]*>پیشنهاد (قبلی|بعدی)/);
  assert.ok(!html.includes('یه پیشنهاد دیگه'));
  assert.match(html, /<button class="title-button">پیشنهاد اول/);
});

test('history boundaries disable only the unavailable direction', () => {
  const first = render({suggestion_count:3,suggestion_index:0});
  assert.match(first, /<button[^>]*disabled=""[^>]*>پیشنهاد قبلی/);
  assert.doesNotMatch(first, /<button[^>]*disabled=""[^>]*>پیشنهاد بعدی/);
  const last = render({suggestion_count:3,suggestion_index:2,replacement_count:2,replacements_remaining:4});
  assert.doesNotMatch(last, /<button[^>]*disabled=""[^>]*>پیشنهاد قبلی/);
  assert.match(last, /<button[^>]*disabled=""[^>]*>پیشنهاد بعدی/);
  assert.ok(last.includes('یه پیشنهاد دیگه'));
});

test('guest suggestions use activities marked active with a published revision in the frontend snapshot', () => {
  const snapshot = fs.readFileSync('activities(1).json', 'utf8').replace(/^\uFEFF/, '');
  const source = new Map(snapshot.split(/\r?\n/).filter(line => line.trim()).map(line => {
    const row = JSON.parse(line);
    return [row.seed_key, row];
  }));
  assert.ok(guestActivities.length > 0);
  assert.equal(new Set(guestActivities.map(activity => activity.key)).size, guestActivities.length);
  for (const activity of guestActivities) {
    const row = source.get(activity.key);
    assert.ok(row?.active && row.published_revision_id, activity.key);
    assert.equal(activity.title, row.raw_title);
    assert.equal(activity.dimension, row.primary_dimension);
  }
});

test('guest ranking follows intent, energy, time, interests and available items', () => {
  const recommend = options => recommendGuestActivity({...initialContext, ...options});
  assert.equal(recommend({activity_intent:'unwind'}).dimension, 'relaxation');
  assert.equal(recommend({energy:'high'}).energy, 'high');
  assert.equal(recommend({energy:'low'}).energy, 'low');
  const reading = {activity_intent:'switch_off', owned_items:['book'], liked_tags:['reading']};
  assert.equal(recommend(reading).key, 'real:everyday-solo-014');
  assert.equal(recommend({...reading, available_minutes:120}).key, 'real:long-now-home-book-reading');
  assert.equal(recommend({...reading, owned_items:[]}).items, undefined);
  const creative = {activity_intent:'meaning', owned_items:['paper','pen']};
  assert.equal(recommend({...creative, liked_tags:['drawing']}).key, 'real:everyday-solo-012');
  assert.equal(recommend({...creative, liked_tags:['photography'], owned_items:['phone']}).key, 'real:everyday-solo-008');
});

test('the guest suggestion fits short times and party sizes without assuming tools or outdoor conditions', () => {
  for (const venue of ['home','away_from_home','any']) {
    for (const [social_mode, party_size] of [['solo',1],['either',1],['together',2],['together',12],['either',12]]) {
      for (const available_minutes of [5,15,30,120,480]) {
        const activity = recommendGuestActivity({...initialContext, venue, social_mode, party_size, available_minutes});
        assert.ok(activity?.minutes <= available_minutes);
        assert.equal(activity.items, undefined);
        assert.equal(activity.city, undefined);
        assert.notEqual(activity.venue, 'outdoor');
        if (venue === 'home') assert.equal(activity.venue, 'home');
        if (venue === 'away_from_home') assert.equal(activity.venue, 'indoor_public');
        if (social_mode !== 'either' || party_size === 1) {
          assert.ok(activity.people[0] <= party_size && activity.people[1] >= party_size);
        }
      }
    }
  }
  for (const available_minutes of [4, 30.5, 481, 1440, 2880]) {
    assert.equal(recommendGuestActivity({...initialContext, available_minutes}), undefined);
  }
  assert.equal(recommendGuestActivity({...initialContext, outing_days:1}), undefined);
});

test('a guest destination needs a matched city, permission, suitable weather and a flexible budget', () => {
  const context = {...initialContext, activity_intent:'unwind', liked_tags:['nature'], energy:'medium',
    available_minutes:60, venue:'away_from_home', city:' شيراز ', allow_venue_planning:true,
    weather:'fair', daylight:'day', budget:{mode:'flexible',cap_toman:null}};
  assert.equal(recommendGuestActivity(context).city, 'شیراز');
  for (const change of [
    {city:'رشت'}, {allow_venue_planning:false}, {daylight:'unknown'}, {weather:'adverse'},
    {budget:{mode:'free',cap_toman:null}}, {budget:{mode:'cap',cap_toman:100000}},
  ]) {
    assert.equal(recommendGuestActivity({...context, ...change}).city, undefined);
  }
});
