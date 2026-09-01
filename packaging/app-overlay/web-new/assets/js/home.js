function unwrap(value) { return value && value.success === true && value.data && typeof value.data === 'object' ? value.data : (value || {}); }
async function j(url, opts) {
  const response = await fetch(url, Object.assign({ credentials: 'same-origin', cache: 'no-store' }, opts || {}));
  const raw = await response.text();
  let payload = {};
  if (raw.trim()) {
    try { payload = JSON.parse(raw); }
    catch (_) { throw new Error('Сервер вернул некорректный ответ'); }
  }
  if (response.status === 401) { location.replace('/?v=0.1.0-r0009c19'); throw new Error('Требуется вход'); }
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
function showError(message) { const element = document.getElementById('homeError'); if (!element) return; element.textContent = message || ''; element.hidden = !message; }
function notify(message, type) { if (window.BROrayUI) window.BROrayUI.toast(message, type); else if (message) alert(message); }
function activeServer(servers) { const id = servers?.activeServerId; return (servers?.servers || []).find(server => server.id === id) || null; }
let xrayInstallMode = 'update';

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
    const internalCandidate = /r0009|0\.1\.0-r9/i.test((info.candidateId || '') + ' ' + (info.version || ''));
    text('lightChannel', internalCandidate ? 'Внутренняя сборка R0009' : (info.releaseChannel === 'stable' ? 'Стабильный канал' : 'Канал ' + (info.releaseChannel || 'не определён')));
    renderFailover(failover);
    const keenetic = unwrap(data.keenetic);
    const severity = keenetic.health?.severity || keenetic.state || keenetic.status || 'unknown';
    const labels = { ok: 'Готов', warning: 'Требует внимания', error: 'Требует настройки', unknown: 'Не проверено' };
    text('keeneticState', labels[severity] || severity);
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

async function xrayCheck() {
  try {
    showError(''); text('xrayUpdate', 'Проверка…'); button('xrayInstallButton', 'Проверка…', false);
    const data = await j('api/xray/update-check.cgi', { method: 'POST' });
    if (data.updateAvailable) {
      xrayInstallMode = 'update'; text('xrayUpdate', 'Доступна версия ' + data.latestVersion + '. Установлена ' + data.currentVersion + '.'); button('xrayInstallButton', 'Обновить до ' + data.latestVersion, true);
    } else if (data.temporaryStorage?.reinstallAllowed === true) {
      xrayInstallMode = 'reinstall'; text('xrayUpdate', 'Установлена актуальная версия ' + data.currentVersion + '. Её можно переустановить.'); button('xrayInstallButton', 'Переустановить ' + data.currentVersion, true);
    } else {
      text('xrayUpdate', 'Установлена актуальная версия ' + (data.currentVersion || 'Xray') + '.'); button('xrayInstallButton', 'Переустановка недоступна', false);
    }
  } catch (error) { text('xrayUpdate', 'Проверка не выполнена: ' + error.message); button('xrayInstallButton', 'Установить', false); showError(error.message); }
}

async function xrayInstall() {
  const mode = xrayInstallMode;
  const label = mode === 'reinstall' ? 'Переустановка' : 'Обновление';
  try {
    showError(''); button('xrayInstallButton', label + '…', false); text('xrayUpdate', label + ' Xray выполняется. Не закрывайте страницу.');
    await j('api/xray/update.cgi', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }) });
    text('xrayUpdate', label + ' завершена успешно.'); notify(label + ' Xray завершена'); await refreshHome(); await xrayCheck();
  } catch (error) { text('xrayUpdate', label + ' завершилась ошибкой: ' + error.message); showError(error.message); notify(error.message, 'error'); await xrayCheck(); }
}

async function lightCheck() {
  try {
    showError(''); text('lightUpdate', 'Проверка…'); button('lightInstallButton', 'Проверка…', false);
    const data = await j('api/broray/update-check.cgi');
    if (data.updateAvailable === true) { text('lightUpdate', 'Доступна версия ' + (data.availableReleaseId || 'BROray-Light') + '. Установлена ' + (data.installedReleaseId || 'не определена') + '.'); button('lightInstallButton', 'Обновить', true); }
    else { text('lightUpdate', 'Установлена актуальная версия ' + (data.installedReleaseId || 'BROray-Light') + '.'); button('lightInstallButton', 'Обновлений нет', false); }
  } catch (error) {
    const internal = error.code === 'UPDATE_CHECK_FAILED';
    text('lightUpdate', internal ? 'Внутренняя сборка R0009: публичный канал обновлений пока не настроен.' : 'Проверка недоступна: ' + error.message);
    button('lightInstallButton', 'Обновить', false);
    if (!internal) showError(error.message);
  }
}

async function lightInstall() {
  try {
    showError(''); button('lightInstallButton', 'Обновление…', false); text('lightUpdate', 'Обновление BROray-Light выполняется.');
    await j('api/broray/update-start.cgi', { method: 'POST' }); notify('BROray-Light обновлён'); await refreshHome(); await lightCheck();
  } catch (error) { text('lightUpdate', 'Обновление завершилось ошибкой: ' + error.message); showError(error.message); notify(error.message, 'error'); button('lightInstallButton', 'Обновить', true); }
}

document.addEventListener('DOMContentLoaded', refreshHome);
