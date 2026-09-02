async function api(url, opts) {
  const response = await fetch(url, Object.assign({ credentials: 'same-origin', cache: 'no-store' }, opts || {}));
  const raw = await response.text();
  let payload = {};
  if (raw.trim()) {
    try { payload = JSON.parse(raw); }
    catch (_) { throw new Error('Сервер вернул некорректный ответ'); }
  }
  if (response.status === 401) {
    location.replace('/?v=1.0.0-r2');
    throw new Error('Требуется вход');
  }
  if (!response.ok || payload.success === false || payload.ok === false) {
    throw new Error(payload.error?.message || payload.message || 'Ошибка');
  }
  return payload.data ?? payload;
}

function notify(message, type) {
  if (window.BROrayUI) window.BROrayUI.toast(message, type);
  else alert(message);
}

function checkText(check) {
  if (!check) return { className: '', text: 'Проверка ещё не выполнялась' };
  const when = check.checkedAt ? ' · ' + check.checkedAt : '';
  const latency = Number.isFinite(check.latencyMs) ? ' · ' + check.latencyMs + ' мс' : '';
  if (check.success === true) {
    const http = Number.isFinite(check.httpStatus) ? ' · HTTP ' + check.httpStatus : '';
    return { className: ' is-success', text: '● Сервер доступен' + http + latency + when };
  }
  return { className: ' is-error', text: '○ Сервер недоступен · ' + (check.error || check.stage || 'ошибка проверки') + when };
}

async function loadServers() {
  if (!window.BROrayLightFailoverConfig) await loadFailoverConfig();
  const data = await api('api/servers/summary.cgi');
  const config = window.BROrayLightFailoverConfig || {};
  const order = new Map((config.orderedServerIds || []).map((id, index) => [id, index]));
  const servers = [...(data.servers || [])].sort((a, b) => (order.get(a.id) ?? 99999) - (order.get(b.id) ?? 99999));
  const excluded = new Set(config.excludedServerIds || []);
  const box = document.getElementById('servers');
  box.innerHTML = '';

  for (const server of servers) {
    const row = document.createElement('section');
    row.className = 'card server-card' + (server.active ? ' is-active' : '');
    row.dataset.serverId = server.id;

    const title = document.createElement('div');
    title.className = 'server-title';
    const name = document.createElement('strong');
    name.textContent = server.name || server.id;
    title.appendChild(name);
    if (server.active) {
      const badge = document.createElement('span');
      badge.className = 'badge badge-success';
      badge.textContent = 'Активен';
      title.appendChild(badge);
    }

    const meta = document.createElement('div');
    meta.className = 'muted';
    meta.textContent = server.address + ':' + server.port + ' · VLESS · ' + (server.network || 'raw') + ' / ' + (server.security || 'none');

    const result = checkText(server.lastCheck);
    const checkResult = document.createElement('div');
    checkResult.className = 'server-check-result' + result.className;
    checkResult.textContent = result.text;

    const exclude = document.createElement('label');
    exclude.className = 'check-line muted';
    exclude.innerHTML = '<input data-exclude type="checkbox" ' + (excluded.has(server.id) ? 'checked' : '') + '> Не использовать в автопереключении';
    exclude.addEventListener('change', updateFailoverDirtyState);

    const actions = document.createElement('div');
    actions.className = 'row actions';
    actions.innerHTML = '<button class="icon-button secondary" data-a="up" aria-label="Переместить выше" title="Переместить выше">↑</button><button class="icon-button secondary" data-a="down" aria-label="Переместить ниже" title="Переместить ниже">↓</button><button class="secondary" data-a="check">Проверить</button><button data-a="activate" ' + (server.active ? 'disabled' : '') + '>' + (server.active ? 'Активен' : 'Активировать') + '</button><button class="danger-button" data-a="delete">Удалить</button>';
    actions.addEventListener('click', async event => {
      const action = event.target.dataset.a;
      if (!action || event.target.disabled) return;
      if (action === 'up') { moveServerCard(row, -1); return; }
      if (action === 'down') { moveServerCard(row, 1); return; }
      if (action === 'delete' && !confirm('Удалить сервер «' + (server.name || server.id) + '»?')) return;
      try {
        event.target.disabled = true;
        const endpoint = { check: 'check.cgi', activate: 'activate.cgi', delete: 'delete.cgi' }[action];
        const reply = await api('api/servers/' + endpoint, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: server.id, serverId: server.id })
        });
        if (action === 'check') {
          const checked = reply.lastCheck || reply;
          notify(checked.success === false ? 'Сервер недоступен' : 'Сервер доступен', checked.success === false ? 'error' : undefined);
        } else notify(action === 'activate' ? 'Сервер активирован' : 'Сервер удалён');
        await loadServers();
      } catch (error) {
        event.target.disabled = false;
        notify(error.message, 'error');
      }
    });
    row.append(title, meta, checkResult, exclude, actions);
    box.appendChild(row);
  }

  if (!servers.length) {
    box.innerHTML = '<section class="card empty-state"><strong>Серверов пока нет</strong><span class="muted">Добавьте VLESS-ссылку или импортируйте подписку.</span></section>';
  }
  establishFailoverBaseline();
  refreshMoveButtons();
}

async function importServer() {
  const uri = document.getElementById('uri').value.trim();
  const importButton = document.getElementById('importServerButton');
  if (!uri) { notify('Вставьте VLESS-ссылку', 'error'); return; }
  try {
    importButton.disabled = true;
    await api('api/servers/import.cgi', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ uri })
    });
    document.getElementById('uri').value = '';
    notify('Сервер добавлен');
    await loadServers();
  } catch (error) {
    notify(error.message, 'error');
  } finally {
    importButton.disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', () => loadServers().catch(error => notify(error.message, 'error')));
