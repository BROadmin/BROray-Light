function normalizedFailover(config) {
  return {
    enabled: config.enabled === true,
    failureThreshold: Number(config.failureThreshold || 3),
    cooldownSeconds: Number(config.cooldownSeconds ?? 600),
    orderedServerIds: [...(config.orderedServerIds || [])],
    excludedServerIds: [...(config.excludedServerIds || [])].sort()
  };
}

function currentFailoverConfig() {
  const cards = [...document.querySelectorAll('#servers > [data-server-id]')];
  return normalizedFailover({
    enabled: document.getElementById('failoverEnabled').checked,
    failureThreshold: document.getElementById('failureThreshold').value,
    cooldownSeconds: document.getElementById('cooldownSeconds').value,
    orderedServerIds: cards.map(card => card.dataset.serverId),
    excludedServerIds: cards.filter(card => card.querySelector('[data-exclude]')?.checked).map(card => card.dataset.serverId)
  });
}

async function loadFailoverConfig() {
  try {
    const data = await api('api/servers/auto-switch-status.cgi');
    const config = data.config || {};
    window.BROrayLightFailoverConfig = config;
    window.BROrayLightFailoverState = data.state || {};
    document.getElementById('failoverEnabled').checked = config.enabled === true;
    document.getElementById('failureThreshold').value = config.failureThreshold || 3;
    document.getElementById('cooldownSeconds').value = config.cooldownSeconds ?? 600;
    renderFailoverStatus(config, window.BROrayLightFailoverState);
  } catch (error) {
    window.BROrayLightFailoverConfig = {};
    window.BROrayLightFailoverState = {};
    renderFailoverStatus({}, {});
    notify(error.message, 'error');
  }
}

function renderFailoverStatus(config, state) {
  const element = document.getElementById('failoverStatus');
  if (!element) return;
  if (config.enabled !== true) {
    element.textContent = 'Выключено — автоматические проверки не выполняются';
    return;
  }
  const labels = {
    healthy: 'Включено — активный сервер работает',
    degraded: 'Включено — обнаружены ошибки соединения',
    switched: 'Включено — сервер автоматически переключён',
    'no-replacement': 'Включено — доступная замена не найдена'
  };
  element.textContent = labels[state.status] || 'Включено — ожидается первая автоматическая проверка';
}

function establishFailoverBaseline() {
  window.BROrayLightFailoverSaved = JSON.stringify(currentFailoverConfig());
  renderFailoverStatus(window.BROrayLightFailoverConfig || {}, window.BROrayLightFailoverState || {});
}

function updateFailoverDirtyState() {
  const current = JSON.stringify(currentFailoverConfig());
  if (current === window.BROrayLightFailoverSaved) {
    renderFailoverStatus(window.BROrayLightFailoverConfig || {}, window.BROrayLightFailoverState || {});
  } else {
    document.getElementById('failoverStatus').textContent = 'Есть несохранённые изменения';
  }
}

function refreshMoveButtons() {
  const cards = [...document.querySelectorAll('#servers > [data-server-id]')];
  cards.forEach((card, index) => {
    const up = card.querySelector('[data-a="up"]');
    const down = card.querySelector('[data-a="down"]');
    if (up) up.disabled = index === 0;
    if (down) down.disabled = index === cards.length - 1;
  });
}

function moveServerCard(card, delta) {
  const box = document.getElementById('servers');
  if (delta < 0 && card.previousElementSibling) box.insertBefore(card, card.previousElementSibling);
  else if (delta > 0 && card.nextElementSibling) box.insertBefore(card.nextElementSibling, card);
  else return;
  refreshMoveButtons();
  updateFailoverDirtyState();
}

async function saveFailover() {
  const body = currentFailoverConfig();
  try {
    const saved = await api('api/servers/auto-switch-save.cgi', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    });
    window.BROrayLightFailoverConfig = saved || body;
    window.BROrayLightFailoverState = {};
    window.BROrayLightFailoverSaved = JSON.stringify(body);
    renderFailoverStatus(window.BROrayLightFailoverConfig, {});
    notify(body.enabled ? 'Автопереключение включено' : 'Автопереключение выключено');
  } catch (error) {
    notify(error.message, 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  for (const id of ['failoverEnabled', 'failureThreshold', 'cooldownSeconds']) {
    document.getElementById(id)?.addEventListener('change', updateFailoverDirtyState);
  }
});
