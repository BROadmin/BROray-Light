# BROray-Light 2.0.0

Статус: **Stable 2.0.0 опубликован 11 сентября 2026 года**. [Скачать релиз](https://github.com/BROadmin/BROray-Light/releases/tag/v2.0.0).

База — проверенный Light `1.0.0-r1`, не полное дерево BROray. Из точного архива BROray `3.1.0-r09c02` перенесены только применимые изменения. Публичная версия: `2.0.0`; внутренний идентификатор: `2.0.0-r1`; архитектура: `aarch64-3.10`.

## Что изменилось

Выбор официальной версии Xray и отдельная переустановка, проверки совместимости точного архива, исправления процесса Xray и подписок, изолированные RAM-каталоги операционных файлов. Сохранён владелец одинакового сервера при пересечении подписок. Исправлено наследование временного каталога установщика фоновым сервисом: после завершения установки сервис использует собственный RAM-каталог. Сохранены native-вход Keenetic, безопасное владение, signed updater и rollback. Routes, DoT, рейтинги и история качества не добавлялись.

## Доказательства

- [20 проверок перед публикацией — PASS](https://github.com/BROadmin/BROray-Light/releases/download/v2.0.0/ACCEPTANCE.json), с указанием границ каждого теста.
- [Независимые Build A/B P109](https://github.com/BROadmin/BROray-Light/releases/download/v2.0.0/REPRODUCIBILITY.json): 8/8 файлов идентичны. [Сборка и подпись существующим ключом](https://github.com/BROadmin/BROray-Light/actions/runs/34594794158).
- [Полная регрессия](https://github.com/BROadmin/BROray-Light/actions/runs/34594794089): 6 успешных заданий, 41 JSON-отчёт и 511 выполнений проверок, включая повторяющиеся preflight-проверки; это не 511 уникальных сценариев.
- [Chromium](https://github.com/BROadmin/BROray-Light/actions/runs/34594934644): 22 проверки кнопок, API-связей и адаптивной вёрстки. Опасные и граничные сценарии проверены в изолированном окружении.
- [Финальная проверка тестового роутера](https://github.com/BROadmin/BROray-Light/blob/codex/r0009-updater-package/checkpoints/R0013/TARGET-FINAL-P113.json): точные файлы установленного пакета, подпись, равная версия, отказ понижения, перезапуск сервисов и сохранность данных. Native-вход и здоровье после фонового цикла подтверждены отдельно. Переход с r1 и принудительный rollback проверены изолированно, а не повторной физической установкой r1.
- [Проверки внешнего HTTPS P89](https://github.com/BROadmin/BROray-Light/blob/codex/r0009-updater-package/checkpoints/R0013/XRAY-EXTERNAL-P89.md): шесть версий прошли текущий ARM64 VLESS/XHTTP/REALITY-профиль. 26.2.6 остановлена на первой HTTPS-ошибке и внесена в запрет; остальные два запроса для неё не выполнялись.

Исходный commit сборки: `f4af30d98fd1f227e5116def825c09399437086f`. Неизменяемый тег `v2.0.0`: `0d10636e3649726b18c5c90223279edab0bd223d`. [Manifest](https://github.com/BROadmin/BROray-Light/releases/download/v2.0.0/RELEASE-MANIFEST.json) и [SHA256SUMS](https://github.com/BROadmin/BROray-Light/releases/download/v2.0.0/SHA256SUMS) фиксируют опубликованные файлы. Приватный ключ подписи не извлекался из Actions. Ранее опубликованные выпуски не переписывались.

## Установка и история

[Пошаговое руководство](beginner-installation.md) · [История версий](../CHANGELOG.md) · [Документация на сайте](https://docs.brovibe.cloud/broray-light/).

Обновление приложения сохраняет Xray. Ядро при чистой установке — 26.9.9, upstream prerelease; успешные тесты конкретного профиля не доказывают совместимость всех сочетаний транспорта и сервера.
