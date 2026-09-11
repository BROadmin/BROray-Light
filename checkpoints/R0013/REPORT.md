# BROray-Light 2.0.0 — R0013, checkpoint P70

## Текущее состояние P83 — реальная замена выполнена, вход требует исправления

Полный BROray штатно удалён с тестового роутера 192.168.1.1 после проверенной резервной копии вне роутера. Отдельно удалены только 12 проверенных файлов старого S99 bootstrap и завершённого handoff. Установлены coreutils-stat и BROray-Light 2.0.0 через настоящий opkg. P72 Build A/B совпадают побайтно; все пять задач регрессии run 34572894126 завершились успешно. P79 установка и P80 службы, манифест, Xray 26.9.9, RAM-каталоги прошли проверку.

P81 выявил реальную ошибку: CGI отвечает HTTP 500 до проверки пароля, потому что runtime guard вызывается до инициализации PATH и не находит Entware stat. Ошибка и диагноз сохранены отдельно (FAILURE-P81-NATIVE-TARGET-LOGIN, TARGET-CGI-DIAGNOSIS-P82). P83 исправляет только порядок подготовки PATH и добавляет тесты пустого/подменённого PATH. Новая сборка и повторная целевая приёмка обязательны. На роутере пока находятся точные P72-байты; скрытый hotpatch и повторная отправка пароля не выполнялись. candidateReady=false, релиз 2.0.0 не опубликован.

Следующий этап: проверить P83 новым Build A/B и native CGI regression, затем выполнить контролируемую замену чистого Light-пакета и повторить native login. Резервные копии находятся в приватном игнорируемом dist/R0013/private-target/p74, их хеши — TARGET-BACKUP-P74 и TARGET-SUPPLEMENT-BACKUP-P77.

## Исторический отчёт P70 (описание блокера до нового разрешения пользователя)

Статус: **BLOCKED_FAIL_CLOSED_USER_TARGET_DECISION_REQUIRED**. `candidateReady=false`, `releaseReady=false`. Это неподписанная инженерная сборка, не готовый кандидат и не опубликованный релиз.

## Что действительно выполнено

