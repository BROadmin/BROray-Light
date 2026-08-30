# Upstream Stable pin — BROray-Light

BROray-Light preparation is pinned to the exact current BROray Stable release bytes verified on 2026-08-30. Current upstream `main` remains documentation/development context only and is not accepted as a byte-exact donor.

## Stable identity

| Field | Value |
| --- | --- |
| Stable releaseId | `3.0.0-r20` |
| Technical candidate | `3.0.0-r20c01` |
| OPKG package version carried by Stable | `3.0.0-r14` |
| Stable publication date | `2026-08-30` |
| WebUI build | `WebUI-3.0.0-r20c01` |
| Stable `release.json` SHA-256 | `b87deb3cca0eb01b1632aa8ceb1bcb81de6972bee5b7925e694088cffa9a2ebd` |
| Application archive SHA-256 | `ad231c899e0a93f90f65489b8b6588aa09ae94b43c1d838e13e4458079c862bd` |
| Updater platform archive SHA-256 | `eaf2eafb62d1b108fe576d1fda09ae7a5d15ad90f71272abc23f321d397611b0` |
| Clean bootstrap SHA-256 | `fb4943e3d336d091b16e6cf436e2a7eefe7274422246c8038a7eea2e6c0d79a0` |
| `INSTALL-ON-ROUTER.sh` SHA-256 | `3c3faa352ef78821de791a3e932602b88efadf9b82fecde39c535a67bfbb14c0` |
| Updater engine | `broray-updater/5` |
| Updater engine SHA-256 | `a3c094b3a5e82ac82be7ec8b53c90f4023351a94eb6ba945b99501c0876e2c4a` |

## Exact donor retrieval

GitHub Actions run `33308452852` downloaded the objects by matching the SHA-256 values from the pinned Stable index and independently rechecked every object. The resulting artifact `broray-stable-r20c01-exact-donor-r2` has GitHub artifact digest `sha256:61c7618193926693014d8ef6b3717a114041bc89d9f17a3ae81184615a034571`.

The application archive contains 284 regular files and 40 directories, with 5,133,493 logical bytes and no unsafe archive paths.

```text
CURRENT_MAIN_AS_DONOR=FORBIDDEN
EXACT_R20C01_RUNTIME_DONOR=VERIFIED
UPDATER_PLATFORM_DONOR=VERIFIED
CLEAN_BOOTSTRAP_DONOR=VERIFIED_AS_ASCII_TEXT
```

The clean bootstrap is intentionally treated as an opaque hashed executable text object. It is not a gzip/tar archive.
