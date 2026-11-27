const $ = (selector) => document.querySelector(selector);
const page = $("#page");
const route = location.pathname;
const routeTitle = route === "/servers" ? "Серверы" : route === "/subscriptions" ? "Подписки" : "Главная";
const feedback = $("#feedback");
const serverChecks = new Map();
let csrf = "";
let state;
let busy = false;

function node(tag, attributes = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (value != null && value !== false) el.setAttribute(key, value === true ? "" : value);
  }
  el.append(...children);
  return el;
}

async function request(path, data) {
  const options = data === undefined ? {} : {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf},
    body: JSON.stringify(data)
  };
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error("Не удалось связаться с BROray-Light");
  }
  const body = await response.json();
  if (response.status === 401 && path !== "/api/login") signedOut();
  if (!response.ok) throw new Error(body.error || "Запрос завершился с ошибкой");
  return body;
}

function signedOut() {
  csrf = "";
  state = undefined;
  serverChecks.clear();
  document.body.classList.add("login-body");
  document.title = "Вход в BROray-Light";
  page.replaceChildren();
  page.hidden = true;
  $("#app-header").hidden = true;
  $("#login").hidden = false;
  $("#navigation").hidden = true;
  $("#logout").hidden = true;
}

async function load() {
  const data = await request("/api/state");
  state = data.state;
  csrf = data.csrf;
  document.body.classList.remove("login-body");
  document.title = "BROray-Light — " + routeTitle;
  $("#header-eyebrow").textContent = route === "/" ? "VLESS для Keenetic" : "BROray-Light";
  $("#header-title").textContent = route === "/" ? "BROray-Light" : routeTitle;
  $("#headerConnection").closest(".header-state").hidden = route !== "/";
  $("#app-header").hidden = false;
  $("#login").hidden = true;
  $("#navigation").hidden = false;
  $("#logout").hidden = false;
  $("#navigation a[href='" + route + "']")?.setAttribute("aria-current", "page");
  const content = route === "/servers" ? servers() : route === "/subscriptions" ? subscriptions() : home();
  page.replaceChildren(...content);
  page.hidden = false;
}

async function perform(job, source) {
  if (busy) return;
  busy = true;
  if (source) source.disabled = true;
  feedback.classList.remove("notice-error");
  feedback.textContent = "Выполняется…";
  try {
    feedback.textContent = await job() || "";
  } catch (err) {
    feedback.classList.add("notice-error");
    feedback.textContent = err.message;
  } finally {
    if (source) source.disabled = false;
    busy = false;
  }
}

async function action(data, message = "Готово") {
  const result = (await request("/api/action", data)).result;
  await load();
  return typeof message === "function" ? message(result) : message;
}

function button(label, job, extra = {}) {
  return node("button", {type: "button", onclick: (e) => perform(job, e.currentTarget), ...extra}, label);
}

function form(makeAction, ...children) {
  return node("form", {onsubmit: (e) => {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    perform(() => makeAction(data), e.submitter);
  }}, ...children);
}

const field = (label, attrs, className = "") => node("label", {class: className}, label, node("input", attrs));
const submit = (label) => node("button", {type: "submit"}, label);
const card = (title, className, ...content) => node("section", {class: className},
  node("h2", {class: "card-label"}, title), ...content);
const actions = (...controls) => node("div", {class: "row actions"}, ...controls);
const detail = (text, id) => node("div", {id, class: "muted detail-text"}, text);
const versionRow = (id, version) => node("div", {class: "version-row"},
  node("span", {class: "version-prefix"}, "Версия"), node("strong", {id}, version));
const emptyState = (title, message) => node("section", {class: "card empty-state"},
  node("strong", {}, title), node("span", {class: "muted"}, message));

