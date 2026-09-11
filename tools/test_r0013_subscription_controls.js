'use strict';
// Actual prepared subscriptions.js; explicit minimal DOM/HTTP/confirm fixtures.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const loaded = cp.spawnSync(process.env.R0013_PYTHON || 'python3', ['-B', '-c',
  "import sys;sys.path.insert(0,'tools');from build_r0013_release import prepared_app;sys.stdout.buffer.write(prepared_app()['web-new/assets/js/subscriptions.js'][0])"], {cwd: root});
if (loaded.status !== 0) throw new Error(loaded.stderr.toString());
const source = loaded.stdout.toString('utf8');
const resultPath = process.argv[2];
const records = [];
let requests = [], created = [], confirmValue = false, apiFailure = false, messages = [];
class Element {
  constructor() { this.listeners = {}; this.children = []; this.selected = new Map(); this.dataset = {}; this.disabled = false; this.value = ''; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  append(...items) { this.children.push(...items); }
  appendChild(item) { this.children.push(item); }
  querySelector(selector) { if (!this.selected.has(selector)) this.selected.set(selector, new Element()); return this.selected.get(selector); }
  focus() {}
}
const box = new Element();
const context = vm.createContext({
  document: { getElementById: () => box, createElement: () => { const e = new Element(); created.push(e); return e; }, addEventListener() {} },
  window: { BROrayUI: { toast(message, type) { messages.push({message, type}); } } }, location: { replace() {} }, confirm: () => confirmValue,
  fetch: async (url, options) => { requests.push({url, options}); return {ok: !apiFailure, status: apiFailure ? 409 : 200,
    text: async () => JSON.stringify(apiFailure ? {success: false, error: {message: 'Fixture refusal'}} :
      {success: true, data: [{id: 'sub-fixture', name: 'Fixture subscription', autoUpdateEnabled: false, updateIntervalMinutes: 360}]})}; }
});
vm.runInContext(source, context);
async function main() {
  let failed = false;
  let name = 'subscription-delete-cancel-restores-clickability';
  try {
    await context.loadSubs();
    const actions = created.find(e => e.className === 'row actions subscription-actions');
    assert.ok(actions?.listeners.click);
    const button = {dataset: {a: 'delete'}, disabled: false};
    const count = requests.length;
    await actions.listeners.click({target: button});
    assert.equal(requests.length, count, 'Declined deletion made a request');
    assert.equal(button.disabled, false, 'Declined deletion left the button disabled');
    records.push({name, status: 'PASS', noDeleteRequest: true, buttonEnabled: true});
    for (const action of ['delete', 'refresh']) {
      for (const refused of [false, true]) {
        name = 'subscription-' + action + (refused ? '-http-refusal' : '-success');
        confirmValue = true;
        apiFailure = refused;
        const target = {dataset: {a: action}, disabled: false};
        const begin = requests.length;
        const click = actions.listeners.click({target});
        assert.equal(target.disabled, true, 'Button not locked during request');
        await click;
        assert.equal(target.disabled, false, 'Button remained disabled after response');
        const post = requests.slice(begin).filter(r => r.options?.method === 'POST');
        assert.equal(post.length, 1);
        assert.equal(post[0].url, 'api/subscriptions/' + action + '.cgi?id=sub-fixture');
        assert.equal(post[0].options.credentials, 'same-origin');
        assert.equal(post[0].options.body, '{}');
        if (refused) assert.deepEqual(messages.at(-1), {message: 'Fixture refusal', type: 'error'});
        else assert.equal(requests.at(-1).url, 'api/subscriptions/list.cgi');
        records.push({name, status: 'PASS', exactIdAndPost: true, buttonEnabled: true});
      }
    }
  } catch (error) { failed = true; records.push({name, status: 'FAIL', error: error.message}); }
  const report = {stage: 'R0013', revision: 'p57-subscription-action-button-finally',
    status: failed ? 'FAIL_FIRST_ERROR' : 'PASS_BOUNDED_CONTROL', candidateReady: false,
    sourceSha256: crypto.createHash('sha256').update(loaded.stdout).digest('hex'),
    mockedBoundaries: ['DOM', 'HTTP', 'confirm'], tests: records};
  const payload = JSON.stringify(report, null, 2) + '\n';
  if (resultPath) fs.writeFileSync(resultPath, payload);
  console.log(payload);
  process.exitCode = failed ? 1 : 0;
}
main().catch(error => { console.error(error); process.exitCode = 1; });
