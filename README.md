# BROray-Light

BROray-Light is a minimal VLESS-focused edition of BROray for Keenetic/KeeneticOS.

## Product scope

BROray-Light intentionally keeps only three WebUI pages:

1. **Home** — active server, automatic failover status/control, Keenetic proxy-interface control, Xray version/update, BROray-Light version/update.
2. **Servers** — VLESS servers, check, activate, delete, ordering and inclusion in automatic failover.
3. **Subscriptions** — add/update/delete subscriptions and import only VLESS servers.

Automatic server switching is retained, but ratings, quality history, best-quality/lowest-ping selection and the full BROray scheduled quality-refresh subsystem are excluded.

## Architecture direction

BROray-Light is a separate product and repository. It reuses only verified mechanisms from exact BROray Stable bytes and physically removes unrelated modules rather than merely hiding them.

Target namespace: `/opt/broray-light/`. Target primary application service: `S24broray-light`.

## Upstream baseline

Current preparation baseline is BROray Stable `3.0.0-r23`, technical candidate `3.0.0-r23c02`, verified from exact release bytes on 2026-08-30. Current `BROadmin/BROray` `main` is not treated as the byte-exact donor.

See `docs/UPSTREAM-STABLE-PIN.md` and `checkpoints/R0007/REPORT.md`.

## Status

```text
REPOSITORY_BOOTSTRAP=PASS
R23_PREPARATION=PASS
EXACT_R23C02_DONOR=PASS
FILE_CLASSIFICATION=287/287
UNCLASSIFIED=0
NEXT_STAGE=BUILD_LIGHT_SOURCE_TREE_FROM_R23_TREATMENT_MAP
PRODUCTION_MUTATION=NONE
```