function failoverForm() {
  const fail = state.failover;
  return form((data) => action({kind: "failover", failover: {
    enabled: data.has("enabled"),
    threshold: Number(data.get("threshold")),
    cooldownSeconds: Number(data.get("cooldown"))
  }}, "Настройки сохранены"),
    node("div", {class: "form-grid failover-grid"},
      node("label", {class: "check-line"},
        node("input", {name: "enabled", type: "checkbox", checked: fail.enabled}), " Включить автопереключение"),
      field("Ошибок до переключения", {name: "threshold", type: "number", min: 1, max: 20, value: fail.threshold, required: true}),
      field("Пауза после переключения, сек.", {name: "cooldown", type: "number", min: 15, max: 3600, value: fail.cooldownSeconds, required: true})),
    actions(submit("Сохранить настройки")));
}

function failoverStatus(disabled = "Выключено") {
  return node("div", {class: "status"}, state.failover.enabled ? "Включено" : disabled);
}

function home() {
  const selected = state.servers.find((server) => server.id === state.active);
  const connected = state.running && selected && !state.health;
  $("#headerConnection").textContent = connected ? "Подключено" : "Нет соединения";
  const activeName = selected?.name || state.active || "Не выбран";
  const connection = card("Активный сервер", "card card-accent",
    node("div", {id: "activeServer", class: "status status-large"}, activeName),
    node("div", {id: "activeServerId", class: "muted mono"}, state.active !== activeName ? state.active : ""),
    node("div", {id: "connection", class: "status-line"}, connected ? "● Соединение работает" : "○ Нет соединения"),
    state.health ? detail(state.health, "connectionDetail") : "");

  const fail = state.failover;
  const failoverDetail = fail.enabled ?
    "Ошибок до переключения: " + fail.threshold + ". Пауза: " + fail.cooldownSeconds + " с." :
    "Автоматические проверки выключены. Включите их на странице «Серверы».";
  const failover = card("Автопереключение", "card", failoverStatus(),
    detail(failoverDetail, "failoverDetail"),
    node("a", {class: "text-link", href: "/servers"}, "Настроить порядок серверов →"));

  const interfaceEnabled = state.manageInterface;
  const interfaceStatus = state.cleanupPending ? "Ожидается завершение очистки" :
    interfaceEnabled ? "Управление включено" : "Управление выключено";
  const interfaceTone = state.cleanupPending ? "warning" : interfaceEnabled ? "active" : "inactive";
  const iface = card("Keenetic", "card",
    node("div", {class: "keenetic-summary-row"},
      node("div", {class: "keenetic-interface"},
        node("span", {class: "keenetic-interface-label"}, "Интерфейс")),
      node("span", {id: "keeneticState", class: "interface-status-badge is-" + interfaceTone}, interfaceStatus)),
    actions(
      button(interfaceEnabled ? "Подтвердить и восстановить" : "Настроить", () => action({kind: "interface", enabled: true})),
      button(state.cleanupPending ? "Повторить очистку" : "Отключить", () => action({kind: "interface", enabled: false}), {class: "secondary"}),
      button("Обновить статус", load, {class: "secondary"})));

  const coreVersion = versionRow("xrayVersion", "—");
  const coreUpdate = detail("Нажмите «Проверить обновление».", "xrayUpdate");
  const core = card("Xray", "card", coreVersion,
    node("div", {id: "xrayState", class: "muted"}, state.running ? "Xray запущен" : "Xray остановлен"),
    coreUpdate,
    actions(
      button("Проверить обновление", async () => {
        const info = (await request("/api/action", {kind: "core-check"})).result;
        coreVersion.lastElementChild.textContent = info.installed || "Не установлен";
        coreUpdate.textContent = "Закреплённая версия: " + info.pinned;
        return coreUpdate.textContent;
      }, {class: "secondary"}),
      button("Установить", async () => {
        if (confirm("Проверить и установить закреплённую версию Xray?")) return action({kind: "core-install"});
      })));

  const lightUpdate = detail("Нажмите «Проверить обновление».", "lightUpdate");
  const update = card("BROray-Light", "card", versionRow("lightVersion", state.version), lightUpdate,
    actions(
      button("Проверить обновление", async () => {
        const info = (await request("/api/action", {kind: "update-check"})).result;
        lightUpdate.textContent = "Подписанный выпуск " + (info.version || info.Version);
        return lightUpdate.textContent;
      }, {class: "secondary"}),
      button("Обновить", async () => {
        if (!confirm("Проверить и установить подписанное обновление BROray-Light?")) return;
        await request("/api/action", {kind: "update-apply"});
        return "Обновление запущено. После перезапуска войдите снова.";
      })));

  const projectLinks = [
    ["Сайт и документация", "https://docs.brovibe.cloud/broray-light/"],
    ["GitHub", "https://github.com/BROadmin/BROray-Light"],
    ["Новости в Telegram", "https://t.me/myBROvibe"],
    ["Обсуждение в Telegram", "https://t.me/BROvibe_vpn"],
    ["Поддержать проект", "https://pay.cloudtips.ru/p/09b23d0a"],
  ];
  const project = card("Проект и поддержка", "card project-card",
    node("ul", {class: "row project-links"}, ...projectLinks.map(([label, href]) =>
      node("li", {}, node("a", {href, target: "_blank", rel: "noopener noreferrer"}, label)))));

  return [node("div", {class: "grid dashboard-grid"}, connection, failover, iface, core, update, project)];
}

