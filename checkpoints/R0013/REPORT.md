# R0013 — замена тестового роутера на BROray-Light 2.0.0

Полная замена на **192.168.1.1 выполнена**. Это PASS установки и базовой проверки, **не приёмка релизного кандидата**. `candidateReady=false`, `releaseReady=false`; 2.0.0 не опубликован.

## Фактическое состояние

- Полный BROray удалён штатным worker после проверенной резервной копии на компьютере.
- Старые S99 bootstrap и завершённый handoff удалены отдельно: только 12 файлов с проверенными SHA-256 и 4 пустых каталога.
- Light 2.0.0 установлен настоящим opkg; внутренний releaseId `2.0.0-r1`.
- Установленный source commit: `14813c3774207502039999e014062464043827d1`.
- Xray 26.9.9: `c1defe42b6db958a97c5e049a02a00a4baaedaca7b51c1c229f0830e288acef5`.
- S23/S24 работают; весь app manifest проверен. SHA-256 APP-SHA256SUMS: `57832490c248a75d0286f142c8553e4b5e7a377336b10f648ee2e2dffb206716`.
- Native-вход через KeeneticOS работает. Без сессии API возвращает 401 локально и снаружи; GET login — 405. Защита входа не ослаблялась.
- Главная, Серверы и Подписки открываются и завершают загрузку.
- Это чистая установка: каталоги серверов/подписок пусты, сервер не выбран, Xray намеренно остановлен. Полная схема конфигурации BROray автоматически не переносилась.
- Операционные каталоги используют защищённый tmpfs. 18 временных файлов этой операции и 3 пустых каталога удалены; приватные резервные копии на компьютере сохранены.
- После очистки: свободно 71 904 KiB в /opt и 246 712 KiB в /tmp. Логический объём Light с Xray на P80 — 35 508 KiB плюс 264 KiB внешнего updater/publication.
- 502 прежних файла R0012 проверены: несовпадений нет.

