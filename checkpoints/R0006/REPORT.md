# BROray-Light — повторная подготовка по актуальному Stable r20

## Итог

`R20_PREPARATION_STATUS=PASS`

Подготовка выполнена заново от текущего Stable BROray `3.0.0-r20`, технический кандидат `3.0.0-r20c01`. Старый pin `r14c68` больше не используется как база Light. Exact runtime donor, updater platform, clean bootstrap и installer получены из текущего Stable index и подтверждены SHA-256.

## Что именно проверено

- Stable `release.json`: `b87deb3cca0eb01b1632aa8ceb1bcb81de6972bee5b7925e694088cffa9a2ebd` — PASS.
- application: `ad231c899e0a93f90f65489b8b6588aa09ae94b43c1d838e13e4458079c862bd` — PASS.
- updater platform: `eaf2eafb62d1b108fe576d1fda09ae7a5d15ad90f71272abc23f321d397611b0` — PASS.
- clean bootstrap: `fb4943e3d336d091b16e6cf436e2a7eefe7274422246c8038a7eea2e6c0d79a0` — PASS; формат ASCII text, не архив.
- installer: `3c3faa352ef78821de791a3e932602b88efadf9b82fecde39c535a67bfbb14c0` — PASS.
- application internal SHA256SUMS: 283/283 entries PASS.
- BusyBox ash syntax: bin/init 26/26 PASS; libraries except intentionally dropped legacy package-transaction 64/64 PASS; Web API 80/80 PASS.
- JavaScript syntax: 24/24 PASS.
- JSON syntax: 33/33 PASS.

Два собственных read-only validation timeout сохранены как отдельные process-failure records; они не меняли donor, GitHub upstream, сервер или роутер. После них проверки были разбиты на короткие пакеты и завершены PASS.

## Результат усечения

Exact r20 application содержит `5,133,493` логических байта. File-treatment registry классифицирует все 284 файла без `UNCLASSIFIED`:

| Treatment | Files | Donor bytes |
| --- | ---: | ---: |
| DROP | 153 | 3,866,549 |
| REPLACE | 48 | 587,725 |
| ADAPT | 65 | 570,559 |
| PORT | 11 | 39,641 |
| RETAIN | 7 | 69,019 |

`DROP` alone removes `3,866,549` logical bytes, or `75.32%` of the full r20 application tree. This is a conservative lower bound: ADAPT/REPLACE modules are intentionally expected to shrink further. An exact compressed Light size is not claimed until the first reproducible Light build exists.

## Главные архитектурные выводы

1. **Автопереключатель нельзя копировать как есть.** Он связан с ratings, ping/jitter ranking, preferred/best-quality modes and resumable routes. Light gets deterministic ordered failover with the safety part retained.
2. **Server core must be VLESS-only physically.** Exact donor has multi-protocol branches in import, validation and config generation; these are removed, not hidden.
3. **Current generic WebUI operation lock is hidden inside `routes-api-operation.sh`.** Light needs a renamed compact lock module retaining updater interlock and stale-owner safety but with zero route semantics.
4. **Updater-v5 cannot be copied byte-exact into Light.** It hardcodes `/opt/broray`, the `broray` package identity, full-app required files and five service names. The mature releaseId comparison, signature, app-slot, health and rollback model is retained in a Light fork.
5. **r20 Lighttpd/Keenetic ownership protections must survive.** Even without WebUI uninstall, Light must never overwrite or restore foreign state ambiguously.
6. **Subscription staging is a strong donor.** Its safe fetch/stage/dedup logic is retained, but Light reports non-VLESS entries as `skippedOtherProtocols`, not generic failures.
7. **Five full-app init scripts collapse to one primary Light service.** The separate subscription scheduler is removed. Updater remains a separate control plane, as approved by the concept.

## Target preparation state

The next implementation stage may start from this checkpoint. It must not copy full `main` or copy the complete r20 app and merely hide pages. It must construct a new Light tree from the treatment registry and target architecture, with new release/checksum identities.

```text
BASE_STABLE=3.0.0-r20
BASE_CANDIDATE=3.0.0-r20c01
EXACT_DONOR=PASS
FILE_CLASSIFICATION=284/284
UNCLASSIFIED=0
DROP_LOGICAL_BYTES=3866549
DROP_PERCENT=75.32
CURRENT_MAIN_AS_DONOR=FORBIDDEN
FULL_BROray_MUTATION=NONE
ROUTER_MUTATION=NONE
PRODUCTION_SERVER_MUTATION=NONE
NEXT_STAGE=BUILD_LIGHT_SOURCE_TREE_FROM_R20_TREATMENT_MAP
```