function servers() {
  const input = node("textarea", {id: "uri", name: "text", rows: 3, autocomplete: "off", required: true,
    "aria-label": "Поддерживаемые ссылки серверов", placeholder: "vless://…"});
  const importer = card("Добавить сервер", "card form-card",
    node("p", {class: "muted section-copy"}, "Вставьте ссылки серверов или выберите файл. Уже сохранённые серверы не будут добавлены повторно."),
    form((data) => action({kind: "import", text: data.get("text")}, (result) => "Добавлено: " + result.added),
      input, actions(submit("Добавить сервер"))));
  const failover = card("Автопереключение", "card form-card",
    failoverStatus("Выключено — автоматические проверки не выполняются"),
    node("p", {class: "muted section-copy"}, "После указанного числа ошибок BROray-Light проверит серверы сверху вниз. Пауза защищает от слишком частых переключений."),
    failoverForm());
  const hasActive = Boolean(state.active && state.servers.some((server) => server.id === state.active));
  const canDeleteInactive = hasActive && state.servers.length > 1;
  const catalogue = actions(
    button("Удалить все, кроме активного", () => {
      if (!canDeleteInactive || !confirm("Удалить из списка все серверы, кроме активного? Серверы из подписок могут вернуться после обновления.")) return;
      return action({kind: "delete-inactive"}, (result) => "Удалено серверов: " + result.removed);
    }, {class: "danger-button", disabled: !canDeleteInactive}));
  const cards = state.servers.map(serverCard);
  if (!cards.length) cards.push(emptyState("Серверов пока нет", "Добавьте ссылку сервера или импортируйте подписку."));
  return [importer, failover, catalogue, node("div", {id: "servers", class: "grid list-grid"}, ...cards)];
}

