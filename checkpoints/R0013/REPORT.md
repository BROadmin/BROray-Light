# BROray-Light 2.0.0 — итог выпуска R0013

**PASS. Stable 2.0.0 опубликован 11 сентября 2026 года.** candidateReady=true, releaseReady=true, publicReleasePublished=true. Все 26 итоговых gate — PASS; 20 выполнены до публикации, остальные подтверждают публичные файлы, документацию и сохранность прежней работы.

[Релиз](https://github.com/BROadmin/BROray-Light/releases/tag/v2.0.0) · [GitHub](https://github.com/BROadmin/BROray-Light) · [Пошаговая инструкция](https://docs.brovibe.cloud/broray-light/) · [История версий](https://github.com/BROadmin/BROray-Light/blob/main/CHANGELOG.md).

## Идентичность и проверки

- Исходный commit точных сборок: `f4af30d98fd1f227e5116def825c09399437086f`. Неизменяемый release tag v2.0.0: `0d10636e3649726b18c5c90223279edab0bd223d`.
- Независимые Build A/B P109: **8/8 файлов побайтно идентичны**. Подпись существующим ключом в Actions; приватный ключ не извлекался.
- CI34594794089: **6 заданий PASS**, 41 JSON-отчёт, 511 выполнений проверок (включая повторные preflight, не 511 уникальных сценариев). Chromium34594934644: **22 сценария PASS**.
- Изолированно: clean install с точным Xray, переход с принятого r1, equal-version, downgrade refusal, forced-health rollback, persistence, native auth/session/ownership и RAM-жизненный цикл. Границы OS-адаптеров указаны в acceptance receipts.
- Авторизованный ARM64-роутер: точный финальный пакет, native-вход, реальные проверки/переключение серверов с восстановлением исходного, переустановка Xray26.9.9, signed equal/downgrade, перезапуск S23/S24, сохранность файлов, работа интерфейса после фонового цикла. Новый физический переход с r1 и перезагрузка всего роутера в финальном цикле не заявляются.
- Конечное наблюдение: Light2.0.0, Xray26.9.9, Proxy0 активен, соединение работает, публичный Stable-check возвращает equal2.0.0-r1 без обновления. Шесть исходных серверов и пользовательская подписка сохранены; тестовая подписка удалена отдельно с проверкой.
- Xray26.2.6: config/start PASS, первый внешний HTTPS FAIL(curl35); оставшиеся два запроса NOT_RUN. Точный архив запрещён. Остальные шесть версий PASS только для проверенного ARM64 VLESS/XHTTP/REALITY-профиля. Xray26.9.9 остаётся upstream prerelease.
- Операционные временные файлы находятся в защищённой RAM; собственный TMPDIR сервиса не зависит от удалённого каталога установщика. Постоянно около35МиБ вместе с Xray, app-slot858363байта;80МиБ — рекомендуемый запас, не размер Light.

## Публичная документация

Light main docs commit: `cf6217f2fdd5f0b55f80211c29f13db28abb42bd`. Главная сайта и отдельная страница Light опубликованы существующим механизмом; последняя исправленная страница в commit `9728483eea1087e9fbd14f23ebb03fa63aaadc94` полного репозитория затрагивает только документацию и её SHA256SUMS. Прямых изменений production-сервера и приложения полного BROray нет. Руководство не добавлено в WebUI.

Обе живые страницы совпали по SHA-256; инструкция содержит 10 последовательных разделов, проверяемую команду установки, обновление, работу с подписками/Xray, диагностику, удаление и историю версий. Все пять кнопок копирования проверены реальными кликами на390px и1440px; исправлено перекрытие кнопки длинным кодом.

## Опубликованные артефакты

| Файл | Байт | SHA-256 |
| --- | ---: | --- |
| ACCEPTANCE.json | 7854 | `3219232456af0a5a6983fe276c3a63dda68a298bb83914303aff8b3125a049a5` |
| INPUT-MANIFEST.json | 40797 | `ef027f9fe09020555445e72761a72bfad398aeaf2aaa190d05808480811514ed` |
| RELEASE-MANIFEST.json | 2675 | `b2c03a799f6acb49f50ebf4c4371d9d88e4126ebd7f2e33ce1969d96b9bc25f3` |
| REPRODUCIBILITY.json | 2583 | `e347617f99dc4c05a1e2de52033a07f0ff1c5b81a13cc7dcd6560cb3b7c36685` |
| SHA256SUMS | 922 | `0a49b45733c82b4040a9ac1639aed9d3500314d68815ee2c232f2a563806a681` |
| broray-light-app-2.0.0-r1.tar.gz | 230223 | `fb7fc533cb7e41d4ea1ea25fb15b7eb0b8e878bb7e75dbbd7b849b18ddc54c9c` |
| broray-light-install-2.0.0.sh | 4108 | `d7d1a709621f3154c0f5b5892a98bddd3f3f782b57d01eb15025e739abcd44f2` |
| broray-light-updater-platform-5-light2-ram.tar.gz | 136061 | `aa814efcb6d75f02c061b3928588439466e9ee02af127bd7eac376786410fc1b` |
| broray-light_2.0.0_aarch64-3.10.ipk | 12992623 | `e582b1f3b2314f118f1caca9aa98efb2e9e67f0ca4aaa9b42f6e1bcc22ae3a0a` |
| release.json | 597 | `64a909aec7f774b74c1819c887435fdd992af9c7f25d048cdc6fce72ac6bb31e` |
| release.json.minisig | 302 | `89d4057cbfd6405fca931e828eb2145ad1c9553d4483aea9257611e85d1d6a67` |

## Результаты всех acceptance gates

| Gate | Итог | Evidence |
| --- | --- | --- |
| pinned-r1-and-canonical-and-donor-inputs | PASS | [UPSTREAM-DELTA-P2.json](UPSTREAM-DELTA-P2.json) |
| selective-upstream-map-and-excluded-features | PASS | [UPSTREAM-PORT-MAP-P2.json](UPSTREAM-PORT-MAP-P2.json) |
| busybox-syntax-and-component-regression | PASS | [REGRESSION-P109.json](REGRESSION-P109.json) |
| native-authentication-session-and-ownership | PASS | [REGRESSION-P109.json](REGRESSION-P109.json) |
| all-webui-buttons-and-responsive-layout | PASS | [BROWSER-CONTROLS-P109.json](BROWSER-CONTROLS-P109.json) |
| archive-validation-locks-and-safe-updater | PASS | [REGRESSION-P109.json](REGRESSION-P109.json) |
| clean-installer-xray-bootstrap-and-daemon-tmpdir | PASS | [INDEPENDENT-BUILDS-P109.json](INDEPENDENT-BUILDS-P109.json) |
| r1-upgrade-equal-downgrade-rollback-persistence | PASS | [REGRESSION-P109.json](REGRESSION-P109.json) |
| independent-build-A-B-and-SHA256 | PASS | [INDEPENDENT-BUILDS-P109.json](INDEPENDENT-BUILDS-P109.json) |
| existing-minisign-trust-root | PASS | [SIGNED-PROBE-P112.json](SIGNED-PROBE-P112.json) |
| authorized-final-package-and-durable-preservation | PASS | [TARGET-INSTALL-P110.json](TARGET-INSTALL-P110.json) |
| physical-signed-equal-and-downgrade-refusal | PASS | [TARGET-FINAL-P113.json](TARGET-FINAL-P113.json) |
| physical-service-restart-and-persistence | PASS | [TARGET-FINAL-P113.json](TARGET-FINAL-P113.json) |
| physical-xray-controls-and-data-path | PASS | [TARGET-CONTROLS-P98.json](TARGET-CONTROLS-P98.json) |
| xray-negative-26.2.6-policy | PASS | [XRAY-EXTERNAL-P89.json](XRAY-EXTERNAL-P89.json) |
| subscription-overlap-and-delete-preservation | PASS | [OVERLAP-RECOVERY-P102.json](OVERLAP-RECOVERY-P102.json) |
| native-ui-health-after-daemon-background-cycle | PASS | [TARGET-WEBUI-P115.json](TARGET-WEBUI-P115.json) |
| temporary-input-cleanup | PASS | [TARGET-CLEANUP-P114-V2.json](TARGET-CLEANUP-P114-V2.json) |
| russian-guide-history-desktop-mobile-copy | PASS | [DOC-PREVIEW-P111.json](DOC-PREVIEW-P111.json) |
| bounded-publication-authority-and-immutable-tag-absence | PASS | [PUBLICATION-PREFLIGHT-P115.json](PUBLICATION-PREFLIGHT-P115.json) |
| public-release-assets-and-latest-alias | PASS | [RELEASE-PUBLISH-P116-V2.json](RELEASE-PUBLISH-P116-V2.json) |
| github-russian-guide-and-version-history | PASS | [DOC-PUBLICATION-P117.json](DOC-PUBLICATION-P117.json) |
| live-homepage-and-light-guide | PASS | [LIVE-DOCUMENTATION-P121.json](LIVE-DOCUMENTATION-P121.json) |
| live-doc-copy-controls-and-responsive-layout | PASS | [PUBLIC-DOC-BROWSER-P121.json](PUBLIC-DOC-BROWSER-P121.json) |
| native-public-stable-check | PASS | [TARGET-STABLE-P119.json](TARGET-STABLE-P119.json) |
| inherited-r0012-preserved | PASS | [R0012-PRESERVATION-P122.json](R0012-PRESERVATION-P122.json) |

## Сохранённые ошибки и границы

Каждая material failure сохранена отдельно в process-failures с SHA-256. P104/P108: унаследованный TMPDIR исправлен в P109 и проверен новыми A/B, полным CI и физическим пакетом. P116: проверяющий скрипт использовал draft URLs; P116-V2 сверил окончательные URL без повторной загрузки файлов или изменения тега. P119: мобильная кнопка копирования на сайте перекрывалась кодом; P120/P121 исправляют только документацию. Прежние ошибочные receipts не переписаны. 502 исходных файлов R0012 сохранены. Старые сводки до этого seal сохранены побайтно в history/P122-BEFORE-SEAL.

## Следующий этап

`OPERATE_STABLE_2_0_0_COLLECT_USER_FEEDBACK_AUTHORIZE_NEXT_CHANGE`. Эксплуатация выпущенного Stable и сбор обратной связи; любые новые изменения — отдельная согласованная версия. Не переписывать v2.0.0 или прежние релизы.
