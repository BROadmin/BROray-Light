# BROray-Light 2.0.0 — R0013, checkpoint P34

Публичная версия и пакет: `2.0.0`, будущий тег: `v2.0.0`. Согласованный служебный releaseId/candidateId: `2.0.0-r1`.
Кандидат пока не готов: `candidateReady=false`, `releaseReady=false`. Публичный выпуск не создан.

## Подтверждённые результаты

База — принятый Light r1 (`9e5fce9bfa7c82bfc2f2654d80fd3987c5259963`) и выборочные изменения опубликованного BROray 3.1.0-r09c02. Незавершённый R0012 не используется как сборочный вход. При повторной проверке 502 прежних файла совпали по SHA-256; три ранее описанных исключения — служебные AGENTS, WORKLOG и статус R0012.

В [CI P34](https://github.com/BROadmin/BROray-Light/actions/runs/34527153274) прошли текущие изолированные проверки. Их границы не равны полной приёмке кандидата:

| Компонент | Проверки | Что действительно проверено |
| --- | ---: | --- |
| RAM и общие блокировки | 38 | Настоящая tmpfs, процессы, конкуренция, dash и native BusyBox |
| Updater и S23 | 32 | Реальные тестовые подписи и канонический формат слота, подставные приложение/служба |
| Допуск старого r1 и журнал блокировок | 42 | Неизменённый старый updater, вызовы CLI и WebUI `update --json`, имитация потери RAM |
| Перенос старого рабочего каталога | 20 | Перенос внутри RAM и возврат исходных байтов/inode при откате |
| Внешние файлы платформы | 32 | Реальные байты r1/new, журнал по каждому файлу, частичная замена и возврат |
| Откат Xray | 32 | Настоящие файлы; процессы и блокировка подставлены для проверки порядка |
| Пути приложения в RAM | 22 | Скомпилированные скрипты, фиксированные пути, права, подмена окружения и общий lock adapter |

Подробности и SHA-256: `R1-WEBUI-AND-JOURNAL-P27.json`, `R1-RAM-VALIDATION-P28.json`, `PLATFORM-VALIDATION-P30.json`, `XRAY-ROLLBACK-VALIDATION-P32.json`, `RUNTIME-PATHS-AND-BUILDS-P34.json`.
Предыдущие проверки выборочного порта Xray, имён серверов, каталога версий и DOM/HTTP сохранены в ранних checkpoint.

## Последние инженерные сборки

`dist/R0013/p34-engineering-build-A` и `dist/R0013/p34-engineering-build-B` собраны отдельными локальными процессами со свежими входными деревьями. Все восемь артефактов совпали побайтно; семь структурных проверок архива/IPK/manifests прошли. Это НЕ финальные независимые clean-checkout runners и НЕ готовый кандидат.

| Основной артефакт | Байт | SHA-256 |
| --- | ---: | --- |
| broray-light-app-2.0.0-r1.tar.gz | 208749 | `263d57ca9a97ed8338dc54afb67ea0a5118536ae53ee7ee06c5e24488957a1ee` |
| broray-light-install-2.0.0.sh | 3860 | `317bc27efc6bb0345a288dddfa89d59024a79e16a5a663f2e6cdd1993c0dcc05` |
| broray-light-updater-platform-5-light2-ram.tar.gz | 134529 | `763fc09fe87e7b4092d036aab6a4f2960dd3983a35586bafd0b2eac97ec57d60` |
| broray-light_2.0.0_aarch64-3.10.ipk | 12964354 | `5465d0a94c31026ee4d18892aae51d23b8dc35f880d33b33d2105fb986db9dbe` |
| release.json | 597 | `72db44b67ebe8b60500e62fb1bf50f748691faa4bead799c2f1f140b412d01b4` |

Установленный Xray сохраняется при обновлении приложения. Для чистой установки зафиксирован Xray 26.9.9, официальный архив/digest и ELF64 AArch64; его binary SHA-256: `c1defe42b6db958a97c5e049a02a00a4baaedaca7b51c1c229f0830e288acef5`.

## Что ещё не принято

Нужно связать проверенные компоненты в реальный lifecycle: атомарно мигрировать lighttpd config вместе с ownership receipt, обновить S24/startup/boot recovery, перенести старые оперативные данные и исправить clean-install postinst. Простая сборка новых путей этого не доказывает. Инженерные P34-артефакты нельзя устанавливать как готовый кандидат.

После интеграции обязательны полные clean install, r1 update, equal-version, downgrade refusal, rollback, persistence, все кнопки/API и native authentication/session, browser desktop/mobile, финальные независимые Build A/B, подпись через существующий encrypted Actions secret и авторизованная приёмка на тестовом роутере. Публикация и проверка публичных байтов — отдельный последующий gate.

В R0013 роутер, production server, full-BROray и публичные релизы не изменялись. Ошибки P26/P29/P31/P33 сохранены отдельными JSON до исправленных ревизий; скрытых повторов провалившихся тестов не было.

Следующий этап: `P35_CONFIG_RECEIPT_ATOMIC_MIGRATION_THEN_S24_BOOT_ROLLBACK_AND_FULL_R1_STARTUP`.

## Все acceptance gates

| Gate | Статус | Evidence |
| --- | --- | --- |
| pinned_donor_archives | PASS | UPSTREAM-DELTA-P2.json |
| complete_upstream_change_map | PASS_AUDIT_ONLY | UPSTREAM-PORT-MAP-P2.json |
| scoped_xray_identity | PASS_ISOLATED_LINUX | RAM-BOOTSTRAP-VALIDATION-P15.json |
| busybox_ash_overlay_syntax | PASS | RUNTIME-PATHS-AND-BUILDS-P34.json |
| active_subscription_rename_and_rollback | PASS_ISOLATED_ROUTER_BOUNDARY_MOCKED | SUBSCRIPTION-NAME-P6.json |
| xray_catalog_and_explicit_consent | PASS_POLICY_OFFICIAL_NETWORK_MOCKED | RAM-BOOTSTRAP-VALIDATION-P15.json |
| home_xray_controls | PASS_DOM_HTTP_BOUNDARIES_MOCKED | RAM-BOOTSTRAP-VALIDATION-P15.json |
| published_r1_to_2_0_0_admission | PASS_COMPARATOR_ONLY | UPGRADE-AND-XRAY-P10.json |
| canonical_source_and_final_input_manifest | PASS_ENGINEERING_INPUTS_FINAL_PENDING | RAM-BOOTSTRAP-VALIDATION-P15.json |
| xray_clean_binary_verification | PASS_ARCHIVE_DIGEST_BINARY_ELF | UPGRADE-AND-XRAY-P10.json |
| all_webui_buttons_and_apis | NOT_RUN_FULL_CANDIDATE | — |
| native_authentication_and_sessions | NOT_RUN_FULL_CANDIDATE | — |
| protected_tmpfs_all_operational_scratch | COMPONENT_PASS_LIFECYCLE_PENDING | RUNTIME-PATHS-AND-BUILDS-P34.json |
| archive_updater_and_ownership_safety | NOT_RUN_FULL_CANDIDATE | — |
| isolated_clean_install | NOT_RUN | — |
| isolated_update_from_r1 | PENDING_FULL_LIFECYCLE_COMPONENTS_PASS | process-failures/FAILURE-P16-PERSISTENT-LOCK-DOMAIN.json |
| isolated_equal_version | NOT_RUN | — |
| isolated_downgrade_refusal | NOT_RUN | — |
| forced_health_rollback | NOT_RUN_FULL_CANDIDATE | — |
| persistence | NOT_RUN_FULL_CANDIDATE | — |
| independent_build_a | PASS_PRELIMINARY_LOCAL_NOT_FINAL_ACCEPTANCE | RUNTIME-PATHS-AND-BUILDS-P34.json |
| independent_build_b | PASS_PRELIMINARY_LOCAL_NOT_FINAL_ACCEPTANCE | RUNTIME-PATHS-AND-BUILDS-P34.json |
| a_b_byte_reproducibility | PASS_PRELIMINARY_LOCAL_NOT_FINAL_ACCEPTANCE | RUNTIME-PATHS-AND-BUILDS-P34.json |
| existing_trust_root_signing | NOT_RUN | — |
| browser_desktop_mobile_layout | NOT_RUN | — |
| authorized_router_validation | NOT_RUN | — |
| immutable_release_and_public_byte_validation | NOT_PUBLISHED | — |
| public_version_vs_internal_updater_identity | PASS_SHELL_JQ_AND_MOCK_DOM_HTTP | RAM-BOOTSTRAP-VALIDATION-P15.json |
| clean_bootstrap_and_installer_protected_ram | PASS_BOUNDED_UNIT_TRANSACTIONS_NOT_TARGET | RAM-BOOTSTRAP-VALIDATION-P15.json |
| engineering_package_structure_hashes_and_modes | PASS | RUNTIME-PATHS-AND-BUILDS-P34.json |
| preexisting_r0012_preservation | PASS_502_FILES_WITH_THREE_EXPLICIT_ROUTING_LOG_EXCEPTIONS | R0012-PRESERVATION-P34.json |
| shared_ram_namespace_and_locks | PASS_REAL_TMPFS_NATIVE_BUSYBOX | NATIVE-UPDATER-VALIDATION-P22.json |
| updater_core_transactions_and_ready_service | PASS_CANONICAL_SLOT_FORMAT_FIXTURE_APP_SERVICE_REAL_MINISIGN_BUSYBOX | UPDATER-PLATFORM-AND-BUILDS-P23.json |
| ram_updater_platform_package_binding | PASS_ENGINEERING_NOT_MIGRATION_ACCEPTANCE | UPDATER-PLATFORM-AND-BUILDS-P23.json |
| exact_live_r1_webui_cli_admission | PASS_FIXTURE_SIGNED_TRANSACTIONS | R1-WEBUI-AND-JOURNAL-P27.json |
| legacy_lock_journal_and_ram_loss_reconciliation | PASS_BOUNDED | R1-WEBUI-AND-JOURNAL-P27.json |
| legacy_ram_namespace_handoff_and_restore | PASS_BOUNDED | R1-RAM-VALIDATION-P28.json |
| external_platform_activation_and_restore | PASS_REAL_BYTES_FIXTURE_SERVICE | PLATFORM-VALIDATION-P30.json |
| xray_rollback_before_fence_release | PASS_REAL_FILES_MOCKED_PROCESS_FENCE | XRAY-ROLLBACK-VALIDATION-P32.json |
| compiled_application_ram_paths_and_environment_guard | PASS_BOUNDED | RUNTIME-PATHS-AND-BUILDS-P34.json |
| config_publication_receipt_migration | NOT_IMPLEMENTED | — |
| coordinated_service_start_and_boot_rollback | NOT_IMPLEMENTED | — |

Machine-readable checkpoint: `CHECKPOINT.json`; gates: `VALIDATION.json`; исходные SHA-256: `PRODUCED-SOURCE-MANIFEST.json`; записи: `SHA256SUMS`.
