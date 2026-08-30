# BROray-Light

BROray-Light is a minimal VLESS-focused edition of BROray for Keenetic/KeeneticOS.

## Product scope

BROray-Light intentionally keeps only three WebUI pages:

1. **Home** — active server, automatic failover status/control, Keenetic proxy-interface control, Xray version/update, BROray-Light version/update.
2. **Servers** — VLESS servers, check, activate, delete, ordering and inclusion in automatic failover.
3. **Subscriptions** — add/update/delete subscriptions and import only VLESS servers.

The product keeps automatic server switching, but does not keep ratings, latency history or quality-history graphs.

## Explicitly excluded

- protocols other than VLESS;
- routes and BAT import;
- DNS-over-TLS management;
- separate Keenetic, Xray and BROray system pages;
- complex server-parameter editor;
- manual Xray start/stop/maintenance UI;
- backup/restore/remove operations from WebUI;
- multiple UI themes.

## Architecture direction

BROray-Light is a separate product and repository. It reuses only verified mechanisms from BROray Stable and removes unrelated modules physically rather than merely hiding them in the UI.

Target runtime namespace:

```text
/opt/broray-light/
```

Target primary application service:

```text
S24broray-light
```

Xray and lighttpd remain separate runtime processes where required by the platform; “one service” means one BROray-Light application-control service. The updater remains a separate control-plane component derived from updater-v5 semantics.

## Upstream baseline

The current donor baseline is BROray Stable `3.0.0-r20`, technical candidate `3.0.0-r20c01`, published 2026-08-30.

The exact Stable application, updater platform, clean bootstrap and installer were fetched from the signed/current Stable index and verified by recorded SHA-256 values. The current `BROadmin/BROray` `main` branch remains development/documentation context and is **not** treated as byte-exact Stable source.

See `docs/UPSTREAM-STABLE-PIN.md` and `checkpoints/R0006/REPORT.md`.

## Preparation status

```text
R20_PREPARATION_STATUS=PASS
EXACT_STABLE_DONOR=PASS
DONOR_FILES_CLASSIFIED=284/284
UNCLASSIFIED=0
IMMEDIATE_DROP_LOGICAL_BYTES=3866549
IMMEDIATE_DROP_PERCENT=75.32
NEXT_STAGE=BUILD_LIGHT_SOURCE_TREE_FROM_R20_TREATMENT_MAP
PRODUCTION_MUTATION=NONE
```
