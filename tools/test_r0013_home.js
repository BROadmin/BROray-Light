/* The actual Home JS, with only DOM/HTTP/user-confirmation boundaries faked. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../packaging/r0013-overlay/app/web-new/assets/js/home.js'), 'utf8');
class Element {
  constructor() { this.value = ''; this.checked = false; this.hidden = true; this.disabled = false; this.children = []; this.textContent = ''; }
  replaceChildren() { this.children = []; this.value = ''; }
  appendChild(child) { this.children.push(child); if (!this.value) this.value = child.value; }
}
const elements = new Map();
const element = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
let requests = [], confirmations = [], confirmValue = true, apiFailure = false;
let releases = [
  { tagName: 'v26.7.28', version: '26.7.28', installed: true, available: true, prerelease: false, archiveSha256: 'a'.repeat(64), compatibility: { status: 'compatible' } },
  { tagName: 'v26.9.9', version: '26.9.9', available: true, prerelease: false, archiveSha256: 'b'.repeat(64), compatibility: { status: 'untested' } },
  { tagName: 'v26.9.10-beta.1', version: '26.9.10-beta.1', available: true, prerelease: true, archiveSha256: 'c'.repeat(64), compatibility: { status: 'untested' } },
  { tagName: 'v26.6.27', version: '26.6.27', available: true, prerelease: false, archiveSha256: 'd'.repeat(64), compatibility: { status: 'incompatible' } }
];
const context = vm.createContext({
  document: { getElementById: element, createElement: () => new Element(), addEventListener() {} },
  window: {}, alert() {}, confirm(message) { confirmations.push(message); return confirmValue; },
  location: { replace() {} },
  fetch: async (url, opts) => {
    requests.push({ url, opts });
    const success = !apiFailure;
    const data = url.endsWith('update-check.cgi') ? { currentVersion: '26.7.28', catalogComplete: true, releases } : { success: true };
    return { ok: success, status: success ? 200 : 409, text: async () => JSON.stringify(success ? { success, data } : { success: false, error: { message: 'Fixture refusal' } }) };
  }
});
vm.runInContext(source, context);
vm.runInContext('refreshHome=async()=>{};', context);
const records = [];
function pass(name) { records.push({ test: name, status: 'PASS' }); }
async function checkCatalog() { apiFailure = false; await context.xrayCheck(); }
async function main() {
  await checkCatalog();
  assert.equal(element('xrayReleaseSelect').children.length, 3);
  assert.equal(element('xrayReleaseSelect').value, 'v26.7.28');
  assert.equal(element('xrayInstallButton').disabled, false);
  assert.match(element('xrayInstallButton').textContent, /Переустановить/);
  pass('installed-stable-visible-and-reinstall-enabled');
  element('xrayShowPrerelease').checked = true;
  context.xrayRenderCatalog();
  assert.equal(element('xrayReleaseSelect').children.length, 4);
  pass('prerelease-toggle');

  element('xrayReleaseSelect').value = 'v26.6.27';
  context.xrayRenderSelection();
  assert.equal(element('xrayInstallButton').disabled, true);
  const before = requests.length;
  await context.xrayInstall();
  assert.equal(requests.length, before);
  pass('incompatible-no-install-request');

  element('xrayReleaseSelect').value = 'v26.9.9';
  context.xrayRenderSelection();
  confirmValue = false;
  await context.xrayInstall();
  assert.equal(requests.length, before);
  pass('declined-consent-no-install-request');

  confirmValue = true;
  element('xrayReleaseSelect').value = 'v26.9.10-beta.1';
  await context.xrayInstall();
  let request = requests.at(-1);
  assert.equal(request.url, 'api/xray/install.cgi');
  let payload = JSON.parse(request.opts.body);
  assert.deepEqual(payload, { tag: 'v26.9.10-beta.1', currentVersion: '26.7.28', archiveSha256: 'c'.repeat(64), allowUntested: true, allowPrerelease: true, allowDowngrade: false });
  assert.equal(request.opts.credentials, 'same-origin');
  assert.equal(element('xrayInstallButton').disabled, true);
  assert.equal(element('xraySelector').hidden, true);
  pass('bound-digest-and-separate-prerelease-consent');

  await checkCatalog();
  element('xrayReleaseSelect').value = 'v26.7.28';
  confirmations = [];
  await context.xrayInstall();
  assert.equal(JSON.parse(requests.at(-1).opts.body).tag, 'v26.7.28');
  assert.equal(confirmations.length, 1);
  assert.match(confirmations[0], /Переустановить/);
  pass('same-version-reinstall-confirmation');

  releases[3].compatibility.status = 'untested';
  await checkCatalog();
  element('xrayReleaseSelect').value = 'v26.6.27';
  await context.xrayInstall();
  payload = JSON.parse(requests.at(-1).opts.body);
  assert.equal(payload.allowDowngrade, true);
  assert.equal(payload.allowUntested, true);
  pass('separate-downgrade-consent');

  await checkCatalog();
  apiFailure = true;
  await context.xrayInstall();
  assert.equal(element('homeError').hidden, false);
  assert.match(element('homeError').textContent, /Fixture refusal/);
  assert.equal(element('xrayInstallButton').disabled, true);
  pass('server-refusal-visible-no-stale-retry');

  await context.xrayCheck();
  assert.equal(element('xraySelector').hidden, true);
  assert.equal(element('xrayInstallButton').disabled, true);
  assert.equal(element('xrayCheckButton').disabled, false);
  pass('catalog-error-fails-closed');
  console.log(JSON.stringify({ stage: 'R0013', revision: 'p8-linux-catalog-and-ui-tests', status: 'PASS', browserLayoutTested: false, tests: records }, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
