# BROray-Light 2.0.0 — R0013, checkpoint P23

Публичная версия и версия пакета: `2.0.0`; будущий тег: `v2.0.0`.
Пользователь согласовал отдельные служебные `releaseId/candidateId=2.0.0-r1` для совместимости со старым обновителем.
**Кандидат пока не готов, выпуск не опубликован: candidateReady=false, releaseReady=false.**

## Результат P17–P23

Общий механизм RAM-папок и блокировок проверен на настоящей tmpfs с живыми процессами: 38 проверок под dash и BusyBox. Внешний updater перенесён в отдельный явный R0013 overlay: операционный статус, блокировки, загрузки, распаковка и ready-файл S23 находятся в защищённой RAM; журнал транзакции и установленные слоты остаются постоянными.

Проверены 32 сценария обновителя и S23 под двумя shell, включая native BusyBox applets, настоящие тестовые подписи minisign, равную версию, отказ от понижения, опасные архивы, health rollback, аварийное прерывание и восстановление. Слоты используют канонический формат сборщика r1; приложение и service/health boundary в этих тестах — подставные. Ошибки P18/P19/P21 сохранены отдельно и исправлены в новых ревизиях. Источник различия вывода hardlink в BusyBox: [header_verbose_list.c](https://raw.githubusercontent.com/mirror/busybox/1_36_stable/archival/libarchive/header_verbose_list.c).

В [CI P23](https://github.com/BROadmin/BROray-Light/actions/runs/34518444806) все текущие проверки прошли. Новая платформа `5-light2-ram` включена в IPK, её файлы совпадают с отдельным архивом. Публичный ключ и бинарник minisign сохранены побайтно из r1.

Предварительные `p23-engineering-build-A` и `p23-engineering-build-B` совпали по всем восьми файлам. SHA-256 и точные границы проверок: `UPDATER-PLATFORM-AND-BUILDS-P23.json`. Это не финальные clean-checkout Build A/B и не готовый кандидат.

Миграция действующей установки r1 ещё не завершена: app-slot не заменяет внешнюю платформу автоматически; старые lock/work и startup semantics требуют согласованного перехода и отката. Приложение в этих сборках ещё использует прежние runtime/log/tmp-пути. Роутер, production server и публичные релизы не изменялись.

## Выполнено ранее

База — проверенный Light r1, commit `9e5fce9bfa7c82bfc2f2654d80fd3987c5259963`, плюс отдельный явный R0013 overlay. Канонический R0008 проверен сборщиком. Незавершённый код R0012 не включён в сборку: 502 ранее существовавших файла кода/истории совпали по SHA-256; исключения — служебные AGENTS, WORKLOG и статус перенаправления R0012 на R0013, перечисленные в `R0012-PRESERVATION-P16.json`.

Из точного опубликованного BROray 3.1.0-r09c02 перенесены распознавание собственного процесса Xray, обработка start/stop, синхронизация имени активного сервера, выбор версий Xray и явные подтверждения риска. Сохранены три страницы, VLESS, native auth и Light ownership. Каталог совместимости полного BROray не считается приёмкой Light.

Старый опубликованный updater прошёл сравнения r1 → 2.0.0-r1, равной версии и понижения. Это проверка решения, не полный update-тест. API и WebUI показывают публичную версию 2.0.0 отдельно от служебного номера.

Для чистой установки проверены архив, официальный digest и бинарник Xray 26.9.9 (ELF64 AArch64, 35061884 байта). Обновление приложения сохраняет установленный Xray.

Установщик и bootstrap вынесены в защищённые RAM-каталоги: проверяются владелец, права, тип ФС, маркер и SHA-256; временные входы очищаются. В пакет не включены заголовки каталогов /tmp, которые могли бы изменить их права. В установщике явно задан `opkg --tmp-dir`, поддерживаемый [opkg](https://openwrt.org/docs/guide-user/additional-software/opkg).

Linux CI на commit `7ef2834233d8e8ecce9db2bb3fa639a9fb231a94` завершился успешно: [run 34509101953](https://github.com/BROadmin/BROray-Light/actions/runs/34509101953). Проверены BusyBox ash, настоящие Linux-процессы, файловые транзакции подписок, политика выбора Xray, поведение UI на подставных DOM/HTTP, версия через shell/jq и 11 сценариев bootstrap/installer. В последних подставлены тип ФС, opkg, бинарник Xray и запуск сервиса — это не физическая приёмка.

## Предыдущие предварительные Build A/B (P15, исторические)

`dist/R0013/p15-engineering-build-A` и `dist/R0013/p15-engineering-build-B` созданы отдельными процессами со свежими временными каталогами. Все 8 файлов совпали побайтно. Финальная независимая сборка из чистых checkout и подпись ещё не выполнены.

| Артефакт | Байт | SHA-256 |
| --- | ---: | --- |
| ENGINEERING-MANIFEST.json | 2343 | `01c85a64b9459653cf00dbbd77c047f27d0e91a8f187b64b5b32bcf3ab2052ef` |
| INPUT-MANIFEST.json | 31755 | `b861c52dcb500f223bfea00f31a7b8ced5799d084c06990b6bdd8fb4690db62b` |
| SHA256SUMS | 666 | `25e23d40bda23cc2b488c97bf99b8fe24f47d198c174e798cafa09b2b7178f2a` |
| broray-light-app-2.0.0-r1.tar.gz | 163974 | `4dcb15246111d242099463a315009126ba3e69fa9781d0b3b476144d32c9d095` |
| broray-light-install-2.0.0.sh | 3860 | `fc1800b889f37a026a29a9e230c76f0afdcbb6287da36f99c465fad5ab4a44ea` |
| broray-light-updater-platform-5-light1.tar.gz | 131458 | `81b7b70bd8180d0293be1e0de116c34801646234daf811b447ac82b0b676051c` |
| broray-light_2.0.0_aarch64-3.10.ipk | 12917824 | `76d31e27e7a2449e9fe9ecd05937f2e882b2180495568fdf341e97dadbd29fdf` |
| release.json | 597 | `f7328899c85b3077886e561e5ea752454721bf39459e2cdd38c4d968811077bc` |

## Блокер P16

Полная проверка RAM обнаружила действующий путь операционной блокировки `/opt/var/lock/broray-light`. Внешний updater r1 также использует старые блокировки. App-slot обновление само по себе не заменяет внешние init/updater-файлы. Простая смена пути лишь у приложения создаст две независимые блокировки и допустит конфликтующие операции.

Также остаются run/log/tmp приложения, сессии WebUI и рабочие файлы/блокировка Xray. Чистый bootstrap исправлен, но общий RAM-контракт пока не выполнен. Отказ сохранён в `process-failures/FAILURE-P16-PERSISTENT-LOCK-DOMAIN.json`. Установка на роутер и публикация не выполнялись.

Точный следующий этап: `P24_IMPLEMENT_MANIFEST_BOUND_R1_LIFECYCLE_TRANSITION_WITH_LEGACY_LOCK_FENCE_RAM_RUNTIME_PATHS_AND_EXTERNAL_PLATFORM_ROLLBACK`. Уже проверенные RAM-примитив и updater P23 подключаются к переходу с r1; это ещё не завершённый переход. Затем полные clean/update/equal/downgrade/rollback/persistence, все кнопки/API и native auth, финальные Build A/B/подпись, браузерная и разрешённая целевая приёмка.

## Каждый acceptance gate

Обозначение PASS с уточнением не заменяет финальную приёмку указанной подсистемы.

| Gate | Состояние | Доказательство |
| --- | --- | --- |
| pinned_donor_archives | PASS | UPSTREAM-DELTA-P2.json |
| complete_upstream_change_map | PASS_AUDIT_ONLY | UPSTREAM-PORT-MAP-P2.json |
| scoped_xray_identity | PASS_ISOLATED_LINUX | RAM-BOOTSTRAP-VALIDATION-P15.json |
| busybox_ash_overlay_syntax | PASS | RAM-BOOTSTRAP-VALIDATION-P15.json |
| active_subscription_rename_and_rollback | PASS_ISOLATED_ROUTER_BOUNDARY_MOCKED | SUBSCRIPTION-NAME-P6.json |
| xray_catalog_and_explicit_consent | PASS_POLICY_OFFICIAL_NETWORK_MOCKED | RAM-BOOTSTRAP-VALIDATION-P15.json |
| home_xray_controls | PASS_DOM_HTTP_BOUNDARIES_MOCKED | RAM-BOOTSTRAP-VALIDATION-P15.json |
| published_r1_to_2_0_0_admission | PASS_COMPARATOR_ONLY | UPGRADE-AND-XRAY-P10.json |
| canonical_source_and_final_input_manifest | PASS_ENGINEERING_INPUTS_FINAL_PENDING | RAM-BOOTSTRAP-VALIDATION-P15.json |
| xray_clean_binary_verification | PASS_ARCHIVE_DIGEST_BINARY_ELF | UPGRADE-AND-XRAY-P10.json |
| all_webui_buttons_and_apis | NOT_RUN_FULL_CANDIDATE | — |
| native_authentication_and_sessions | NOT_RUN_FULL_CANDIDATE | — |
| protected_tmpfs_all_operational_scratch | FAIL_CLOSED | process-failures/FAILURE-P16-PERSISTENT-LOCK-DOMAIN.json |
| archive_updater_and_ownership_safety | NOT_RUN_FULL_CANDIDATE | — |
| isolated_clean_install | NOT_RUN | — |
| isolated_update_from_r1 | BLOCKED_COORDINATED_RAM_LIFECYCLE_MIGRATION | process-failures/FAILURE-P16-PERSISTENT-LOCK-DOMAIN.json |
| isolated_equal_version | NOT_RUN | — |
| isolated_downgrade_refusal | NOT_RUN | — |
| forced_health_rollback | NOT_RUN_FULL_CANDIDATE | — |
| persistence | NOT_RUN_FULL_CANDIDATE | — |
| independent_build_a | PASS_PRELIMINARY_LOCAL_NOT_FINAL_ACCEPTANCE | RAM-BOOTSTRAP-VALIDATION-P15.json |
| independent_build_b | PASS_PRELIMINARY_LOCAL_NOT_FINAL_ACCEPTANCE | RAM-BOOTSTRAP-VALIDATION-P15.json |
| a_b_byte_reproducibility | PASS_PRELIMINARY_LOCAL_NOT_FINAL_ACCEPTANCE | RAM-BOOTSTRAP-VALIDATION-P15.json |
| existing_trust_root_signing | NOT_RUN | — |
| browser_desktop_mobile_layout | NOT_RUN | — |
| authorized_router_validation | NOT_RUN | — |
| immutable_release_and_public_byte_validation | NOT_PUBLISHED | — |
| public_version_vs_internal_updater_identity | PASS_SHELL_JQ_AND_MOCK_DOM_HTTP | RAM-BOOTSTRAP-VALIDATION-P15.json |
| clean_bootstrap_and_installer_protected_ram | PASS_BOUNDED_UNIT_TRANSACTIONS_NOT_TARGET | RAM-BOOTSTRAP-VALIDATION-P15.json |
| engineering_package_structure_hashes_and_modes | PASS | RAM-BOOTSTRAP-VALIDATION-P15.json |
| preexisting_r0012_preservation | PASS_502_FILES_WITH_THREE_EXPLICIT_ROUTING_LOG_EXCEPTIONS | R0012-PRESERVATION-P16.json |

Контрольная точка: `checkpoints/R0013/CHECKPOINT.json`; machine-readable gates: `VALIDATION.json`; SHA-256 всех записей: `SHA256SUMS`.
