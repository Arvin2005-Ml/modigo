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
  const module = {exports:{}};
  cache.set(filename,module);
  const localRequire = name => {
    if(!name.startsWith('.') && !name.startsWith('@/')) return require(name);
    const base = name.startsWith('@/') ? path.resolve(name.slice(2)) : path.resolve(path.dirname(filename),name);
    const target = [base+'.tsx',base+'.ts'].find(p => fs.existsSync(p));
    if(!target) throw new Error('Missing test module: '+name);
    return load(target);
  };
  vm.runInNewContext(code, {module,exports:module.exports,require:localRequire,Intl,Map,Response}, {filename});
  return module.exports;
}
const SingleSuggestion = load('components/SingleSuggestion.tsx').default;
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

test('conditional venue plans show their booking requirement and bounded duration', () => {
  const html = render({items:[{...item,cost_label:'هزینهٔ متغیر',requires_venue_check:true,total_minutes:210}]});
  assert.ok(html.includes('نیاز به بررسی محل، قیمت و رزرو'));
  assert.match(html, /تا .*۲۱۰.*دقیقه/);
  const {ContentDetails} = load('components/Activity.tsx');
  const detail = renderToStaticMarkup(React.createElement(ContentDetails, {content:{
    title:'سینما',teaser:'فیلم روی پرده',first_step:'سانس مناسب را بررسی کن',
    steps:['بلیت را بررسی کن','فیلم را ببین'],lighter_version:'سانس کوتاه‌تر',
    active_minutes:120,setup_minutes:30,travel_minutes:60,requires_venue_check:true,
    conditions_note:'رفتن و برگشتن حداکثر ۶۰ دقیقه',cost:{kind:'unknown',note:'قیمت تأیید نشده'},
    materials_note:'وسایل را بپرس',accessibility_note:'دسترسی تأیید نشده',safety_notes:[],
  }}));
  assert.ok(detail.includes('این پیشنهاد رزرو قطعی نیست'));
  assert.ok(detail.includes('رفتن و برگشتن حداکثر ۶۰ دقیقه'));
  assert.ok(detail.includes('قیمت تأیید نشده'));
});

test('a researched place exposes a labelled source link without promising booking or price', () => {
  const {ContentDetails} = load('components/Activity.tsx');
  const detail = renderToStaticMarkup(React.createElement(ContentDetails,{content:{
    title:'پردیس سینمایی کورش',teaser:'یک فیلم از برنامه جاری',first_step:'برنامه را بررسی کن',
    steps:['بلیت معتبر همان سانس را تهیه کن','فیلم را کامل ببین'],lighter_version:'یک فیلم کوتاه‌تر انتخاب کن',
    active_minutes:120,setup_minutes:20,travel_minutes:60,requires_venue_check:true,
    place:{name:'پردیس سینمایی کورش',city:'تهران',source_url:'https://kouroshmall.com/',source_name:'مجتمع کورش',researched_on:'2026-11-14',evidence_scope:'place_and_activity_type_only'},
    conditions_note:'برنامه روز تأیید نشده',cost:{kind:'unknown',note:'قیمت روز را بپرس'},
    materials_note:'بلیت معتبر',accessibility_note:'دسترسی را بررسی کن',safety_notes:[],
  }}));
  assert.match(detail,/href="https:\/\/kouroshmall.com\/" target="_blank" rel="noopener noreferrer"/);
  assert.ok(detail.includes('معرفی محل در مجتمع کورش'));
  assert.ok(detail.includes('قیمت امروز را تأیید نمی‌کند'));
  assert.ok(detail.includes('تهران'));
  assert.ok(!detail.includes('DRAMMA'));
});
