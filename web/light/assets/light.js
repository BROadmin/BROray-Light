const $ = (selector) => document.querySelector(selector);
const page = $("#page");
const route = location.pathname;
let csrf = "";
let state;
let busy = false;

function node(tag, attributes = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (value !== false) el.setAttribute(key, value === true ? "" : value);
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
  page.replaceChildren();
  $("#login").hidden = false;
  $("#navigation").hidden = true;
  $("#logout").hidden = true;
}

async function load() {
  const data = await request("/api/state");
  state = data.state;
  csrf = data.csrf;
  $("#login").hidden = true;
  $("#navigation").hidden = false;
  $("#logout").hidden = false;
  $("#navigation a[href='" + route + "']")?.setAttribute("aria-current", "page");
  const content = route === "/servers" ? servers() : route === "/subscriptions" ? subscriptions() : home();
  page.replaceChildren(...content);
}

async function perform(job, source) {
  if (busy) return;
  busy = true;
  if (source) source.disabled = true;
  $("#feedback").textContent = "Выполняется…";
  try {
    $("#feedback").textContent = await job() || "";
  } catch (err) {
    $("#feedback").textContent = err.message;
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

const field = (label, attrs) => node("label", {}, label, node("input", attrs));
const submit = (label) => node("button", {class: "primary"}, label);
const panel = (title, ...content) => node("section", {class: "panel"}, node("h2", {}, title), ...content);

function home() {
  const selected = state.servers.find((s) => s.id === state.active);
  const connected = state.running && selected && !state.health;
  const connection = panel("Подключение",
    node("p", {}, node("strong", {class: connected ? "good" : ""}, connected ? "Подключено" : "Отключено"),
      selected ? " · " + selected.name : ""),
    node("small", {}, state.health || "BROray-Light " + state.version));
  const iface = panel("Интерфейс Keenetic",
    node("p", {}, state.cleanupPending ? "Ожидается завершение очистки" : state.manageInterface ? "Управление включено" : "Управление выключено"),
    node("div", {class:"row"},
      button(state.manageInterface ? "Подтвердить и восстановить" : "Настроить", () => action({kind:"interface", enabled:true})),
      button(state.cleanupPending ? "Повторить очистку" : "Отключить", () => action({kind:"interface", enabled:false}))));
  const fail = state.failover;
  const failover = panel("Резервное переключение",
    form((data) => action({kind:"failover", failover: {
      enabled:data.has("enabled"), threshold:Number(data.get("threshold")),
      cooldownSeconds:Number(data.get("cooldown"))
    }}), node("label", {class:"inline"}, node("input",{name:"enabled",type:"checkbox",checked:fail.enabled}), "Автоматически включать следующий доступный сервер"),
    field("Количество ошибок", {name:"threshold",type:"number",min:1,max:20,value:fail.threshold,required:true}),
    field("Интервал между переключениями, с", {name:"cooldown",type:"number",min:15,max:3600,value:fail.cooldownSeconds,required:true}),
    submit("Сохранить")));
  const update = panel("Обновление BROray-Light",
    node("div", {class:"row"},
      button("Проверить обновление", async () => {
        const info = (await request("/api/action",{kind:"update-check"})).result;
        return "Подписанный выпуск " + (info.version || info.Version);
      }),
      button("Установить обновление", async () => {
        if (!confirm("Проверить и установить подписанное обновление BROray-Light?")) return;
        await request("/api/action",{kind:"update-apply"});
        return "Обновление запущено. После перезапуска войдите снова.";
      })));
  const core = panel("Ядро Xray",
    node("div", {class:"row"},
      button("Проверить ядро", async () => {
        const info = (await request("/api/action",{kind:"core-check"})).result;
        return (info.installed ? "Установлено: " + info.installed : "Ядро отсутствует") + ". Доступно: " + info.pinned;
      }),
      button("Установить или обновить Xray", async () => {
        if (!confirm("Проверить и установить закреплённую версию Xray?")) return;
        return action({kind:"core-install"});
      })));
  return [node("h1", {}, "Главная"), node("div", {class:"grid"}, connection, iface, failover, update, core)];
}

function servers() {
  const input = node("textarea", {name:"text", rows:4, required:true, placeholder:"vless://…"});
  const upload = node("input",{type:"file",accept:".txt,text/plain",onchange:async (event) => {
    const file = event.currentTarget.files[0];
    if (!file) return;
    if (file.size > 2 ** 21) {
      $("#feedback").textContent = "Максимальный размер файла — 2 МиБ";
      return;
    }
    input.value = await file.text();
  }});
  const importer = panel("Импорт",
    form((data) => action({kind:"import",text:data.get("text")}, (res) => "Добавлено: " + res.added),
      node("label",{},"Ссылки серверов",input),node("label",{},"Файл UTF-8",upload),submit("Импортировать")));
  return [node("h1",{},"Серверы"), importer, ...state.servers.map((s,index) => {
    const cmd = (kind, data = {}) => action({kind,id:s.id,...data});
    const parameters = [["SNI",s.serverName],["Flow",s.flow],["Host",s.transportHost],["Path",s.path],["Service",s.serviceName]].filter(([,value]) => value);
    return node("article",{class:"panel server"},
      node("h2",{},s.name),
      node("p",{class:"muted"}, s.protocol.toUpperCase() + " · " + s.address + ":" + s.port +
        (s.active ? " · Активный" : "") + (s.excluded ? " · Исключён" : "") +
        (s.pending ? " · Новые параметры готовы к применению" : "")),
      node("details",{},node("summary",{},"Параметры и имя"),
        node("p",{},"Транспорт: " + s.network + " · Защита: " + s.security),
        ...parameters.map(([label,value]) => node("p",{},label + ": " + value)),
        form((data) => cmd("rename",{name:data.get("name")}),field("Имя",{name:"name",value:s.name,maxlength:120,required:true}),submit("Переименовать"))),
      node("div",{class:"row"},
        button("Проверить",() => cmd("check")),
        button(s.pending ? "Применить" : "Активировать",() => cmd("activate"),{disabled:s.excluded}),
        button("↑",() => cmd("move",{position:index-1}),{disabled:index===0,"aria-label":"Переместить выше"}),
        button("↓",() => cmd("move",{position:index+1}),{disabled:index===state.servers.length-1,"aria-label":"Переместить ниже"}),
        button(s.excluded ? "Вернуть" : "Исключить",() => cmd("exclude",{enabled:!s.excluded})),
        button("Удалить",() => confirm("Удалить сервер?") ? cmd("delete") : "")));
  })];
}

function subscriptions() {
  function edit(s = {}) {
    return form((data) => action({kind:"subscription-save",id:s.id,name:data.get("name"),url:data.get("url"),refreshMinutes:Number(data.get("minutes"))}),
      field("Имя",{name:"name",value:s.name || "",maxlength:120}),
      field("Ссылка",{name:"url",type:"url",value:s.url || "",required:true}),
      field("Интервал, мин. (0 — вручную)",{name:"minutes",type:"number",min:0,max:10080,value:s.refreshMinutes || 0,required:true}),
      submit(s.id ? "Сохранить" : "Добавить"));
  }
  return [node("h1",{},"Подписки"), panel("Новая подписка",edit()),
    ...(state.subscriptions || []).map((s) => node("article",{class:"panel subscription"},
      node("h2",{},s.name),
      node("p",{class:"muted"}, "Обновлена: " + (s.refreshedAt.startsWith("0001-") ? "−" : new Date(s.refreshedAt).toLocaleString("ru"))),
      node("div",{class:"row"},
        button("Обновить",() => action({kind:"subscription-refresh",id:s.id})),
        button("Удалить",() => confirm("Удалить подписку?") ? action({kind:"subscription-delete",id:s.id}) : "")),
      node("details",{},node("summary",{},"Настройки"),edit(s))))];
}

$("#login-form").addEventListener("submit",(e) => {
  e.preventDefault();
  const data = new FormData(e.currentTarget);
  perform(async () => {
    try {
      await request("/api/login",{user:data.get("user"),password:data.get("password"),secureSession:location.protocol === "https:"});
      await load();
    } finally {
      $("#login-form input[type=password]").value = "";
    }
  },e.submitter);
});
$("#logout").addEventListener("click",(e) => perform(async () => {
  await request("/api/logout",{});
  signedOut();
},e.currentTarget));
load().catch((err) => { signedOut(); if (err.message !== "sign in to Keenetic") $("#feedback").textContent = err.message; });
