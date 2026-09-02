async function sapi(url, opts) {
  const response = await fetch(url, Object.assign({ credentials: 'same-origin', cache: 'no-store' }, opts || {}));
  const raw = await response.text();
  let payload = {};
  if (raw.trim()) {
    try {
      payload = JSON.parse(raw);
    } catch (_) {
      throw new Error('Сервер вернул некорректный ответ');
    }
  }
  if (response.status === 401) {
    location.replace('/?v=1.0.0-r3');
    throw new Error('Требуется вход');
  }
  if (!response.ok || payload.success === false || payload.ok === false) {
    throw new Error(payload.error?.message || payload.message || 'Ошибка');
  }
  return payload.data ?? payload;
}

function toast(message, type) {
  if (window.BROrayUI) window.BROrayUI.toast(message, type);
  else alert(message);
}

function subscriptionItems(data) {
  return Array.isArray(data) ? data : (data.subscriptions || data.items || []);
}

function subscriptionMeta(subscription) {
  const parts = [];
  const count = Number.isFinite(subscription.serversCount) ? subscription.serversCount : subscription.serverCount;
  if (Number.isFinite(count)) parts.push('Серверов: ' + count);
  parts.push(subscription.lastUpdatedAt ? 'Обновлена: ' + subscription.lastUpdatedAt : 'Ещё не обновлялась');
  return parts.join(' · ');
}

async function subscriptionAction(subscription, action) {
  if (action === 'delete' && !confirm('Удалить подписку «' + (subscription.name || subscription.id) + '» и все полученные из неё серверы?')) return;
  const endpoint = action === 'refresh' ? 'refresh.cgi' : 'delete.cgi';
  const url = 'api/subscriptions/' + endpoint + '?id=' + encodeURIComponent(subscription.id);
  await sapi(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  toast(action === 'refresh' ? 'Подписка обновлена' : 'Подписка удалена');
  await loadSubs();
}

function autoUpdatePanel(subscription) {
  const panel = document.createElement('div');
  panel.className = 'subscription-auto-update';
  const enabled = subscription.autoUpdateEnabled === true;
  const interval = Number(subscription.updateIntervalMinutes) || 360;
  panel.innerHTML =
    '<div class="subscription-auto-heading"><span class="subscription-auto-title">Автообновление</span>' +
      '<span class="badge ' + (enabled ? 'badge-success' : '') + '" data-auto-status>' + (enabled ? 'Включено' : 'Выключено') + '</span></div>' +
    '<div class="subscription-auto-grid">' +
      '<label class="check-line"><input type="checkbox" data-auto-enabled ' + (enabled ? 'checked' : '') + '> Включить автообновление</label>' +
      '<label>Интервал, минут<input type="number" min="5" max="10080" step="1" value="' + interval + '" data-auto-interval></label>' +
    '</div>' +
    '<div class="muted subscription-auto-next">' +
      (enabled && subscription.nextUpdateAt ? 'Следующее обновление: ' + subscription.nextUpdateAt : 'Автоматическое обновление не запланировано') +
    '</div>' +
    '<div class="row actions subscription-auto-actions"><button type="button" data-auto-save>Сохранить автообновление</button></div>';

  panel.querySelector('[data-auto-save]').addEventListener('click', async event => {
    const autoUpdateEnabled = panel.querySelector('[data-auto-enabled]').checked;
    const updateIntervalMinutes = Number(panel.querySelector('[data-auto-interval]').value);
    if (!Number.isInteger(updateIntervalMinutes) || updateIntervalMinutes < 5 || updateIntervalMinutes > 10080) {
      toast('Интервал должен быть от 5 до 10080 минут', 'error');
      return;
    }
    try {
      event.target.disabled = true;
      await sapi('api/subscriptions/details.cgi?id=' + encodeURIComponent(subscription.id), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ autoUpdateEnabled, updateIntervalMinutes })
      });
      toast(autoUpdateEnabled ? 'Автообновление включено' : 'Автообновление выключено');
      await loadSubs();
    } catch (error) {
      event.target.disabled = false;
      toast(error.message, 'error');
    }
  });
  return panel;
}

async function loadSubs() {
  const data = await sapi('api/subscriptions/list.cgi');
  const box = document.getElementById('subscriptions');
  const items = Array.isArray(data)?data:(data.subscriptions || data.items || []);
  box.innerHTML = '';
  if (!items.length) {
    box.innerHTML = '<section class="card empty-state"><strong>Подписок пока нет</strong><span class="muted">Добавьте название и ссылку выше.</span></section>';
    return;
  }
  for (const subscription of items) {
    const card = document.createElement('section');
    card.className = 'card subscription-card';
    card.dataset.subscriptionId = subscription.id;

    const heading = document.createElement('div');
    heading.className = 'subscription-heading';
    const title = document.createElement('strong');
    title.className = 'card-title';
    title.textContent = subscription.name || subscription.id;
    heading.appendChild(title);

    const meta = document.createElement('div');
    meta.className = 'muted subscription-meta';
    meta.textContent = subscriptionMeta(subscription);
    card.append(heading, meta);

    if (subscription.lastError) {
      const error = document.createElement('div');
      error.className = 'notice notice-error';
      error.textContent = subscription.lastError;
      card.appendChild(error);
    }

    card.appendChild(autoUpdatePanel(subscription));

    const actions = document.createElement('div');
    actions.className = 'row actions subscription-actions';
    actions.innerHTML = '<button data-a="refresh">Обновить</button><button class="danger-button" data-a="delete">Удалить</button>';
    actions.addEventListener('click', async event => {
      const action = event.target.dataset.a;
      if (!action) return;
      try {
        event.target.disabled = true;
        await subscriptionAction(subscription, action);
      } catch (error) {
        event.target.disabled = false;
        toast(error.message, 'error');
      }
    });
    card.appendChild(actions);
    box.appendChild(card);
  }
}

async function addSub() {
  const name = document.getElementById('subName').value.trim();
  const url = document.getElementById('subUrl').value.trim();
  if (!name) {
    toast('Укажите название подписки', 'error');
    document.getElementById('subName').focus();
    return;
  }
  if (!url) {
    toast('Укажите ссылку подписки', 'error');
    document.getElementById('subUrl').focus();
    return;
  }
  try {
    await sapi('api/subscriptions/create.cgi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({name,url,updateImmediately:true})
    });
    document.getElementById('subName').value = '';
    document.getElementById('subUrl').value = '';
    toast('Подписка добавлена');
    await loadSubs();
  } catch (error) {
    toast(error.message, 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('addSubscription').addEventListener('click', addSub);
  loadSubs().catch(error => toast(error.message, 'error'));
});