Адрес: [WebUI](https://brolight.tvervip.keenetic.link/home.html?v=2.0.0).

## Зафиксированная ошибка и исправление

P81: HTTP 500 при входе — runtime guard выполнялся до настройки PATH и не находил Entware stat. Ошибка отдельно сохранена в [FAILURE-P81-NATIVE-TARGET-LOGIN.json](process-failures/FAILURE-P81-NATIVE-TARGET-LOGIN.json); повтор на той же ревизии не выполнялся.

P83 устанавливает путь Entware до guard, не меняя native-auth, сессии или ownership-проверки. Пустой и подменённый PATH включены в регрессию: 100 CGI/session тестов PASS. P84 заменяет пакет штатно, сохраняя точные durable-хеши; P85 подтверждает настоящий вход. Не было unmanifested hotpatch, force-флагов opkg или обхода co-install-защиты.

## Сборки и артефакты

[Build A/B](https://github.com/BROadmin/BROray-Light/actions/runs/34575296123): независимые Ubuntu runners, **8/8 файлов побайтно одинаковы**. Чистая установка — 4 + 4 теста PASS; bootstrap/stat — 15 PASS. [Полная регрессия](https://github.com/BROadmin/BROray-Light/actions/runs/34575296136) требует отдельной финальной фиксации всех результатов; на момент P87 native-auth и prepared-app PASS, live-entry ещё не завершён.

| Артефакт | Байт | SHA-256 |
|---|---:|---|
| broray-light-app-2.0.0-r1.tar.gz | 229584 | `c6fc51632127b1afc58ab8bdf23020122861b99b1eaa510c035ad8a26ffec66b` |
| broray-light-install-2.0.0.sh | 4108 | `f8775988803ed70fd1eed455a6444e567ebad8109a252c430a7071f4aefda0c2` |
| broray-light-updater-platform-5-light2-ram.tar.gz | 136061 | `aa814efcb6d75f02c061b3928588439466e9ee02af127bd7eac376786410fc1b` |
| broray-light_2.0.0_aarch64-3.10.ipk | 12991917 | `a31449263dfc5b772854fcd3f4d8624c334e3038715c61ae9996fd4fcd6adb79` |
| ENGINEERING-MANIFEST.json | 2347 | `c48ef13db0d25c86ca9094a2974b4045c55a86c4d9c061d7f9cd24f44d2f23ac` |
| INPUT-MANIFEST.json | 40796 | `46e528de85ccebe6a1fb1cfb33ff31b007c979bf4dc1c46aba5dfab90176de3e` |
| release.json | 597 | `4dab50872ef07f307dcc2a37cc0bb9779e118a879fd351abc5e69df64f35ca2b` |
| SHA256SUMS | 670 | `db5d22b42eac246274f224ea258f2b9856138db8d3b13708f442e30a9088a9ad` |

Точные receipts: [INDEPENDENT-BUILDS-P83.json](INDEPENDENT-BUILDS-P83.json), [TARGET-REPLACEMENT-P87.json](TARGET-REPLACEMENT-P87.json).

## Резервные копии

Приватный игнорируемый каталог: `dist/R0013/private-target/p74`. Архивы содержат пользовательские секреты, в Git не добавлены.

| Архив | SHA-256 |
|---|---|
| backup-bundle.tar — полный BROray и running-config | `bd340ffe2a6e781434f33dba528cfde0be7eb1341f9d4126beb88b7c4088cda4` |
| supplement-preserved-bootstrap.tar | `276aa1ca87c51ff750bbfe4eccc5cbedaeb39e5119f4a466ff608fb6872eb401` |
| light-p72-before-p84.tar.gz | `5f9cf04217face11d6207d9b5839fd40afec24e1c1935f82dc8de593f224ec2e` |

## Acceptance gates

Здесь сохранены границы ранее выполненных компонентных проверок; PASS изолированного теста не означает PASS всего нового кандидата.

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
| xray_clean_binary_verification | PASS_PINNED_BINARY_ACTUAL_ARM64_TARGET | TARGET-STATE-P80.json |
| all_webui_buttons_and_apis | PARTIAL_ALL_FRONTEND_CONTROLS_PASS_FULL_BACKEND_FUNCTIONAL_PENDING | BROWSER-CONTROLS-P66.json |
| native_authentication_and_sessions | PASS_100_CGI_TESTS_AND_PHYSICAL_NATIVE_LOGIN | TARGET-NATIVE-LOGIN-P85.json |
| protected_tmpfs_all_operational_scratch | PASS_INSTALL_RUNTIME_LINKS_AND_INVOCATION_CLEANUP_TARGET | TARGET-CLEANUP-P86.json |
| archive_updater_and_ownership_safety | PASS_ISOLATED_COMPONENTS_FINAL_SIGNED_TARGET_PENDING | REGRESSION-P64.json |
| isolated_clean_install | PASS_P83_BUILD_EXACT_CLEAN_PACKAGE_FIXTURE | INDEPENDENT-BUILDS-P83.json |
| isolated_update_from_r1 | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| isolated_equal_version | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| isolated_downgrade_refusal | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| forced_health_rollback | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| persistence | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| independent_build_a | PASS_INDEPENDENT_LINUX_UNSIGNED_BYTES | INDEPENDENT-BUILDS-AND-CLEAN-P63.json |
| independent_build_b | PASS_INDEPENDENT_LINUX_UNSIGNED_BYTES | INDEPENDENT-BUILDS-AND-CLEAN-P63.json |
| a_b_byte_reproducibility | PASS_P83_8_OF_8 | INDEPENDENT-BUILDS-P83.json |
| existing_trust_root_signing | NOT_RUN | null |
| browser_desktop_mobile_layout | PASS_CHROMIUM_FIXTURE_390_768_1440_NINE_IMAGES_REVIEWED | BROWSER-CONTROLS-P66.json |
| authorized_router_validation | BLOCKED_FULL_BROray_OWNERSHIP_AND_STAT_CAPABILITY | process-failures/FAILURE-P69-TARGET-FULL-BRORAY-OWNERSHIP.json |
| immutable_release_and_public_byte_validation | NOT_PUBLISHED | null |
| public_version_vs_internal_updater_identity | PASS_SHELL_JQ_AND_MOCK_DOM_HTTP | RAM-BOOTSTRAP-VALIDATION-P15.json |
| clean_bootstrap_and_installer_protected_ram | PASS_BUILT_PACKAGE_REAL_SERVICES_HTTP_QEMU_OS_ADAPTERS | INDEPENDENT-BUILDS-AND-CLEAN-P63.json |
| engineering_package_structure_hashes_and_modes | PASS_P83_BUILT_ARTIFACTS_AND_TARGET_MANIFEST | INDEPENDENT-BUILDS-P83.json |
| preexisting_r0012_preservation | PASS_502_FILES_UNCHANGED | TARGET-REPLACEMENT-P87.json |
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
| scoped_s24_and_private_ram_publication | PASS_ACTUAL_TARGET_S23_S24_PUBLICATION | TARGET-CORRECTED-INSTALL-P84.json |
| legacy_runtime_tree_ram_handoff_and_byte_rollback | PASS_BOUNDED_REAL_CROSS_FILESYSTEM_DASH_BUSYBOX | RUNTIME-TREES-AND-BUILDS-P40.json |
| actual_lighttpd_nginx_pid_and_stop_contract | PASS_BOUNDED_REAL_LINUX_DAEMONS | ACTUAL-DAEMON-VALIDATION-P39.json |
| new_updater_complete_prepared_app_service_transition | PASS_FULL_PREPARED_APP_DASH_BUSYBOX_OS_BOUNDARIES_MOCKED | PREPARED-LIFECYCLE-P64.json |
| target_stat_prerequisite | PASS_ACTUAL_TARGET_COREUTILS_STAT | TARGET-STAT-P75.json |

## Следующий этап

`R0013_P88_FUNCTIONAL_VLESS_AND_ALL_WEBUI_BACKEND_ACCEPTANCE_ON_REPLACED_TEST_TARGET`

Проверить окончание регрессии P83 и сохранить результаты. Затем выполнить функциональную приёмку VLESS и всех кнопок/backend, physical restart/persistence и signed updater. После этого — подпись существующим encrypted Actions secret, финальные immutable release/documentation gates. До выполнения этих требований готовность кандидата и релиза остаётся false.

Основной checkpoint: [CHECKPOINT.json](CHECKPOINT.json). История ошибок сохранена; исходный R0008, прежние релизы, production server и репозиторий полного BROray не изменялись.
