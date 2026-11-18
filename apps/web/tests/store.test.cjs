const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const {renderToString} = require('react-dom/server');

// Exercise the real store, middleware and client without contacting a backend.
function loadApp(fetch = async () => { throw new Error('Unexpected request'); }) {
  const cache = new Map();
  function load(filename) {
    filename = path.resolve(filename);
    if (cache.has(filename)) return cache.get(filename).exports;
    const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      fileName: filename,
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.ReactJSX,
        esModuleInterop: true,
      },
    }).outputText;
    const loaded = {exports: {}};
    cache.set(filename, loaded);
    const localRequire = name => {
      if (!name.startsWith('.') && !name.startsWith('@/')) return require(name);
      const base = name.startsWith('@/')
        ? path.resolve(name.slice(2))
        : path.resolve(path.dirname(filename), name);
      const target = [base + '.ts', base + '.tsx', path.join(base, 'index.ts')]
        .find(candidate => fs.existsSync(candidate));
      if (!target) throw new Error('Missing application module: ' + name);
      return load(target);
    };
    vm.runInNewContext(code, {
      module: loaded, exports: loaded.exports, require: localRequire,
      fetch, Response, crypto: require('node:crypto').webcrypto,
      Intl, Map, setTimeout, clearTimeout, process,
    }, {filename});
    return loaded.exports;
  }
  return load;
}

const user = {
  id: 'user-1', email: 'test@example.com', display_name: 'تست',
  role: 'user', timezone: 'Asia/Tehran',
};

function setup(t, fetch) {
  const load = loadApp(fetch);
  const {makeStore} = load('lib/store/store.ts');
  const {apiSlice} = load('lib/store/api/apiSlice.ts');
  const {createApiClient} = load('lib/store/api/apiClient.ts');
  const store = makeStore();
  t.after(() => store.dispatch(apiSlice.util.resetApiState()));
  return {load, makeStore, apiSlice, store, client: createApiClient(store.dispatch)};
}

test('each store isolates authentication and API state', t => {
  const {load, makeStore, store} = setup(t);
  const second = makeStore();
  const {setUser, clearUser} = load('lib/store/slices/authSlice.ts');
  store.dispatch(setUser(user));
  assert.equal(store.getState().auth.user.id, user.id);
  assert.equal(second.getState().auth.user, null);
  assert.notEqual(store.getState().api, second.getState().api);
  store.dispatch(clearUser());
  assert.equal(store.getState().auth.user, null);
});

test('the provider renders the application with its real Redux hooks', () => {
  const load = loadApp();
  const StoreProvider = load('app/StoreProviders.tsx').default;
  const Funilo = load('components/Funilo.tsx').default;
  const html = renderToString(React.createElement(StoreProvider, null, React.createElement(Funilo)));
  assert.match(html, /id="main"/);
  assert.match(html, /role="status"/);
});

test('imperative queries use the API middleware and refresh cached data', async t => {
  let requests = 0;
  const {apiSlice, store, client} = setup(t, async url => {
    assert.equal(url, '/api/v1/me');
    return Response.json({...user, display_name: `request-${++requests}`});
  });
  assert.equal((await client.getMe()).display_name, 'request-1');
  assert.equal((await client.getMe()).display_name, 'request-2');
  assert.equal(apiSlice.endpoints.getMe.select()(store.getState()).data.display_name, 'request-2');
  store.dispatch(apiSlice.util.resetApiState());
  assert.equal(apiSlice.endpoints.getMe.select()(store.getState()).data, undefined);
});

test('Redux mutations keep CSRF and idempotency headers and accept empty responses', async t => {
  const calls = [];
  const {client} = setup(t, async (url, options) => {
    calls.push({url, ...options});
    if (url.endsWith('/auth/csrf')) return Response.json({csrf_token: 'test-token'});
    if (url.endsWith('/check-ins')) return Response.json({id: 'check-1'}, {status: 201});
    return new Response(null, {status: 204});
  });
  assert.equal((await client.createCheckIn({available_minutes: 30})).id, 'check-1');
  assert.equal(calls[1].method, 'POST');
  assert.equal(calls[1].headers['X-CSRF-Token'], 'test-token');
  assert.ok(calls[1].headers['Idempotency-Key']);
  assert.equal(JSON.parse(calls[1].body).available_minutes, 30);
  assert.equal(await client.saveActivity('activity-1'), null);
  assert.equal(calls[2].url, '/api/v1/saved/activity-1');
  assert.equal(calls[2].method, 'PUT');
});

test('Redux failures retain API error codes, status and validation fields', async t => {
  const {load, client} = setup(t, async () => Response.json({error: {
    code: 'AUTH_REQUIRED', message: 'دوباره وارد شو.', fields: {session: 'expired'},
  }}, {status: 401}));
  const {ApiError} = load('lib/api.ts');
  await assert.rejects(client.getMe(), error =>
    error instanceof ApiError && error.status === 401 &&
    error.code === 'AUTH_REQUIRED' && error.fields.session === 'expired');
});
