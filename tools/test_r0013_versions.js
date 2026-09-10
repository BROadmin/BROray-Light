'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../packaging/r0013-overlay/app/web-new/assets/js/home.js'), 'utf8');
const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, { hidden: true, disabled: false, textContent: '' });
  return elements.get(id);
};
let update = { installedReleaseId: '1.0.0-r1', availableReleaseId: '2.0.0-r1', updateAvailable: true };
let fail = false;
const responses = {
  'api/home/summary.cgi': { servers: {}, xray: {}, keenetic: {} },
  'api/broray/info.cgi': { version: '2.0.0', releaseId: '2.0.0-r1', releaseChannel: 'stable' },
  'api/servers/auto-switch-status.cgi': {}
};
const context = vm.createContext({
  document: { getElementById: element, addEventListener() {} },
  window: {}, location: { replace() {} },
  fetch: async url => ({ ok: !fail, status: fail ? 500 : 200,
    text: async () => JSON.stringify(fail ? { success: false, message: 'Fixture refusal' } :
      { success: true, data: url.endsWith('update-check.cgi') ? update : responses[url] }) })
});
vm.runInContext(source, context);
(async () => {
  assert.equal(context.lightPublicVersion('2.0.0-r1'), '2.0.0');
  assert.equal(context.lightPublicVersion('1.0.0-r1'), '1.0.0-r1');
  assert.equal(context.lightPublicVersion('2.0.0-r2'), '2.0.0-r2');
  await context.refreshHome();
  assert.equal(element('lightVersion').textContent, '2.0.0');
  await context.lightCheck();
  assert.equal(element('lightUpdate').textContent, 'Доступна версия 2.0.0. Установлена 1.0.0-r1.');
  assert.equal(element('lightInstallButton').disabled, false);
  update = { installedReleaseId: '2.0.0-r1', availableReleaseId: '2.0.0-r1', updateAvailable: false };
  await context.lightCheck();
  assert.equal(element('lightUpdate').textContent, 'Установлена актуальная версия 2.0.0.');
  assert.equal(element('lightInstallButton').disabled, true);
  fail = true;
  await context.lightCheck();
  assert.equal(element('lightInstallButton').disabled, true);
  assert.match(element('lightUpdate').textContent, /Fixture refusal/);
  console.log(JSON.stringify({ stage: 'R0013', revision: 'p13', status: 'PASS',
    tests: ['approved-exact-alias', 'old-version-preserved', 'future-version-not-guessed',
      'home-public-version', 'available-update-public-version', 'equal-version-disabled', 'check-failure-disabled'] }));
})().catch(error => { console.error(error); process.exitCode = 1; });
