# BROray-Light 2.0.0 — R0013, checkpoint P37

Публичная версия: `2.0.0`; служебный releaseId: `2.0.0-r1`; будущий тег: `v2.0.0`.
`candidateReady=false`, `releaseReady=false`. Публичный выпуск не создан.

## Подтверждено

База — принятый Light r1 (`9e5fce9bfa7c82bfc2f2654d80fd3987c5259963`) и выборочный порт опубликованного BROray 3.1.0-r09c02. Неоконченный R0012 не включён автоматически; 502 прежних файла снова совпали по SHA-256, кроме трёх ранее описанных служебных исключений.

[CI P37](https://github.com/BROadmin/BROray-Light/actions/runs/34530275676) завершился успешно на исходниках `e13b4f6ad9ce615a0591103c7d818cfd81061569`.

- P35: 28 проверок пары lighttpd config / ownership receipt, включая прерывание между файлами, точный откат и отказ при чужих объектах. Служба подставная.
- P37: 30 проверок настоящего S24, процессов Linux и RAM-публикации: запуск/статус/перезапуск/остановка, отдельная остановка native-auth sidecar, чужой executable/аргументы/PID, дубли и блокировка updater. Работа daemon, Xray и команды Keenetic имитируются.
- Сохранены предыдущие результаты: RAM и блокировки — 38; updater/S23 — 32; допуск r1 и журнал — 42; RAM handoff — 20; внешняя платформа — 32; откат Xray — 32; скомпилированные RAM-пути — 22.
- P36 провален: очистка временного каталога теряла исходный код ошибки. Ошибка сохранена отдельным JSON до P37; исправление и отрицательные тесты приняты.

## Инженерные Build A/B

`dist/R0013/p37-engineering-build-A` и `dist/R0013/p37-engineering-build-B`: отдельные локальные процессы, свежие входные деревья, восемь побайтно одинаковых файлов и семь структурных PASS. Это не финальные независимые clean-checkout сборки, не подписанные релизные файлы и не готовый кандидат.

| Артефакт | Байт | SHA-256 |
| --- | ---: | --- |
| ENGINEERING-MANIFEST.json | 2347 | `a8b3b50b6135a5deebc3a2b8aadc763a98cbaa47b78b90145852dab4ceec91d3` |
| INPUT-MANIFEST.json | 39748 | `15de13149e5531eae0ea89d3d6ffaff05272725d9e27c060dd44c27e0f9f8fe9` |
| SHA256SUMS | 670 | `6d0e28d90f563bb2c19f2ad2e54e564de70bfadf8c98a13328e1a1d46fd1d6db` |
| broray-light-app-2.0.0-r1.tar.gz | 212656 | `d68b5e590ca4833e8f0f92cbc880c7de51e616276b1f9e5e9bd46056c06a1673` |
| broray-light-install-2.0.0.sh | 3860 | `d405c9ec337487004e69605a6bf88da0eac3a685987b204f114ae981e041a3c1` |
| broray-light-updater-platform-5-light2-ram.tar.gz | 134529 | `763fc09fe87e7b4092d036aab6a4f2960dd3983a35586bafd0b2eac97ec57d60` |
| broray-light_2.0.0_aarch64-3.10.ipk | 12968928 | `4687d09b411a78b63d11ccc24b9565065d9e66be4baf557a6970c5a647f5ec9b` |
| release.json | 597 | `973ed76bc3d3ddabb5e3d3f6b0030de931cec004f7ad8fc34c43562e59a0350f` |

Для чистой установки закреплён Xray 26.9.9, ELF64 AArch64; SHA-256 бинарника `c1defe42b6db958a97c5e049a02a00a4baaedaca7b51c1c229f0830e288acef5`. App-slot обновление сохраняет установленный Xray.

## Осталось

Проверенные части нужно связать в полный переход с r1: перенос старых рабочих данных в RAM, вход из неизменённого старого updater, согласованный откат внешних файлов и config, восстановление после перезагрузки, clean-install postinst. Инженерные P37-артефакты не предназначены для установки на роутер.

Затем обязательны полные install/update/equal/downgrade/rollback/persistence, все кнопки/API, native authentication/session, browser desktop/mobile, финальные независимые Build A/B, подпись существующим Actions secret и авторизованная приёмка на тестовом роутере. Публикация и публичные байты — последующий gate.

В R0013 роутер, production server, полный BROray и публичные релизы не изменялись. Все material failures сохранены; скрытых повторов провалившегося revision нет.

Следующий этап: `P38_LEGACY_RUNTIME_DATA_HANDOFF_AND_FULL_R1_ENTRY_BOOT_ROLLBACK`.

## Acceptance gates

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
| independent_build_a | PASS_PRELIMINARY_LOCAL_NOT_FINAL_ACCEPTANCE | SERVICE-AND-BUILDS-P37.json |
| independent_build_b | PASS_PRELIMINARY_LOCAL_NOT_FINAL_ACCEPTANCE | SERVICE-AND-BUILDS-P37.json |
| a_b_byte_reproducibility | PASS_PRELIMINARY_LOCAL_NOT_FINAL_ACCEPTANCE | SERVICE-AND-BUILDS-P37.json |
| existing_trust_root_signing | NOT_RUN | — |
| browser_desktop_mobile_layout | NOT_RUN | — |
| authorized_router_validation | NOT_RUN | — |
| immutable_release_and_public_byte_validation | NOT_PUBLISHED | — |
| public_version_vs_internal_updater_identity | PASS_SHELL_JQ_AND_MOCK_DOM_HTTP | RAM-BOOTSTRAP-VALIDATION-P15.json |
| clean_bootstrap_and_installer_protected_ram | PASS_BOUNDED_UNIT_TRANSACTIONS_NOT_TARGET | RAM-BOOTSTRAP-VALIDATION-P15.json |
| engineering_package_structure_hashes_and_modes | PASS | SERVICE-AND-BUILDS-P37.json |
| preexisting_r0012_preservation | PASS_502_FILES_WITH_THREE_EXPLICIT_ROUTING_LOG_EXCEPTIONS | R0012-PRESERVATION-P37.json |
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
| coordinated_service_start_and_boot_rollback | NOT_IMPLEMENTED | — |
| scoped_s24_and_private_ram_publication | PASS_REAL_S24_PROCESSES_MOCK_DAEMON_AND_KEENETIC | SERVICE-AND-BUILDS-P37.json |

Machine-readable: `CHECKPOINT.json`, `VALIDATION.json`; SHA-256 исходников: `PRODUCED-SOURCE-MANIFEST.json`; SHA-256 записей: `SHA256SUMS`.