- Выборочный порт из зафиксированного BROray 3.1.0-r09 / packaged 3.1.0-r09c02 поверх принятого Light r1 `9e5fce9bfa7c82bfc2f2654d80fd3987c5259963`. Канонический R0008 `684b27bdb53e545047419baa87c63dd86dffa469` сохранён. Публичная/package версия **2.0.0**, технический updater releaseId **2.0.0-r1**.
- [P64: все пять заданий регрессии PASS](https://github.com/BROadmin/BROray-Light/actions/runs/34549087783), source `ebae309b93aee000ed1c5b5743385ba39e33ed98`. **479** проверок из JSON, 20 архивов evidence проверены SHA-256. Повторные RAM preflight и retirement subset не удваивают число. Командные проверки без JSON дополнительно не посчитаны.
- Полные подготовленные application scripts на dash и BusyBox: r1 → 2.0.0, equal-version no-op, downgrade refusal, следующее обновление через новый updater, forced health rollback, persistence — **12 PASS**. Это настоящие app/daemon/updater/S24 скрипты; OS/Xray/network границы этого набора подменены. Исправлен подтверждённый дефект остановки daemon: безопасное ожидание явного внешнего sleep и адресное завершение только собственного дочернего процесса. Отдельно **8 PASS** сигналов/остановки.
- Native HTTP/CGI/session: **96 PASS** настоящего кода приложения и curl, с loopback-имитатором ответа KeeneticOS. Это не доказательство native SCGI на физическом устройстве.
- [P63: независимые Build A и B PASS](https://github.com/BROadmin/BROray-Light/actions/runs/34549442753), source `f38cfb7d00d6435d51a90672cdf2b39726e1f027`. Разные свежие Linux jobs, checkout и загрузки входов; **8/8 файлов побайтно совпали**.
- Точный собранный clean installer/IPK с preinst/data/postinst, настоящими S23/S24/lighttpd и HTTP — **8 PASS** на dash/BusyBox. ARM64 Xray **26.9.9** реально запускается через QEMU. Проверены manifest, login/session/logout, restart/stop, шесть постоянных файлов и очистка operational scratch. Извлечение/порядок opkg эмулирует тестовый адаптер; настоящий Entware dependency solver и публикация Keenetic не проверены.
- [P66: Chromium WebUI — 22 PASS](https://github.com/BROadmin/BROray-Light/actions/runs/34550298557), source `40f1ac096ad65cb62fa218bf83d542de2d9d3bf8`. Все отображаемые кнопки покрыты сгруппированными сценариями, включая cancel/accept удаления и переустановки Xray. **HTTP API тестовые**, поэтому полная функциональная backend-приёмка остаётся открытой. 9 снимков Home/Servers/Subscriptions на 390/768/1440 px просмотрены: круглый логотип, зелёные заголовки, отступы, переносы, без видимых наложений или горизонтального overflow.
- P70: обе сборки скачаны локально с проверкой ZIP и каждого файла; побайтное равенство перепроверено. Все **19 frontend-файлов** из browser test совпадают с файлами в собранном app-архиве.
- 502 прежних файла R0012 повторно проверены без изменений; три исторически описанных routing/log исключения сохранены. 90 файлов текущего source manifest совпали по SHA-256.

## Реальный блокер — целевое устройство

Read-only SSH-проверка `192.168.1.1` выявила **полный BROray**:

- пакет `broray - 3.0.0-r14`;
- каталог `/opt/broray`, root-owned mode 700;
- `S24broray -> /opt/broray/current/init/S24broray`;
- каталог и служба BROray-Light отсутствуют;
- `/tmp` — tmpfs, `/opt` — ubifs;
- `/opt/bin/stat -> /opt/bin/busybox` не поддерживает необходимые `-f` и `-c`; `coreutils-stat` не установлен.

Это не историческое состояние принятого Light r1. Установка поверх полного продукта запрещена инвариантом ownership. Полный BROray не удалялся и не изменялся. Пакеты, файлы, настройки и службы на роутере не менялись; выполнялись только read-only диагностики. Production server не затронут.

FIRST-ERROR сохранён отдельно: P67 key-only SSH authentication; P68 stat capability; P69 full BROray ownership. После каждой ошибки использована отдельно записанная диагностическая ревизия, без скрытого повтора установки. P54/P60/P62 daemon failures сохранены и исправлены с PASS в P64. P65 ошибка управления браузерным confirm сохранена; P66 проверил confirm на независимом Linux browser harness. Исторические проваленные R0012 workflows не относятся к R0013 gates и не объявляются зелёными.

## Артефакты и SHA-256

Локальные каталоги: `dist/R0013/p63-independent-build-A/` и `dist/R0013/p63-independent-build-B/`. Ниже одинаковые SHA-256 для A и B. `release.json` **не подписан**.

| Артефакт | Байты | SHA-256 |
|---|---:|---|
| ENGINEERING-MANIFEST.json | 2347 | `23f5ce63daf825d0412cb990853777238c9bc32f93cf9a440bf0d42decac8d00` |
| INPUT-MANIFEST.json | 40798 | `9c4dc2cb507d5b0f9d0359bca7e4fa359b1126f203d02e3523d9fae8815fa1be` |
| SHA256SUMS | 670 | `abdba3617272f8335e359143e3aa907b4d8f84b8667cc8bba365bce79e666378` |
| broray-light-app-2.0.0-r1.tar.gz | 229432 | `57a02b3101b3ce120932fd15ea88241b29c81f279b3bbb0e43a5c9c8854f6496` |
| broray-light-install-2.0.0.sh | 3860 | `06b9ce1ba7127f19cccee99b8b87e8670260bb92ce68152e394f3655612889f2` |
| broray-light-updater-platform-5-light2-ram.tar.gz | 136061 | `aa814efcb6d75f02c061b3928588439466e9ee02af127bd7eac376786410fc1b` |
| broray-light_2.0.0_aarch64-3.10.ipk | 12991349 | `8e855ab876de2d000849241b36c80397da97a57f5755ba9ca83df75734d7c7a4` |
| release.json | 597 | `b7da9bd2f6fc4ee69f1c26e780167ef92e586d98467fe187870793f6ad912ad3` |

Приложение: 146 файлов, 855021 логических байт без Xray; SHA-256 app sums `91b949910948897d3c62a3fc1b47b108f8cd6cb76c6b4f41bb8f83a8763a95bc`. Xray binary: 35061884 байта, SHA-256 `c1defe42b6db958a97c5e049a02a00a4baaedaca7b51c1c229f0830e288acef5`. Это логические размеры, не замер выделенных блоков на роутере. Не следует менять immutable engineering manifest после сборки: его pendingGates отражают статус на момент build; последующие результаты находятся в checkpoint.

## Каждый acceptance gate

Ни один частичный или ограниченный тест не заменяет финальную приёмку. Статус содержит проверенную границу; `MOCKED` / `FIXTURE` / `BOUNDED` — имитация или ограниченный набор; `PENDING` / `PARTIAL` — не закрыт полностью. Machine-readable источник: [VALIDATION.json](VALIDATION.json).

| Gate | Результат | Evidence |
|---|---|---|
| pinned_donor_archives | PASS | UPSTREAM-DELTA-P2.json |
| complete_upstream_change_map | PASS_AUDIT_ONLY | UPSTREAM-PORT-MAP-P2.json |
| scoped_xray_identity | PASS_ISOLATED_LINUX | RAM-BOOTSTRAP-VALIDATION-P15.json |
| busybox_ash_overlay_syntax | PASS | RUNTIME-PATHS-AND-BUILDS-P34.json |
| active_subscription_rename_and_rollback | PASS_ISOLATED_ROUTER_BOUNDARY_MOCKED | SUBSCRIPTION-NAME-P6.json |
| xray_catalog_and_explicit_consent | PASS_POLICY_OFFICIAL_NETWORK_MOCKED | RAM-BOOTSTRAP-VALIDATION-P15.json |
| home_xray_controls | PASS_DOM_HTTP_BOUNDARIES_MOCKED | RAM-BOOTSTRAP-VALIDATION-P15.json |
| published_r1_to_2_0_0_admission | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| canonical_source_and_final_input_manifest | PASS_ENGINEERING_INPUTS_FINAL_PENDING | RAM-BOOTSTRAP-VALIDATION-P15.json |
| xray_clean_binary_verification | PASS_ARCHIVE_DIGEST_ELF_AND_ACTUAL_ARM64_BINARY_QEMU | INDEPENDENT-BUILDS-AND-CLEAN-P63.json |
| all_webui_buttons_and_apis | PARTIAL_ALL_FRONTEND_CONTROLS_PASS_FULL_BACKEND_FUNCTIONAL_PENDING | BROWSER-CONTROLS-P66.json |
| native_authentication_and_sessions | PASS_NATIVE_HTTP_CGI_SESSIONS_PHYSICAL_SCGI_PENDING | REGRESSION-P64.json |
| protected_tmpfs_all_operational_scratch | PASS_ISOLATED_LIFECYCLE_TARGET_STAT_PREREQUISITE_BLOCKED | INDEPENDENT-BUILDS-AND-CLEAN-P63.json |
| archive_updater_and_ownership_safety | PASS_ISOLATED_COMPONENTS_FINAL_SIGNED_TARGET_PENDING | REGRESSION-P64.json |
| isolated_clean_install | PASS_BUILT_PACKAGE_REAL_SERVICES_HTTP_QEMU_OS_ADAPTERS | INDEPENDENT-BUILDS-AND-CLEAN-P63.json |
| isolated_update_from_r1 | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| isolated_equal_version | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| isolated_downgrade_refusal | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| forced_health_rollback | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| persistence | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| independent_build_a | PASS_INDEPENDENT_LINUX_UNSIGNED_BYTES | INDEPENDENT-BUILDS-AND-CLEAN-P63.json |
| independent_build_b | PASS_INDEPENDENT_LINUX_UNSIGNED_BYTES | INDEPENDENT-BUILDS-AND-CLEAN-P63.json |
| a_b_byte_reproducibility | PASS_INDEPENDENT_LINUX_UNSIGNED_BYTES | INDEPENDENT-BUILDS-AND-CLEAN-P63.json |
| existing_trust_root_signing | NOT_RUN | — |
| browser_desktop_mobile_layout | PASS_CHROMIUM_FIXTURE_390_768_1440_NINE_IMAGES_REVIEWED | BROWSER-CONTROLS-P66.json |
| authorized_router_validation | BLOCKED_FULL_BROray_OWNERSHIP_AND_STAT_CAPABILITY | process-failures/FAILURE-P69-TARGET-FULL-BRORAY-OWNERSHIP.json |
| immutable_release_and_public_byte_validation | NOT_PUBLISHED | — |
| public_version_vs_internal_updater_identity | PASS_SHELL_JQ_AND_MOCK_DOM_HTTP | RAM-BOOTSTRAP-VALIDATION-P15.json |
| clean_bootstrap_and_installer_protected_ram | PASS_BUILT_PACKAGE_REAL_SERVICES_HTTP_QEMU_OS_ADAPTERS | INDEPENDENT-BUILDS-AND-CLEAN-P63.json |
| engineering_package_structure_hashes_and_modes | PASS_BUILT_PACKAGE_REAL_SERVICES_HTTP_QEMU_OS_ADAPTERS | INDEPENDENT-BUILDS-AND-CLEAN-P63.json |
| preexisting_r0012_preservation | PASS_502_FILES_WITH_THREE_EXPLICIT_ROUTING_LOG_EXCEPTIONS | R0012-PRESERVATION-P70.json |
| shared_ram_namespace_and_locks | PASS_REAL_TMPFS_NATIVE_BUSYBOX | NATIVE-UPDATER-VALIDATION-P22.json |
| updater_core_transactions_and_ready_service | PASS_CANONICAL_SLOT_FORMAT_FIXTURE_APP_SERVICE_REAL_MINISIGN_BUSYBOX | UPDATER-PLATFORM-AND-BUILDS-P23.json |
| ram_updater_platform_package_binding | PASS_ENGINEERING_NOT_MIGRATION_ACCEPTANCE | UPDATER-PLATFORM-AND-BUILDS-P23.json |
| exact_live_r1_webui_cli_admission | PASS_FIXTURE_SIGNED_TRANSACTIONS | R1-WEBUI-AND-JOURNAL-P27.json |
| legacy_lock_journal_and_ram_loss_reconciliation | PASS_BOUNDED | R1-WEBUI-AND-JOURNAL-P27.json |
| legacy_ram_namespace_handoff_and_restore | PASS_BOUNDED | R1-RAM-VALIDATION-P28.json |
| external_platform_activation_and_restore | PASS_REAL_BYTES_FIXTURE_SERVICE | PLATFORM-VALIDATION-P30.json |
| xray_rollback_before_fence_release | PASS_REAL_FILES_MOCKED_PROCESS_FENCE | XRAY-ROLLBACK-VALIDATION-P32.json |
| compiled_application_ram_paths_and_environment_guard | PASS_BOUNDED | RUNTIME-PATHS-AND-BUILDS-P34.json |
| config_publication_receipt_migration | PASS_REAL_CONFIG_BYTES_FIXTURE_SERVICE | WEB-CONFIG-VALIDATION-P35.json |
| coordinated_service_start_and_boot_rollback | PASS_BOUNDED_P52_EARLY_S23_AND_P48_DEAD_OWNER_FULL_CANDIDATE_PENDING | EARLY-BOOT-AND-CLEANUP-P52.json |
| scoped_s24_and_private_ram_publication | PASS_SCOPED_SERVICES_AND_CLEAN_PACKAGE_ISOLATED_TARGET_PENDING | REGRESSION-P64.json |
| legacy_runtime_tree_ram_handoff_and_byte_rollback | PASS_BOUNDED_REAL_CROSS_FILESYSTEM_DASH_BUSYBOX | RUNTIME-TREES-AND-BUILDS-P40.json |
| actual_lighttpd_nginx_pid_and_stop_contract | PASS_BOUNDED_REAL_LINUX_DAEMONS | ACTUAL-DAEMON-VALIDATION-P39.json |
| new_updater_complete_prepared_app_service_transition | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| target_stat_prerequisite | BLOCKED_TARGET_STAT_MISSING_REQUIRED_F_AND_C_OPTIONS | process-failures/FAILURE-P68-TARGET-STAT-CAPABILITY.json |

## Checkpoint и продолжение

Точка возобновления: [CHECKPOINT.json](CHECKPOINT.json); активный blocker: [FAILURE-P69-TARGET-FULL-BRORAY-OWNERSHIP.json](process-failures/FAILURE-P69-TARGET-FULL-BRORAY-OWNERSHIP.json). SHA-256 всех JSON/MD — [SHA256SUMS](SHA256SUMS) и sidecars.

Точный следующий этап: `USER_SELECT_CLEAN_TEST_TARGET_OR_EXPLICITLY_AUTHORIZE_SEPARATELY_PLANNED_FULL_BROray_REMOVAL_THEN_RESOLVE_STAT_PREREQUISITE`.

Сначала требуется выбор подходящего тестового устройства либо отдельное явное решение пользователя о полном BROray на текущем адресе. Нельзя автоматически сносить его или устанавливать зависимости. После разрешения ownership — оформить совместимость stat/Entware в новой именованной ревизии, повторить затронутые gates и независимые сборки, завершить полную функциональную backend/WebUI-приёмку, подпись существующим encrypted Actions secret, целевую установку/обновление и проверку опубликованных байтов/документации. Подпись и публикация сейчас не выполнялись.
