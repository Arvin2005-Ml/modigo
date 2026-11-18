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
