# Upstream Stable pin — BROray-Light

BROray-Light preparation is pinned to exact BROray Stable `3.0.0-r23` / `3.0.0-r23c02` bytes verified on 2026-08-30. Current upstream `main` is context only and is not accepted as a byte-exact donor.

| Field | Value |
| --- | --- |
| Stable releaseId | `3.0.0-r23` |
| Technical candidate | `3.0.0-r23c02` |
| OPKG package version | `3.0.0-r14` |
| WebUI build | `WebUI-3.0.0-r23c02` |
| Stable release.json SHA-256 | `2b376932d7e7d7a773e1454012a512d382014890f514e3181843fa24689e11f1` |
| Application SHA-256 | `69679f6d7339b856faf28f69cb1800254984e5400201fe97247011ab166c3f85` |
| Updater platform SHA-256 | `eaf2eafb62d1b108fe576d1fda09ae7a5d15ad90f71272abc23f321d397611b0` |
| Clean bootstrap SHA-256 | `fb4943e3d336d091b16e6cf436e2a7eefe7274422246c8038a7eea2e6c0d79a0` |
| Installer SHA-256 | `12f9d9edace123c1137d6143210af7c1e7157109859efbc0e75c02fdc53cec21` |
| Updater engine | `broray-updater/5` (`a3c094b3...e2c4a`) |

Exact donor retrieval: GitHub Actions run `33334405978`, artifact `9738580535`, digest `sha256:7d44da3e09e4207235d3daa0f25e822da651274a6020702f8c7d106a85da2fe2`.

Application: 287 regular files, 40 directories, 5,167,612 logical bytes, unsafe archive paths 0. Internal SHA256SUMS: 286/286 PASS.

`r23c02` adds scheduled quality-refresh to full BROray, but that subsystem is outside approved Light scope. The r23 Keenetic interface ownership fix is included in the adaptation baseline.

```text
CURRENT_MAIN_AS_DONOR=FORBIDDEN
EXACT_R23C02_RUNTIME_DONOR=VERIFIED
UPDATER_PLATFORM_DONOR=VERIFIED
CLEAN_BOOTSTRAP_DONOR=VERIFIED
```
