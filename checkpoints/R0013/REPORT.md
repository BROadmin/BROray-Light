# BROray-Light 2.0.0 — R0013, checkpoint P57

`candidateReady=false`, `releaseReady=false`. Публичная версия `2.0.0`, внутренний releaseId `2.0.0-r1`. Релиз не опубликован; роутер, production server и приложение полного BROray не изменялись.

## Подтверждённые результаты

- База: принятый Light r1 `9e5fce9bfa7c82bfc2f2654d80fd3987c5259963`; выборочный порт опубликованного BROray 3.1.0-r09c02. Канонический R0008 сохранён. VLESS-only, три страницы, native authentication и остальные ограничения остаются обязательными.
- P39: 42 PASS с настоящими Linux lighttpd/nginx и проверками PID/executable/argv.
- P40: 22 PASS переноса operational run/logs/tmp/update между файловыми системами с сохранением и откатом байтов.
- P44: обновление r1 и health rollback на dash/BusyBox — 4 PASS. Проверяется настоящий r1 updater, старый/новый S24 и runtime-prepare; workload/lighttpd/публикация в этом наборе — тестовые границы.
- P48: **10 PASS** — финализация, SIGKILL старого обновлятора, реальная потеря private tmpfs, чужой файл в legacy lock и подменённый исходный слот; dash + BusyBox. Конфигурация/серверы/подписки/Xray сохранены; при откате без reboot сессия сохраняется, при reboot RAM-сессия исчезает. Старые файлы восстановлены, снимки удалены. Evidence: `DEAD-OWNER-RECOVERY-P48.json`, SHA-256 `dd1d13b2edd9b80658ef7d6a6ec34ce0c15bdac0d91f36cd4c66aba1cd9c8215`.
- Повторная проверка P45 сохранила 502 прежних файла R0012; три описанных исключения — маршрутизация задачи и журнал. Они не включаются в сборку автоматически.

## FIRST-ERROR и текущая ревизия

P45/P46 остановились на неполном тестовом окружении прямого запуска старого S24. Обе ошибки сохранены; P48 исправил PID binding и контракт `status/ensure` тестовой публикации.

**Весь P48 не PASS:** последующий старый RAM-тест ожидал `LEGACY_WORK_SHAPE`, но перенесённая в journal проверка отклоняла посторонний файл раньше, без этого кода. Callback не записывал отчёт при assertion failure. Ошибка: `process-failures/FAILURE-P48-EARLY-WORK-SHAPE-DIAGNOSTIC.json`; другое выполнявшееся задание отменено. Ревизия повторно не запускалась.

P49: все три задания regression PASS на commit `66616c8ccd4efc0fea72218b212a128a1ea91493`. Проверены 14 архивов evidence по SHA-256; 337 тестов из JSON-отчётов, повторные preflight отчёты посчитаны один раз. `REGRESSION-P49.json`: SHA-256 `b5d00600ec26f0c3b56cf5701c20e2ab42b55d2b70a9da798fb983c4e9f64e9f`. В том числе 33 bootstrap/RAM preflight, live/recovery, runtime trees и процессная регрессия. Clean package не перезаписывает установленный current; postinst создаёт operational данные в защищённом RAM и проверяет manifest слота.

P51: очистка снимков после live rollback и ранний SIGKILL после замены S24 без reboot — PASS на dash. Ранний reboot через старый S23 — FAIL: старый updater создаёт пустой немаркированный work directory; новый recovery отказывает. Ошибка сохранена в `process-failures/FAILURE-P51-EARLY-S23-EMPTY-RAM-SURVIVOR.json`, SHA-256 `21c7e0fdecce1a5019c525a9f2339bd77577932b862a44570a99aad386e69652`. Повторного запуска проваленной ревизии не было.

P52: 10 PASS на dash/BusyBox, включая ранний old-S23 reboot и отказы для постороннего вызывающего процесса и постороннего файла. Пустой legacy каталог остаётся нетронутым, не маркируется и не удаляется. Evidence: `EARLY-BOOT-AND-CLEANUP-P52.json`, SHA-256 `5bf063e8632347be480435809f203bcfe3b8434510995f1ea8acae885459dab8`.