function serverCard(server, index) {
  const cmd = (kind, data = {}, message) => action({kind, id: server.id, ...data}, message);
  const name = server.name || server.id;
  const parameters = [["SNI", server.serverName], ["Flow", server.flow], ["Host", server.transportHost],
    ["Path", server.path], ["Service", server.serviceName]].filter(([, value]) => value);
  const check = serverChecks.get(server.id);
  const alreadyRunning = server.active && state.running && !state.health && !server.pending;
  const result = node("div", {class: "server-check-result" + (check ? " " + check.tone : ""), role: "status"},
    check?.message || "Проверка ещё не выполнялась");

  return node("section", {class: "card server-card" + (server.active ? " is-active" : ""), "data-server-id": server.id},
    node("div", {class: "server-title"}, node("strong", {}, name),
      server.active ? node("span", {class: "badge badge-success"}, "Активен") : ""),
    node("div", {class: "muted"}, server.address + ":" + server.port + " · " + server.protocol.toUpperCase() +
      " · " + (server.network || "raw") + " / " + (server.security || "none")),
    result,
    server.pending ? node("div", {class: "muted"}, "Новые параметры готовы к применению") : "",
    node("label", {class: "check-line muted"},
      node("input", {type: "checkbox", checked: server.excluded, onchange: (event) => {
        const checkbox = event.currentTarget;
        const enabled = checkbox.checked;
        checkbox.checked = server.excluded;
        perform(() => cmd("exclude", {enabled}), checkbox);
      }}), " Не использовать в автопереключении"),
    node("details", {}, node("summary", {}, "Параметры и имя"),
      node("p", {}, "Транспорт: " + server.network + " · Защита: " + server.security),
      ...parameters.map(([label, value]) => node("p", {}, label + ": " + value)),
      form((data) => cmd("rename", {name: data.get("name")}),
        field("Имя", {name: "name", value: name, maxlength: 120, required: true}), submit("Переименовать"))),
    actions(
      button("↑", () => cmd("move", {position: index - 1}),
        {class: "icon-button secondary", disabled: index === 0, "aria-label": "Переместить выше", title: "Переместить выше"}),
      button("↓", () => cmd("move", {position: index + 1}),
        {class: "icon-button secondary", disabled: index === state.servers.length - 1, "aria-label": "Переместить ниже", title: "Переместить ниже"}),
      button("Проверить", async () => {
        try {
          await request("/api/action", {kind: "check", id: server.id});
          result.textContent = "● Сервер доступен";
          serverChecks.set(server.id, {message: result.textContent, tone: "is-success"});
          result.className = "server-check-result is-success";
          return "Сервер доступен";
        } catch (error) {
          result.textContent = "○ Сервер недоступен · " + error.message;
          if (state) serverChecks.set(server.id, {message: result.textContent, tone: "is-error"});
          result.className = "server-check-result is-error";
          throw error;
        }
      }, {class: "secondary"}),
      button(alreadyRunning ? "Активен" : server.pending ? "Применить" : "Активировать",
        () => cmd("activate", {}, "Сервер активирован"), {disabled: alreadyRunning || server.excluded}),
      button("Удалить", () => confirm("Удалить сервер «" + name + "»?") ? cmd("delete", {}, "Сервер удалён") : "",
        {class: "danger-button"})));
}

function subscriptionFields(subscription = {}) {
  return node("div", {class: "form-grid"},
    field("Название", {name: "name", value: subscription.name || "", maxlength: 120, placeholder: "Например: Основная"}),
    field("Ссылка подписки", {name: "url", type: "url", value: subscription.url || "", required: true, autocomplete: "off", placeholder: "https://…"}, "wide"));
}

function subscriptionSave(data, subscription, minutes, message) {
  return action({kind: "subscription-save", id: subscription.id, name: data.get("name"), url: data.get("url"), refreshMinutes: minutes}, message);
}

