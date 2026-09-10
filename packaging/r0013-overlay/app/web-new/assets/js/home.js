function unwrap(value) { return value && value.success === true && value.data && typeof value.data === 'object' ? value.data : (value || {}); }
async function j(url, opts) {
  const response = await fetch(url, Object.assign({ credentials: 'same-origin', cache: 'no-store' }, opts || {}));
  const raw = await response.text();
  let payload = {};
  if (raw.trim()) {
    try { payload = JSON.parse(raw); }
    catch (_) { throw new Error('Сервер вернул некорректный ответ'); }
  }
  if (response.status === 401) { location.replace('/?v=1.0.0-r1'); throw new Error('Требуется вход'); }
  if (!response.ok || payload.success === false || payload.ok === false) {
    const error = new Error(payload.error?.message || payload.message || 'Ошибка');
    error.code = payload.error?.code || payload.code || '';
    error.status = response.status;
    error.details = payload.error?.details || payload.details || null;
    throw error;
  }
  return payload.data ?? payload;
}
function text(id, value) { const element = document.getElementById(id); if (element) element.textContent = value ?? '—'; }
function button(id, label, enabled) { const element = document.getElementById(id); if (!element) return; if (label) element.textContent = label; element.disabled = enabled !== true; }
function statusBadge(id, label, tone) { const element = document.getElementById(id); if (!element) return; element.textContent = label; element.className = 'interface-status-badge is-' + tone; }
function showError(message) { const element = document.getElementById('homeError'); if (!element) return; element.textContent = message || ''; element.hidden = !message; }
function notify(message, type) { if (window.BROrayUI) window.BROrayUI.toast(message, type); else if (message) alert(message); }
function activeServer(servers) { const id = servers?.activeServerId; return (servers?.servers || []).find(server => server.id === id) || null; }
let xrayCatalog = null;
let xrayBusy = false;

function renderFailover(data) {
  const config = data?.config || {};
  const state = data?.state || {};
  if (config.enabled !== true) {
    text('failover', 'Выключено');
    text('failoverDetail', 'Автоматические проверки выключены. Включите их на странице «Серверы».');
    return;
  }
  const labels = { healthy: 'Сервер работает', degraded: 'Обнаружены ошибки', switched: 'Сервер переключён', 'no-replacement': 'Нет доступной замены' };
  text('failover', labels[state.status] || 'Ожидание первой проверки');
  if (!state.status) text('failoverDetail', 'Настройки сохранены. Автоматическая проверка ещё не выполнялась.');
  else if (state.status === 'healthy') text('failoverDetail', 'Последняя автоматическая проверка успешна. Счётчик ошибок: 0.');
  else if (state.status === 'degraded') text('failoverDetail', 'Ошибок подряд: ' + (state.consecutiveFailures || 0) + ' из ' + (config.failureThreshold || 3) + '.');
  else if (state.status === 'switched') text('failoverDetail', 'Последнее автоматическое переключение выполнено успешно.');
  else text('failoverDetail', 'Порог ошибок достигнут, но подходящий сервер не найден.');
}

async function refreshHome() {
  try {
    showError('');
    const [data, info, failover] = await Promise.all([j('api/home/summary.cgi'), j('api/broray/info.cgi'), j('api/servers/auto-switch-status.cgi')]);
    const server = activeServer(data.servers);
    const id = data.servers?.activeServerId || '';
    text('activeServer', server?.name || id || 'Не выбран');
    text('activeServerId', server && server.name !== id ? id : '');
    const connected = data.connection?.connected === true;
    text('connection', connected ? '● Соединение работает' : '○ Нет соединения');
    text('headerConnection', connected ? 'Подключено' : 'Нет соединения');
    const xray = unwrap(data.xray);
    text('xrayVersion', xray.version || 'Не определена');
    text('xrayState', xray.running ? 'Xray запущен' : 'Xray остановлен');
    text('lightVersion', info.version || 'Не определена');
    text('lightChannel', info.releaseChannel === 'stable' ? 'Стабильный канал' : 'Канал ' + (info.releaseChannel || 'не определён'));
    renderFailover(failover);
    const keenetic = unwrap(data.keenetic);
    const health = keenetic.health || {};
    const facts = health.facts || {};
    const severity = health.severity || keenetic.state || keenetic.status || 'unknown';
    const interfaceName = facts.interfaceName || keenetic.interfaceName || 'Не определён';
    const exists = facts.exists === true || keenetic.exists === true;
    const operational = health.operational === true || keenetic.healthy === true;
    let stateLabel = 'Не проверено';
    let stateTone = 'pending';
    if (severity === 'ok' && operational) { stateLabel = 'Активен'; stateTone = 'active'; }
    else if (severity === 'warning') { stateLabel = 'Требует внимания'; stateTone = 'warning'; }
    else if (severity === 'error' && !exists) { stateLabel = 'Не активен'; stateTone = 'inactive'; }
    else if (severity === 'error') { stateLabel = 'Ошибка'; stateTone = 'error'; }
    text('keeneticInterfaceName', interfaceName);
    statusBadge('keeneticState', stateLabel, stateTone);
    const healthy = severity === 'ok';
    text('keeneticDetail', healthy ? 'Интерфейс Keenetic настроен и связан с активным сервером. Дополнительные действия не требуются.' : 'Нажмите «Настроить» или «Исправить», затем обновите статус.');
    button('keeneticCreateButton', 'Настроить', !healthy);
    button('keeneticRepairButton', healthy ? 'Исправно' : 'Исправить', !healthy);
  } catch (error) { showError(error.message); }
}

