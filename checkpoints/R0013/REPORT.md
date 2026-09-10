# BROray-Light 2.0.0 — R0013, checkpoint P46

Публичная версия `2.0.0`, технический releaseId `2.0.0-r1`. `candidateReady=false`, `releaseReady=false`. Релиз не опубликован; роутер, production server и приложение полного BROray не изменялись.

## Подтверждено

База: принятый Light r1 `9e5fce9bfa7c82bfc2f2654d80fd3987c5259963`; выборочный порт опубликованного BROray 3.1.0-r09c02. Канонический R0008 и ограничения VLESS-only/три страницы/native authentication сохранены. Повторная проверка 502 прежних файлов R0012: SHA-256 совпадают; три ранее зафиксированных исключения — маршрутизация задачи и журнал.

- P39: 42 PASS с настоящими Linux lighttpd/nginx, точным PID/executable/argv и изолированной остановкой.
- P40: 22 PASS переноса operational run/logs/tmp/update в RAM и точного восстановления между разными файловыми системами.
- P44: 4 PASS — обновление r1 и принудительный health rollback на dash и BusyBox. Неизменённый r1 updater, настоящие старый/новый S24 и runtime-prepare; конфигурация, серверы, подписки, runtime и сессии сохранены. Рабочий цикл daemon, lighttpd и OS-публикация в этом наборе имитируются. Все три задания CI P44 завершились success.
- P41/P42/P43 были отдельными неудачными тестовыми ревизиями. Причины, SHA-256 evidence и исправления сохранены; повторного запуска тех же ревизий не было.

## Текущая проверка

P45 устанавливает S24 recovery entry первым, связывает receipt с boot ID, SHA-256 обоих слотов и исходным RAM-каталогом, добавляет dead-owner recovery, откат и финализацию под общей блокировкой. Локальные syntax/AST/сборка дерева приложения: PASS (146 файлов). Первый Linux run: [34539155996](https://github.com/BROadmin/BROray-Light/actions/runs/34539155996), исходный commit `16a710922acee060c51760b3f0a5ded450719a66`. Функциональный результат P45 ещё не принят.

P45 остановлен на первой ошибке: финализация PASS, но dead-owner rollback вернул 1 после восстановления файлов и очистки снимков. Причина: имитация lighttpd не получила PID-путь при прямом вызове восстановленного S24. Evidence и SHA-256: `process-failures/FAILURE-P45-RECOVERY-FIXTURE-PID-BINDING.json`. P46 исправляет только окружение теста; продуктовые байты P45 сохранены. RAM-loss и отрицательные recovery-тесты пока не выполнены.

Контракт и SHA-256 изменённых источников: `SOURCE-INPUTS-P45.json`. Полный текущий перечень: `PRODUCED-SOURCE-MANIFEST.json` (74 файла). START-P46 фиксирует исправление до изменения файлов.

## Сборки

Build A/B P40 — восемь побайтно одинаковых файлов, семь структурных PASS. Это предварительные неподписанные сборки до P41/P45, не финальный кандидат. Артефакты, размеры и все SHA-256: `ENGINEERING-BUILD-ARTIFACTS-P40.json` и `RUNTIME-TREES-AND-BUILDS-P40.json`. Состав текущего P45 ими не подтверждается.

## Следующие обязательные этапы

1. Принять или зафиксировать первую ошибку Linux P45; проверить раннюю загрузку и завершение очистки operational state.
2. Clean-install postinst и полный prepared-app install/update/equal/downgrade/rollback/persistence.
3. Каждая кнопка/API, native authentication/session, desktop/mobile browser.
4. Финальные независимые чистые Build A/B, воспроизводимость, SHA-256 и подпись существующим encrypted Actions secret.
5. Авторизованная целевая приёмка. Публикация и публичные байты — только после готовности кандидата.

Точные результаты каждого acceptance gate находятся в `VALIDATION.json`. Исторические компонентные PASS не означают PASS текущего полного кандидата.