function subscriptionCard(subscription) {
  const name = subscription.name || subscription.id;
  const enabled = subscription.refreshMinutes > 0;
  const refreshed = !subscription.refreshedAt.startsWith("0001-");
  const nextUpdate = new Date(Date.parse(subscription.refreshedAt) + subscription.refreshMinutes * 60000);
  const settings = node("div", {class: "subscription-auto-update"},
    node("div", {class: "subscription-auto-heading"},
      node("span", {class: "subscription-auto-title"}, "Автообновление"),
      node("span", {class: enabled ? "badge badge-success" : "badge"}, enabled ? "Включено" : "Выключено")),
    form((data) => action({kind: "subscription-save", id: subscription.id, name: subscription.name,
      url: subscription.url, refreshMinutes: data.has("enabled") ? Number(data.get("minutes")) : 0}, "Настройки сохранены"),
      node("div", {class: "subscription-auto-grid"},
        node("label", {class: "check-line"},
          node("input", {name: "enabled", type: "checkbox", checked: enabled}), " Включить автообновление"),
        field("Интервал, минут", {name: "minutes", type: "number", min: 5, max: 10080, value: subscription.refreshMinutes || 360, required: true})),
      node("div", {class: "muted subscription-auto-next"}, !enabled ? "Автоматическое обновление выключено" :
        refreshed && nextUpdate.getTime() > Date.now() ? "Следующее обновление: " + nextUpdate.toLocaleString("ru") : "Ожидается автоматическое обновление"),
      node("div", {class: "row actions subscription-auto-actions"}, submit("Сохранить автообновление"))));

  return node("section", {class: "card subscription-card", "data-subscription-id": subscription.id},
    node("div", {class: "subscription-heading"}, node("strong", {class: "card-title"}, name)),
    node("div", {class: "muted subscription-meta"}, refreshed ?
      "Обновлена: " + new Date(subscription.refreshedAt).toLocaleString("ru") : "Ещё не обновлялась"),
    settings,
    node("details", {}, node("summary", {}, "Настройки подписки"),
      form((data) => subscriptionSave(data, subscription, subscription.refreshMinutes, "Подписка сохранена"),
        subscriptionFields(subscription), actions(submit("Сохранить")))),
    node("div", {class: "row actions subscription-actions"},
      button("Обновить", () => action({kind: "subscription-refresh", id: subscription.id}, "Подписка обновлена")),
      button("Удалить", () => confirm("Удалить подписку «" + name + "»?") ?
        action({kind: "subscription-delete", id: subscription.id}, "Подписка удалена") : "", {class: "danger-button"})));
}

function subscriptions() {
  const create = card("Новая подписка", "card form-card",
    form((data) => subscriptionSave(data, {}, Number(data.get("minutes")), "Подписка добавлена"),
      subscriptionFields(),
      field("Интервал, мин. (0 — вручную)", {name: "minutes", type: "number", min: 0, max: 10080, value: 0, required: true}),
      actions(submit("Добавить подписку"))),
    node("div", {class: "muted"}, "Импортируются поддерживаемые ссылки серверов. Ссылка подписки не показывается в списке."));
  const cards = (state.subscriptions || []).map(subscriptionCard);
  if (!cards.length) cards.push(emptyState("Подписок пока нет", "Добавьте название и ссылку выше."));
  return [create, node("div", {id: "subscriptions", class: "grid list-grid"}, ...cards)];
}

const password = $("#password");
const passwordToggle = $("#password-toggle");

function setPasswordVisible(visible) {
  password.type = visible ? "text" : "password";
  const label = visible ? "Скрыть пароль" : "Показать пароль";
  passwordToggle.setAttribute("aria-label", label);
  passwordToggle.title = label;
  passwordToggle.querySelector(".visually-hidden").textContent = label;
}

passwordToggle.addEventListener("click", () => setPasswordVisible(password.type === "password"));
$("#login-form").addEventListener("submit",(e) => {
  e.preventDefault();
  const data = new FormData(e.currentTarget);
  perform(async () => {
    try {
      await request("/api/login",{user:data.get("user"),password:data.get("password"),secureSession:location.protocol === "https:"});
      await load();
    } finally {
      password.value = "";
      setPasswordVisible(false);
    }
  },e.submitter);
});
$("#logout").addEventListener("click",(e) => perform(async () => {
  await request("/api/logout",{});
  signedOut();
},e.currentTarget));
load().catch((err) => {
  signedOut();
  if (err.message !== "sign in to Keenetic") {
    feedback.classList.add("notice-error");
    feedback.textContent = err.message;
  }
});
