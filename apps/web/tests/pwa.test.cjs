const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

function worker({network = async () => new Response('network'), existingKeys = []} = {}) {
  const listeners = {};
  const operations = [];
  const entries = new Map();
  const cache = {
    async addAll(paths) {for (const path of paths) {assert.ok(fs.existsSync('public' + path), `missing precache asset: ${path}`);entries.set(path, new Response(path));}operations.push(['addAll', paths]);},
    async match(request) {return entries.get(typeof request === 'string' ? request : new URL(request.url).pathname)?.clone();}
  };
  const caches = {async open(name) {operations.push(['open', name]);return cache;}, async keys() {return existingKeys;}, async delete(name) {operations.push(['delete', name]);}};
  const self = {location: {origin: 'https://funilo.test'}, clients: {async claim() {}}, async skipWaiting() {}, addEventListener(name, listener) {listeners[name] = listener;}};
  vm.runInNewContext(fs.readFileSync('public/sw.js', 'utf8'), {self, caches, fetch: network, URL, Set, Promise, Response});
  return {operations, entries, async lifecycle(name) {let task;listeners[name]({waitUntil(promise) {task = promise;}});await task;}, async request(path, options = {}) {
    let response;
    const request = {url: new URL(path, self.location.origin).href, method: 'GET', mode: 'cors', ...options};
    listeners.fetch({request, respondWith(promise) {response = promise;}});
    return response ? await response : undefined;
  }};
}

test('offline precache contains only real public static assets', async () => {
  const sw = worker();
  await sw.lifecycle('install');
  assert.ok(sw.entries.has('/offline.html'));
  assert.ok(sw.entries.has('/fonts/Vazirmatn-Regular.ttf'));
  assert.ok([...sw.entries.keys()].every(path => !path.startsWith('/api/') && path !== '/'));
});

test('API, mutations and cross-origin requests bypass the worker and cache entirely', async () => {
  const sw = worker({network: async () => {throw new Error('must not intercept');}});
  for (const [path, options] of [['/api/v1/me', {}], ['/api/v1/auth/csrf', {}], ['/api/docs', {}], ['/', {method: 'POST', mode: 'navigate'}], ['https://other.test/offline.html', {}]]) {
    assert.equal(await sw.request(path, options), undefined);
  }
  assert.equal(sw.operations.length, 0);
});

test('online personalized navigation is network-only and never written to cache', async () => {
  let calls = 0;
  const sw = worker({network: async () => {calls++;return new Response('private account');}});
  const response = await sw.request('/?experience=private-id', {mode: 'navigate'});
  assert.equal(await response.text(), 'private account');
  assert.equal(calls, 1);
  assert.equal(sw.operations.length, 0);
  assert.equal(sw.entries.size, 0);
});

test('offline navigation returns the generic page without personal data', async () => {
  const sw = worker({network: async () => {throw new TypeError('offline');}});
  await sw.lifecycle('install');
  const response = await sw.request('/?slate=private-id', {mode: 'navigate'});
  assert.equal(await response.text(), '/offline.html');
  assert.ok(![...sw.entries.keys()].some(key => key.includes('private-id')));
});

test('activation removes only obsolete Funilo static caches', async () => {
  const sw = worker({existingKeys: ['other-app', 'funilo-static-v0', 'funilo-static-v1']});
  await sw.lifecycle('activate');
  assert.deepEqual(sw.operations.filter(op => op[0] === 'delete'), [['delete', 'funilo-static-v0']]);
});

test('evicted offline cache still produces a valid generic response', async () => {
  const sw = worker({network: async () => {throw new TypeError('offline');}});
  const response = await sw.request('/?experience=private-id', {mode: 'navigate'});
  assert.equal(response.status, 503);
  assert.match(response.headers.get('Content-Type'), /text\/html/);
  const body = await response.text();
  assert.ok(body.includes('lang="fa"'));
  assert.ok(!body.includes('private-id'));
});

test('manifest supplies standalone RTL metadata and valid raster installation icons', () => {
  const source = fs.readFileSync('app/manifest.ts', 'utf8');
  const exports = {};
  vm.runInNewContext(ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText, {exports});
  const manifest = exports.default();
  assert.equal(manifest.display, 'standalone');
  assert.equal(manifest.dir, 'rtl');
  assert.equal(manifest.lang, 'fa');
  assert.equal(manifest.start_url, '/');
  assert.equal(manifest.scope, '/');
  for (const icon of manifest.icons) {
    const png = fs.readFileSync('public' + icon.src);
    assert.equal(png.subarray(1, 4).toString(), 'PNG');
    const [width, height] = icon.sizes.split('x').map(Number);
    assert.equal(png.readUInt32BE(16), width);
    assert.equal(png.readUInt32BE(20), height);
  }
  assert.ok(manifest.icons.some(icon => icon.purpose === 'maskable'));
});