async function keeneticAction(action) {
  try {
    showError('');
    await j('api/keenetic/' + action + '.cgi', { method: 'POST' });
    notify(action === 'repair' ? 'Настройки Keenetic исправлены' : 'Настройки Keenetic созданы');
    await refreshHome();
  } catch (error) { showError(error.message); notify(error.message, 'error'); }
}

function xraySelection() {
  const tag = document.getElementById('xrayReleaseSelect')?.value;
  return xrayCatalog?.releases?.find(release => release.tagName === tag) || null;
}

function xrayVersionKey(version) {
  return String(version || '').replace(/^v/, '').split(/[.-]/).slice(0, 3).reduce((key, value) => key * 100 + (Number(value) || 0), 0);
}

function xrayRenderSelection() {
  const selected = xraySelection();
  const status = selected?.compatibility?.status || 'untested';
  const labels = { compatible: 'Проверена с этой сборкой BROray-Light', untested: 'Не проверена с этой сборкой BROray-Light', incompatible: 'Несовместима с этой сборкой BROray-Light' };
  text('xrayCompatibility', selected ? labels[status] || labels.untested : 'Выберите версию.');
  const installed = selected?.version === xrayCatalog?.currentVersion;
  const verb = installed ? 'Переустановить' : 'Установить';
  button('xrayInstallButton', selected ? verb + ' ' + selected.version : 'Установить', !xrayBusy && selected?.available === true && /^[a-f0-9]{64}$/.test(selected.archiveSha256 || '') && status !== 'incompatible');
}

function xrayRenderCatalog() {
  const select = document.getElementById('xrayReleaseSelect');
  if (!select) return;
  const previous = select.value;
  const includePrerelease = document.getElementById('xrayShowPrerelease')?.checked === true;
  const rows = (xrayCatalog?.releases || []).filter(release => !release.prerelease || includePrerelease || release.installed);
  select.replaceChildren();
  for (const release of rows) {
    const option = document.createElement('option');
    option.value = release.tagName;
    option.textContent = release.version + (release.prerelease ? ' — предварительная' : ' — стабильная') +
      (release.installed ? ' (установлена)' : '') + (release.available === false ? ' — нет в каталоге' : '');
    select.appendChild(option);
  }
  const selected = rows.find(release => release.tagName === previous) || rows.find(release => release.installed) || rows[0];
  if (selected) select.value = selected.tagName;
  document.getElementById('xraySelector').hidden = false;
  xrayRenderSelection();
}

async function xrayCheck() {
  if (xrayBusy) return;
  xrayBusy = true;
  try {
    showError('');
    text('xrayUpdate', 'Получение официального списка версий…');
    button('xrayCheckButton', 'Проверка…', false);
    button('xrayInstallButton', 'Проверка…', false);
    xrayCatalog = await j('api/xray/update-check.cgi', { method: 'POST' });
    text('xrayUpdate', 'Установлена ' + xrayCatalog.currentVersion + '. Выберите версию для установки или переустановки.' +
      (xrayCatalog.catalogComplete === false ? ' Каталог получен не полностью.' : ''));
    xrayRenderCatalog();
  } catch (error) {
    xrayCatalog = null;
    document.getElementById('xraySelector').hidden = true;
    text('xrayUpdate', 'Проверка не выполнена: ' + error.message);
    showError(error.message);
  } finally {
    xrayBusy = false;
    button('xrayCheckButton', 'Проверить обновление', true);
    xrayRenderSelection();
  }
}

