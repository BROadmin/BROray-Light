# BROray-Light 2.0.0 — R0013, checkpoint P43

Публичная версия `2.0.0`, служебный releaseId `2.0.0-r1`, будущий тег `v2.0.0`.
`candidateReady=false`, `releaseReady=false`. Релиз не создан; роутер и production server не изменялись.

## Подтверждённый результат

База — принятый Light r1 `9e5fce9bfa7c82bfc2f2654d80fd3987c5259963` и выборочный порт опубликованного BROray 3.1.0-r09c02. Сохранены VLESS-only, три страницы, native authentication и ограничения отдельного продукта. 502 прежних файла R0012 совпали по SHA-256; три ранее описанных исключения относятся к маршрутизации задачи и журналу.

- P39: 42 PASS, включая настоящие lighttpd/nginx, точный PID/executable/argv и безопасную остановку.
- P40: 22 PASS переноса run/logs/tmp/update между разными файловыми системами, сохранения сессий/байтов, частичного копирования/удаления/отката и отказа при чужих файлах/PID. Служба в этом наборе имитируется.
- P42: обновление r1 → 2.0.0 прошло с неизменённым старым updater, настоящими старым и новым S24 и новым runtime-prepare. Старая транзакция завершена, сессия сохранена. Рабочий цикл daemon, lighttpd и команды публикации в этом наборе подставные.
- Полная ревизия P42 не PASS: очистка тестового tmpfs вернула ошибку. Основной результат сохранён отдельно. P43 исправляет ожидание освобождения файловых ссылок; его итог ещё не принят.

## Инженерные Build A/B

`dist/R0013/p40-engineering-build-A` и `dist/R0013/p40-engineering-build-B`: отдельные локальные процессы, свежие входные деревья; восемь файлов совпали побайтно, семь структурных проверок PASS. Эти сборки предшествуют новому координатору P41, не подписаны и не предназначены для роутера.

| Артефакт | Байт | SHA-256 |
| --- | ---: | --- |
| broray-light_2.0.0_aarch64-3.10.ipk | 12973977 | `3df606c6e9806d59ccb216183c7ac23a9a818a58fcf5be4db7ae1341711578f8` |
| broray-light-app-2.0.0-r1.tar.gz | 217650 | `a739d42dddc0611aa21e3a5f5163b789e2448051506c82a8a9783d5008d4a84e` |
| broray-light-install-2.0.0.sh | 3860 | `9481ee2d437506b987bc8d1e9d07ef4523d56fd0c8baa826ad40d7a96fe8f167` |
| broray-light-updater-platform-5-light2-ram.tar.gz | 134529 | `763fc09fe87e7b4092d036aab6a4f2960dd3983a35586bafd0b2eac97ec57d60` |
| ENGINEERING-MANIFEST.json | 2347 | `5f014b962e53b6436eaf7a65c9d17e30e021b2637b9fa090e053a577aa0a798a` |
| INPUT-MANIFEST.json | 40274 | `2ffe2c8b4dea6e542065092253e7fc8680c85e52935a2030654bb038e141a813` |
| release.json | 597 | `64867b461a1d39eba4ee9f2b642cf0e62e23b50571a54d5dca7386cb02cfa607` |
| SHA256SUMS | 670 | `113770d6c5cafbdf267399d80110d567b45e4ec5fd70319a076e7dae200a6459` |

Закреплён Xray 26.9.9 ELF64 AArch64, SHA-256 бинарника `c1defe42b6db958a97c5e049a02a00a4baaedaca7b51c1c229f0830e288acef5`; app-slot обновление сохраняет существующий runtime.

## Ошибки и следующий шаг

P41: cleanup скрыл основной исход; сохранён полный SHA-256 CI-журнала и excerpt.
P42: основной update PASS сохранён, но tmpfs остался занят после остановки перечисленных процессов. Точный оставшийся держатель ещё не установлен. P43 добавляет ограниченное ожидание и диагностику файловых ссылок; чужие процессы не завершает. Повтора той же неудачной ревизии не было. Остальные задания неудачных P41/P42 остановлены по FIRST-ERROR; дальнейшие CI-задания зависят от успешного live-entry gate.

Следующий этап: `P43_VALIDATE_LIVE_HEALTH_ROLLBACK_THEN_BOOT_RECOVERY_AND_FULL_CANDIDATE_GATES`.

Затем: восстановление/финализация после перезагрузки и потери RAM, clean-install postinst, полные install/update/equal/downgrade/rollback/persistence, каждая кнопка/API и native sessions, desktop/mobile browser, финальные независимые Build A/B и подпись через существующий encrypted Actions secret, авторизованная целевая приёмка. Публикация и проверка публичных байтов — отдельный последующий gate.

## Acceptance gates

| Gate | Результат | Evidence |
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
| isolated_update_from_r1 | PASS_BOUNDED_REAL_R1_ENGINE_AND_S24_DASH_FULL_CANDIDATE_PENDING | process-failures/FAILURE-P42-LIVE-FIXTURE-TMPFS-BUSY.json |
| isolated_equal_version | NOT_RUN | — |
| isolated_downgrade_refusal | NOT_RUN | — |
| forced_health_rollback | NOT_RUN_FULL_CANDIDATE | — |
| persistence | NOT_RUN_FULL_CANDIDATE | — |
| independent_build_a | PASS_PRELIMINARY_LOCAL_NOT_FINAL_ACCEPTANCE | RUNTIME-TREES-AND-BUILDS-P40.json |
| independent_build_b | PASS_PRELIMINARY_LOCAL_NOT_FINAL_ACCEPTANCE | RUNTIME-TREES-AND-BUILDS-P40.json |
| a_b_byte_reproducibility | PASS_PRELIMINARY_LOCAL_NOT_FINAL_ACCEPTANCE | RUNTIME-TREES-AND-BUILDS-P40.json |
| existing_trust_root_signing | NOT_RUN | — |
| browser_desktop_mobile_layout | NOT_RUN | — |
| authorized_router_validation | NOT_RUN | — |
| immutable_release_and_public_byte_validation | NOT_PUBLISHED | — |
| public_version_vs_internal_updater_identity | PASS_SHELL_JQ_AND_MOCK_DOM_HTTP | RAM-BOOTSTRAP-VALIDATION-P15.json |
| clean_bootstrap_and_installer_protected_ram | PASS_BOUNDED_UNIT_TRANSACTIONS_NOT_TARGET | RAM-BOOTSTRAP-VALIDATION-P15.json |
| engineering_package_structure_hashes_and_modes | PASS | RUNTIME-TREES-AND-BUILDS-P40.json |
| preexisting_r0012_preservation | PASS_502_FILES_WITH_THREE_EXPLICIT_ROUTING_LOG_EXCEPTIONS | R0012-PRESERVATION-P43.json |
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
| coordinated_service_start_and_boot_rollback | LIVE_ENTRY_IMPLEMENTED_ROLLBACK_PENDING_BOOT_NOT_IMPLEMENTED | SOURCE-INPUTS-P41.json |
| scoped_s24_and_private_ram_publication | PASS_BOUNDED_P39_CURRENT_ENTRY_EXTENSION_PENDING | ACTUAL-DAEMON-VALIDATION-P39.json |
| legacy_runtime_tree_ram_handoff_and_byte_rollback | PASS_BOUNDED_REAL_CROSS_FILESYSTEM_DASH_BUSYBOX | RUNTIME-TREES-AND-BUILDS-P40.json |
| actual_lighttpd_nginx_pid_and_stop_contract | PASS_BOUNDED_REAL_LINUX_DAEMONS | ACTUAL-DAEMON-VALIDATION-P39.json |
