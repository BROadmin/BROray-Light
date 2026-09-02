# R0010 Stable release report

R0010 завершён со статусом **PASS**. BROray-Light `1.0.0-r1` опубликован как публичный Stable release, `candidateReady=true`, `releaseReady=true`, все 20 acceptance gates пройдены.

Публичный релиз: <https://github.com/BROadmin/BROray-Light/releases/tag/v1.0.0-r1>. Release-source commit — `9e5fce9bfa7c82bfc2f2654d80fd3987c5259963`; annotated tag `v1.0.0-r1` разыменовывается строго в этот commit. Последующий commit содержит только доказательные checkpoints, состояние проекта, handoff и тестовые runner-файлы; опубликованные байты не меняются.

## Артефакты и воспроизводимость

- IPK: `707431aa20c01958edfe40ed04a70c24308a9dabc9ff26f758101c952827d432` (12799724 байта).
- App archive: `2b2d22e9a172b28229aa19ca904f1810722da21b5d34f27eafd79d5acac1e5b0` (157138 байт).
- Clean installer: `da8c57ee3b68156462a2dea5cb2f3b6d1706ed754b1cd8904b745ee1fb86c51d` (1851 байт).
- Updater platform archive: `4983f0fc268a9f19f3e64959fe5f7d8086f26ad907d528ca82ca623f10d9a92a` (131682 байта).
- Release manifest: `05523426a5edd246330e8987ab9a772f9ec61a4c19bb99f145170aa882ac6f42` (2966 байт).
- Stable `release.json`: `ccbd353f6042be992ae1aab293447ae7f6f57727d263a5b58253bde276cd0cf6` (576 байт).
- Minisign signature: `da2ff05d973c19b3b4ea79bc48329cecdb9e0cdae99f3dcd05efd2b703e2d84d` (269 байт).
- Artifact `SHA256SUMS`: `00de57fe2472b642e88a3f90ccdad7e1ad4fb8092963a505b509a21628618a72` (669 байт).

Build A (`dist/R0010/1.0.0-r1-P50-Cache-Final-Build-A`) и независимый Build B (`dist/R0010/1.0.0-r1-P53-Cache-Final-Build-B`) совпадают побайтно для всех 8/8 файлов. Оба manifests проверены, публично скачанные файлы 8/8 совпадают с обоими builds.

## Проверки

Изолированный suite: 52/52 PASS. Он охватывает clean install, точный Xray, новую версию, equal-version no-op, downgrade refusal, rollback, locks, persistence, fail-closed ownership, Stable signature/index, WebUI/cache и запрещённые подсистемы.

Публичный clean installer был исполнен без изменений в чистом `chroot` с точным публичным IPK и реальными `preinst+data+postinst`. Результат: `current -> releases/1.0.0-r1`, Xray `26.7.28` с SHA-256 `4b8af237444801bf17b3dc10a1c5c24581fbe3d433eba3d78c6c3a0da1df56fc`; production-состояние не изменилось.

На разрешённом физическом роутере точный публичный installer подтвердил установленный пакет как актуальный. Подписанный Stable-check и фактическая команда update вернули `relation=equal`, `updateAvailable=false`, `sameVersionPolicy=NO_OP_SUCCESS`. До и после совпали 19 persistent-файлов; primary/updater services, Xray, WebUI HTTP 200 и native-auth HTTP 401 здоровы. В WebUI кнопка показала «Установлена актуальная версия 1.0.0-r1» и отключённое действие «Обновлений нет».

Полный WebUI audit: 20 действий кнопок и 23 endpoint binding, без отсутствующих handlers/endpoints. Сохранены пользовательские серверы, подписка, активный сервер и интерфейс `Proxy0`; автоматическое переключение остаётся выключено. Полный BROray отсутствует, совместное ownership остаётся fail-closed. Production server и репозиторий `BROadmin/BROray` не изменялись.

Stable minisign identity: key ID `F8ABF7C93FAB7C1F`, public key SHA-256 `b1587b8407f0c0443a361ed29b839319b66912b1b71414bcf31e848c29eab696`. Encrypted GitHub Actions secret присутствует; локальный plaintext private key необратимо удалён. Repository secret scan не обнаружил приватных ключей, токенов или предоставленных учётных данных.

Все 50 material failures R0010 сохранены отдельными JSON с валидными SHA-256 sidecars. R049 подтверждает полное применение патча после обрезанного ответа, а R050 отклоняет недоказательный счётчик credential scan до исправленного аудита; скрытых retry не выполнялось. Итоговые machine-readable записи находятся в `checkpoints/R0010/`.

## Следующий этап

`DEFINE_AND_AUTHORIZE_R0011_BEFORE_ANY_POST_RELEASE_CHANGE`
