/* Generate bounded release-doc staging; never publish or edit the full product. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { marked } = require('marked');
const root = path.resolve(__dirname, '..');
const build = path.resolve(root, process.argv[2] || 'dist/R0013/p97-release-build/A');
const target = path.join(root, 'publication/R0013');
const manifest = JSON.parse(fs.readFileSync(path.join(build, 'ENGINEERING-MANIFEST.json'), 'utf8'));
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const installerHash = hash(fs.readFileSync(path.join(build, 'broray-light-install-2.0.0.sh')));
let guide = fs.readFileSync(path.join(root, 'docs/beginner-installation.md'), 'utf8');
guide = guide.replace(/'([a-f0-9]{64})' \]/, "'" + installerHash + "' ]");
guide = guide.replace(/146 файлов, \d+ байт/, manifest.slot.appFiles + ' файлов, ' + manifest.slot.appLogicalBytes + ' байт');
// Mechanical checksum/size synchronization of this turn's new guide source.
fs.writeFileSync(path.join(root, 'docs/beginner-installation.md'), guide);
const history = fs.readFileSync(path.join(root, 'CHANGELOG.md'), 'utf8');
let html = marked.parse(guide.replace(/^# .+\n/, '') + '\n\n' + history.replace(/^# История версий BROray-Light/, '## История версий BROray-Light'));
html = html.replaceAll('href="../CHANGELOG.md"', 'href="https://github.com/BROadmin/BROray-Light/blob/main/CHANGELOG.md"')
  .replaceAll('href="../checkpoints/', 'href="https://github.com/BROadmin/BROray-Light/blob/codex/r0009-updater-package/checkpoints/')
  .replaceAll('href="RELEASE-2.0.0.md"', 'href="https://github.com/BROadmin/BROray-Light/blob/main/docs/RELEASE-2.0.0.md"');
let headings = [], index = 0;
html = html.replace(/<h2>([\s\S]*?)<\/h2>/g, (_, text) => {
  const id = 'guide-' + (++index);
  headings.push('<a href="#' + id + '">' + text + '</a>');
  return '<h2 id="' + id + '">' + text + '</h2>';
});
html = html.replaceAll('<pre><code', '<pre><button class="copy" type="button" aria-label="Копировать команды">Копировать</button><code');
let page = fs.readFileSync(path.join(target, 'templates/broray-light/index.html'), 'utf8');
page = page.replace(/<title>[^<]*<\/title>/, '<title>BROray-Light 2.0.0 — пошаговая инструкция и история версий</title>');
page = page.replace('BROvibe Docs · BROray-Light 1.0.0-r1', 'BROvibe Docs · BROray-Light 2.0.0');
page = page.replace(/<meta name="description" content="[^"]*">/, '<meta name="description" content="BROray-Light: установка Entware и SSH, VLESS, подписки, Xray, безопасное обновление и история версий.">');
page = page.replace(/<aside class="sidebar"[\s\S]*?<\/aside>/, '<aside class="sidebar" aria-label="Разделы страницы"><p class="sidebar-title">Пошаговая инструкция</p>' + headings.join('\n') + '</aside>');
page = page.replace(/<main class="content" id="content">[\s\S]*?<\/main>/,
  '<main class="content" id="content"><section class="release-banner"><div><p class="eyebrow">Подготовка релиза</p><h1>BROray-Light 2.0.0</h1><p class="lead">Только VLESS. Три страницы WebUI. Безопасное управление Xray.</p></div><div class="release-state">Приёмка продолжается</div></section>\n' + html + '\n</main>');
let home = fs.readFileSync(path.join(target, 'templates/index.html'), 'utf8');
home = home.replace('Stable 1.0.0-r1', '2.0.0 · подготовка');
home = home.replace('Лёгкая VLESS-only редакция: три страницы WebUI, подписки,\n                автопереключение серверов и безопасное управление Xray.',
  'Лёгкая VLESS-only редакция: выбор версии Xray, подписки и резервные серверы.\n                Пошаговая установка, обновление и история версий.');
fs.mkdirSync(path.join(target, 'site/broray-light'), { recursive: true });
fs.writeFileSync(path.join(target, 'site/broray-light/index.html'), page);
fs.writeFileSync(path.join(target, 'site/index.html'), home);
const readme = `# BROray-Light

Лёгкий отдельный VLESS-клиент для совместимых Keenetic: серверы, подписки и безопасное управление Xray в трёх страницах WebUI. Без Routes, управления DNS-over-TLS, рейтингов и истории качества.

[Пошаговая инструкция для начинающих](docs/beginner-installation.md) · [Сайт](https://docs.brovibe.cloud/broray-light/) · [История версий](CHANGELOG.md) · [Stable](https://github.com/BROadmin/BROray-Light/releases/latest)

## Статус 2.0.0

Подготовка к выпуску. Публикация выполняется только после финальной приёмки; текущий Stable пока 1.0.0-r1.

| Компонент | Значение |
| --- | --- |
| Публичная версия / OPKG | 2.0.0 |
| Технический releaseId | 2.0.0-r1 |
| Архитектура | aarch64-3.10 |
| Xray при чистой установке | 26.9.9 (upstream prerelease) |
| Обновитель | 5-light2-ram, существующий ключ подписи |
| WebUI | Главная, Серверы, Подписки |

## Что нового

- Выбор официальной версии Xray, переустановка текущей и отдельные подтверждения риска. Точная 26.2.6 заблокирована по собственному тесту Light.
- Исправления процесса Xray, обновления подписок и имени интерфейса, навигации и управления подписками — избирательно из проверенного BROray 3.1.0-r09c02.
- Временные рабочие данные, загрузки и bootstrap находятся в защищённой оперативной памяти; конфигурация и установленный runtime сохраняются на накопителе.
- Стабильный выбор владельца одинакового сервера: новая пересекающаяся подписка не должна перехватывать уже существовавшие записи и сбрасывать их порядок.

## Требования и размер

Entware aarch64-3.10, записываемый /opt, SSH root, DNS/HTTPS и корректное время. Одновременное владение полным BROray и Light запрещено. Около **35 МиБ постоянно вместе с Xray**; app-slot Light без Xray — около **0,82 МиБ**. Рекомендуемые 80 МиБ свободного /opt — запас для безопасной замены ядра, не размер Light. Временные операции используют /tmp в RAM: ориентир 64 МиБ свободно, предпочтительно 128 МиБ; конкретная операция проверяет требуемое место.

## Установка: пять шагов

1. Установите Entware нужной архитектуры и проверьте /opt.
2. Подключитесь к SSH-порту Entware через Termius, PuTTY или встроенный SSH как root. Приглашение (config)> означает другой терминал — KeeneticOS CLI.
3. Выполните проверяемый блок из [пошаговой инструкции](docs/beginner-installation.md#4-чистая-установка-200). Он скачивает точный установщик в RAM и проверяет SHA-256 **${installerHash}** до запуска.
4. Откройте http://LAN-IP:8080/ либо https://brolight.ВАШ-ДОМЕН-KEENDNS/ и войдите учётной записью Keenetic.
5. Добавьте подписку с названием или VLESS-ссылку, проверьте и активируйте сервер. На Главной проверьте Xray, соединение и статус управляемого интерфейса.

Подробный путь без пропущенных шагов: [Entware, SSH, установка, работа, обновление, диагностика и удаление](docs/beginner-installation.md).

## Обновление установленного Light

Главная → BROray-Light → Проверить обновление → Обновить. Проверенный исходный выпуск — 1.0.0-r1. Обновление сохраняет серверы, подписки, настройки и установленный Xray. Равная версия завершается без изменений, понижение запрещено; при ошибке проверки здоровья предусмотрен возврат предыдущего слота. Не устанавливайте чистый IPK поверх имеющегося приложения.

Xray обновляется отдельно в своей карточке на Главной. Список различает проверенный, непроверенный и несовместимый архив. Непроверенная или предварительная версия требует отдельного согласия; статус полного BROray не переносится автоматически на Light.

## История версий

- **2.0.0 — подготовка:** выбор Xray, защита от несовместимого архива, исправления подписок и процесса, RAM-операции, сохранение canonical-владельца дублей.
- **1.0.0-r2 — 02.09.2026:** опубликованная документационная версия с руководством внутри WebUI; размещение отклонено, рекомендованным Stable снова выбран r1.
- **1.0.0-r1 — 02.09.2026:** первый проверенный публичный Light с VLESS, подписками, автообновлением, резервным переключением и signed updater.

[Полная история](CHANGELOG.md) · [Доказательства и границы 2.0.0](docs/RELEASE-2.0.0.md).

## Безопасность и поддержка

Пароль проверяется KeeneticOS и не сохраняется Light. Не отключайте native-вход, не открывайте LAN-порт напрямую в интернет и не обходите конфликт владения. Перед удалением сохраните данные. Не публикуйте URL подписок, UUID, пароли, cookies, приватные ключи и полные резервные копии.

[Telegram](https://t.me/BROvibe_vpn) · [Issues](https://github.com/BROadmin/BROray-Light/issues) · [Поддержать проект](https://pay.cloudtips.ru/p/09b23d0a).

Приложение — [GPL-3.0](LICENSE); отдельный Xray-core — MPL-2.0. Сторонние компоненты сохраняют собственные лицензии.
`;
fs.mkdirSync(path.join(target, 'github'), {recursive: true});
fs.writeFileSync(path.join(target, 'github/README.md'), readme);
const names = ['site/index.html','site/broray-light/index.html','github/README.md'];
const receipts = names.map(name => { const data=fs.readFileSync(path.join(target,name)); return {path:'publication/R0013/'+name,bytes:data.length,sha256:hash(data)}; });
console.log(JSON.stringify({status:'DRAFT_PUBLICATION_DOCS_GENERATED',installerSha256:installerHash,artifacts:receipts,published:false},null,2));