async function xrayInstall() {
  if (xrayBusy) return;
  const selected = xraySelection();
  if (!selected || selected.available !== true || selected.compatibility?.status === 'incompatible' ||
      !/^[a-f0-9]{64}$/.test(selected.archiveSha256 || '')) return;
  const request = { tag: selected.tagName, currentVersion: xrayCatalog.currentVersion,
    archiveSha256: selected.archiveSha256, allowUntested: false, allowPrerelease: false, allowDowngrade: false };
  if (selected.compatibility?.status !== 'compatible') {
    if (!confirm('Xray ' + selected.version + ' не проверен с этой сборкой BROray-Light. Установить с проверкой запуска и автоматическим откатом при ошибке?')) return;
    request.allowUntested = true;
  }
  if (selected.prerelease) {
    if (!confirm('Выбрана предварительная версия Xray. Она может работать нестабильно. Продолжить?')) return;
    request.allowPrerelease = true;
  }
  if (xrayVersionKey(selected.version) < xrayVersionKey(request.currentVersion)) {
    if (!confirm('Понизить версию Xray с ' + request.currentVersion + ' до ' + selected.version + '?')) return;
    request.allowDowngrade = true;
  }
  if (selected.version === request.currentVersion && !confirm('Переустановить текущую версию Xray ' + selected.version + '?')) return;
  xrayBusy = true;
  const select = document.getElementById('xrayReleaseSelect');
  const prerelease = document.getElementById('xrayShowPrerelease');
  select.disabled = true;
  prerelease.disabled = true;
  try {
    showError('');
    button('xrayCheckButton', 'Проверить обновление', false);
    button('xrayInstallButton', 'Установка…', false);
    text('xrayUpdate', 'Установка Xray ' + selected.version + '. Не закрывайте страницу.');
    await j('api/xray/install.cgi', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request) });
    text('xrayUpdate', 'Xray ' + selected.version + ' установлен.');
    notify('Установка Xray завершена');
    await refreshHome();
  } catch (error) {
    text('xrayUpdate', 'Установка не выполнена: ' + error.message);
    showError(error.message);
    notify(error.message, 'error');
  } finally {
    xrayBusy = false;
    select.disabled = false;
    prerelease.disabled = false;
    button('xrayCheckButton', 'Проверить обновление', true);
    // The installed version may have changed; require a fresh, bound selection.
    xrayCatalog = null;
    document.getElementById('xraySelector').hidden = true;
    button('xrayInstallButton', 'Сначала проверьте версии', false);
  }
}

function lightPublicVersion(version) {
  // Exact approved alias, not a general suffix-stripping rule for future releases.
  return version === '2.0.0-r1' ? '2.0.0' : version;
}

async function lightCheck() {
  try {
    showError(''); text('lightUpdate', 'Проверка…'); button('lightInstallButton', 'Проверка…', false);
    const data = await j('api/broray/update-check.cgi');
    const available = lightPublicVersion(data.availableReleaseId);
    const installed = lightPublicVersion(data.installedReleaseId);
    if (data.updateAvailable === true) { text('lightUpdate', 'Доступна версия ' + (available || 'BROray-Light') + '. Установлена ' + (installed || 'не определена') + '.'); button('lightInstallButton', 'Обновить', true); }
    else { text('lightUpdate', 'Установлена актуальная версия ' + (installed || 'BROray-Light') + '.'); button('lightInstallButton', 'Обновлений нет', false); }
  } catch (error) {
    text('lightUpdate', 'Проверка Stable-канала не выполнена: ' + error.message);
    button('lightInstallButton', 'Обновить', false);
    showError(error.message);
  }
}

async function lightInstall() {
  try {
    showError(''); button('lightInstallButton', 'Обновление…', false); text('lightUpdate', 'Обновление BROray-Light выполняется.');
    await j('api/broray/update-start.cgi', { method: 'POST' }); notify('BROray-Light обновлён'); await refreshHome(); await lightCheck();
  } catch (error) { text('lightUpdate', 'Обновление завершилось ошибкой: ' + error.message); showError(error.message); notify(error.message, 'error'); button('lightInstallButton', 'Обновить', true); }
}

document.addEventListener('DOMContentLoaded', refreshHome);