Полная регрессия P52: все три задания PASS, 347 уникально учтённых тестов в JSON-отчётах из 15 проверенных архивов. `REGRESSION-P52.json`: SHA-256 `b74752608839776511cad4d485f27c9400707cb367977b28c2ccd24f79e09e24`.

P53: вся компонентная регрессия PASS, три задания, 351 уникально учтённая проверка из 16 SHA-256-проверенных архивов. Включены удаление опознанных старых state/ready, очистка позднего ready старого S23, отказы для чужого JSON и symlink без удаления пары, на dash и BusyBox. Есть собственная RAM-блокировка и inode/размер/SHA-256 в durable receipt. `REGRESSION-P53.json`: SHA-256 `0747151a22c5acef5d9a2f4a32cb104c55fee6dc61e07ec3d011a57410b29b70`.

## Build A/B

P54 подготовил отдельный Linux-набор с полными принятыми r1 и R0013 app-скриптами, без замены daemon/subscriptions/Xray-control. Изолированная network namespace запрещает доступ к реальным серверам. Проверяются старый/new updater, equal-version, downgrade, синтетическая следующая версия, health rollback и persistence. Syntax/AST PASS; выполнение — после проверки P53.

`dist/R0013/p47-engineering-build-A` и `...-B`: отдельные процессы и свежие входные деревья; восемь файлов совпали побайтно, семь структурных проверок PASS. Это предварительные неподписанные сборки **до последней диагностики P49**, не финальный кандидат. Полный список размеров и SHA-256 — `ENGINEERING-BUILDS-P47.json` (SHA-256 `73ceaf5f6179c87abf0ca25c0fe2e829cb91fb8edc0a33b815e6110e69ced708`). App-slot P47: 146 файлов, 836767 логических байт; Xray: 35061884 байта. Это не замер выделенных блоков на роутере.

## Ещё необходимо

1. Завершить P54 полный app lifecycle и P55 native-auth/CGI.
2. Полный prepared-app: clean install, r1/new update, equal-version, downgrade refusal, rollback, persistence. Отдельно проверить stop/start реального S24 под общей блокировкой нового updater.
3. Все кнопки/API, native authentication/session, desktop/mobile browser.
4. Финальные независимые clean-checkout Build A/B, воспроизводимость, SHA-256 и подпись существующим encrypted Actions secret.
5. Авторизованная целевая приёмка. Публикация и публичные байты — только после готовности кандидата.

P55 добавляет проверку точных подготовленных CGI/native-auth/session в private mount/network namespaces на канонических путях. HTTP-ответ KeeneticOS имитируется с придуманными тестовыми данными; curl и код приложения настоящие. Положительный вход, негативные native-ответы, сессии/истечение/logout и защита всех CGI от неавторизованного доступа подготовлены; Linux PASS пока не заявляется.

P56 воспроизвёл дефект принятого обработчика подписки: отмена удаления оставляла кнопку disabled без отправки запроса. FIRST-ERROR сохранён (`FAILURE-P56-SUBSCRIPTION-CANCEL-DISABLES-BUTTON.json`). P57 добавляет только finally для восстановления доступности кнопки. Пять тестов на настоящем prepared JS с DOM/HTTP/confirm fixtures PASS: отмена, delete/refresh success и HTTP error. `CONTROL-P57.json`: SHA-256 `18180c9ff3f419c5c758b97197c5f75ad669fd163d1f75ba4ad67fcea6c144b7`. P55 CI отменён до запуска и заменяется P57 с неизменённым тестом native-auth; это не retry проваленного revision.

Точные статусы каждого acceptance gate: `VALIDATION.json`. Текущие источники: `PRODUCED-SOURCE-MANIFEST.json` (79 файлов), изменения P57 — `SOURCE-INPUTS-P57.json`. Компонентный PASS не равен PASS полного кандидата.
