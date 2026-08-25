# Upstream Stable pin

BROray-Light must be derived from the exact released BROray Stable bytes, not from an assumed-equivalent development tree.

## Stable identity

| Field | Value |
| --- | --- |
| Public release | `3.0.0` |
| OPKG release | `3.0.0-r14` |
| Technical candidate | `3.0.0-r14c68` |
| Stable publication date | `2026-08-25` |
| Stable `release.json` SHA-256 | `0740557b08c90fe07d51afd3d99d1c6947fdd082cca0c191369af03116995a4c` |
| Stable COPY-PASTE installer SHA-256 | `06a0f631269f175bc02469856733020a713f1eaed13ac047abd111519cf92967` |
| Candidate carrier SHA-256 | `8ccb49508292b8d2b04c76ea06189b07471aeeb4ffba0255b3fbc4f69d882f39` |
| Application archive SHA-256 | `314be910e180d5bbac4677a9483e17f18406c8a4339a849edb2c1c8d7de4e382` |
| Updater platform archive SHA-256 | `40b71cf3a5be9697d19989bac4baee6023692b7cced32ba8b888e4331ae5272f` |
| Xray 26.7.28 SHA-256 | `4b8af237444801bf17b3dc10a1c5c24581fbe3d433eba3d78c6c3a0da1df56fc` |

## Source-import rule

`BROadmin/BROray` documentation states that the current `main` tree is not automatically a byte-exact copy of the published Stable archives. Therefore:

```text
CURRENT_MAIN_AS_DONOR=FORBIDDEN
EXACT_R14C68_RELEASE_SOURCE_REQUIRED=YES
```

No BROray application source is copied into this repository until the exact release-source overlay/archive corresponding to `r14c68` is available and verified.
