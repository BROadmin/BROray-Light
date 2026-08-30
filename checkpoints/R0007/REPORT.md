# BROray-Light — повторная подготовка по актуальному Stable r23

## Итог

`R23_PREPARATION_STATUS=PASS`

Подготовка выполнена заново от текущего Stable BROray `3.0.0-r23`, технический кандидат `3.0.0-r23c02`. Предыдущий r20 checkpoint сохранён как история, но больше не является текущей базой Light.

## Exact Stable

- `release.json`: `2b376932d7e7d7a773e1454012a512d382014890f514e3181843fa24689e11f1` — PASS.
- application: `69679f6d7339b856faf28f69cb1800254984e5400201fe97247011ab166c3f85` — PASS.
- updater platform: `eaf2eafb62d1b108fe576d1fda09ae7a5d15ad90f71272abc23f321d397611b0` — PASS and byte-identical to r20.
- clean bootstrap: `fb4943e3d336d091b16e6cf436e2a7eefe7274422246c8038a7eea2e6c0d79a0` — PASS and byte-identical to r20.
- installer: `12f9d9edace123c1137d6143210af7c1e7157109859efbc0e75c02fdc53cec21` — PASS.
- GitHub Actions exact donor run: `33334405978`.
- exact donor artifact: `9738580535`, digest `sha256:7d44da3e09e4207235d3daa0f25e822da651274a6020702f8c7d106a85da2fe2`.

## Exact application validation

- 287 regular files, 40 directories, 5,167,612 logical bytes;
- unsafe archive paths: 0;
- internal SHA256SUMS: 286/286 PASS;
- BusyBox ash bin/init: 26/26 PASS;
- BusyBox ash libraries (excluding intentionally dropped legacy package-transaction): 64/64 PASS;
- Web API ash: 82/82 PASS;
- JavaScript: 25/25 PASS;
- JSON: 33/33 PASS;
- preparation validator: 32/32 PASS.

## Что изменилось относительно r20

Exact file delta: 3 files added, 0 removed, 16 changed, 268 common files remain byte-identical.

All three new files belong to the new scheduled server quality-refresh subsystem:

- `app/web-new/api/servers/quality-refresh-save.cgi`;
- `app/web-new/api/servers/quality-refresh-status.cgi`;
- `app/web-new/assets/js/servers-quality-refresh.js`.

They are `DROP` for BROray-Light. The approved Light concept keeps automatic failover but not a separate periodic quality-measurement scheduler, ratings, ping/jitter ranking or quality history.

`app/lib/interface-owner.sh` changed in r23 and is `ADAPT/MUST_PRESERVE`: the new zero-or-one `proxy connect via` binding validation fixes managed-interface ownership detection and must be preserved in Light.

`app/bin/broray-server-auto-switch` is still `REPLACE`: r23 makes the full daemon more coupled by adding `qualityRefresh` state and scheduled checks. Light retains threshold/cooldown, config validation, post-activation connectivity check, rollback and global serialization, but selection is deterministic persisted order.

## Новая treatment map

| Treatment | Files | Donor bytes |
| --- | ---: | ---: |
| DROP | 156 | 3,883,525 |
| REPLACE | 48 | 602,718 |
| ADAPT | 65 | 572,709 |
| PORT | 11 | 39,641 |
| RETAIN | 7 | 69,019 |

`DROP` removes 75.15% of the r23 application logical bytes before further shrinking of ADAPT/REPLACE files. This is not a final compressed package-size estimate.

## Architecture decision

The approved BROray-Light concept does not change:

- VLESS only;
- Home, Servers, Subscriptions only;
- automatic failover retained;
- deterministic order, no rating/history/best-quality/lowest-ping/preferred modes;
- no scheduled quality-refresh subsystem;
- Keenetic status/configure/repair/refresh on Home;
- one brand theme;
- one primary application-control service `S24broray-light`;
- updater-v5 semantics forked to Light identity/paths/topology;
- no WebUI remove/restore/backup/manual-Xray maintenance.

```text
BASE_STABLE=3.0.0-r23
BASE_CANDIDATE=3.0.0-r23c02
EXACT_DONOR=PASS
FILE_CLASSIFICATION=287/287
UNCLASSIFIED=0
DROP_LOGICAL_BYTES=3883525
DROP_PERCENT=75.15
CURRENT_MAIN_AS_DONOR=FORBIDDEN
FULL_BROray_MUTATION=NONE
ROUTER_MUTATION=NONE
PRODUCTION_SERVER_MUTATION=NONE
NEXT_STAGE=BUILD_LIGHT_SOURCE_TREE_FROM_R23_TREATMENT_MAP
```
