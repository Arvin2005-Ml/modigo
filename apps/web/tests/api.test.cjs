const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

function client(fetch) {
  const source = fs.readFileSync('lib/api.ts', 'utf8');
  const code = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
  const exports = {};
  vm.runInNewContext(code, {exports, fetch, Response, crypto: require('node:crypto').webcrypto, Intl, Map});
  return exports;
}

test('proxy text on signup becomes a readable connection error', async () => {
  const responses = [new Response('{"csrf_token":"token"}', {status: 200}),
    new Response('Bad Gateway', {status: 502})];
  const api = client(async () => responses.shift());
  await assert.rejects(api.api('/auth/signup', 'POST', {}), error =>
    error.code === 'NETWORK' && error.status === 502 && !error.message.includes('JSON'));
});

test('network and malformed CSRF responses produce readable errors', async () => {
  for (const fetch of [async () => {throw new TypeError('fetch failed');},
                       async () => new Response('<html>error</html>', {status: 200})]) {
    const api = client(fetch);
    await assert.rejects(api.refreshCsrf(), error => error.code === 'NETWORK' && !error.message.includes('JSON'));
  }
});

test('JSON errors from API keep their code and message', async () => {
  const api = client(async () => new Response(JSON.stringify({error: {code: 'FORBIDDEN', message: 'اجازه نداری'}}), {status: 403}));
  await assert.rejects(api.api('/admin/activities'), error => error.code === 'FORBIDDEN' && error.message === 'اجازه نداری');
});

test('stale CSRF retries once with a fresh token and the same idempotency key', async () => {
  const requests = [];
  let calls = 0;
  const api = client(async (path, options) => {
    requests.push({path, headers: {...options.headers}});
    calls++;
    if (calls === 1) return new Response('{"csrf_token":"old"}', {status: 200});
    if (calls === 2) return new Response('{"error":{"code":"CSRF_FAILED"}}', {status: 403});
    if (calls === 3) return new Response('{"csrf_token":"new"}', {status: 200});
    return new Response('{"ok":true}', {status: 200});
  });
  const result = await api.api('/check-ins', 'POST', {test: true});
  assert.equal(result.ok, true);
  assert.equal(calls, 4);
  assert.equal(requests[1].headers['X-CSRF-Token'], 'old');
  assert.equal(requests[3].headers['X-CSRF-Token'], 'new');
  assert.equal(requests[1].headers['Idempotency-Key'], requests[3].headers['Idempotency-Key']);
});

test('CSRF rejection after refresh does not retry indefinitely', async () => {
  let calls = 0;
  const api = client(async path => {
    calls++;
    if (path.endsWith('/csrf')) return new Response('{"csrf_token":"token"}', {status: 200});
    return new Response('{"error":{"code":"CSRF_FAILED","message":"درخواست معتبر نیست"}}', {status: 403});
  });
  await assert.rejects(api.api('/auth/signup', 'POST', {}), error => error.code === 'CSRF_FAILED');
  assert.equal(calls, 4);
});
