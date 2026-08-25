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

Xray and lighttpd remain separate runtime processes where required by the platform; “one service” means one BROray-Light application-control service.

## Upstream baseline

The donor baseline is BROray Stable `3.0.0-r14`, technical candidate `3.0.0-r14c68`, published 2026-08-25.

The current `BROadmin/BROray` `main` branch is **not** treated as byte-exact Stable source. Source import into this repository is blocked until the exact `r14c68` release-source bytes are obtained and their identity is verified.

See `docs/UPSTREAM-STABLE-PIN.md`.

## Status

```text
REPOSITORY_BOOTSTRAP=PASS
REMOTE_REPOSITORY=NOT_CREATED
STABLE_SOURCE_IMPORT=BLOCKED_PENDING_EXACT_R14C68_SOURCE_BYTES
PRODUCTION_MUTATION=NONE
```
