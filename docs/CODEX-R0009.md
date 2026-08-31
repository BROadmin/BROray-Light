# Codex task — R0009

## Objective

Build the first installable BROray-Light internal candidate from canonical R0008 source without reopening product architecture.

Authorized stage:

`BUILD_LIGHT_UPDATER_INSTALLER_AND_INSTALLABLE_CANDIDATE_FROM_R0008`

Working branch:

`codex/r0009-updater-package`

## Immutable source input

Canonical source commit:

`684b27bdb53e545047419baa87c63dd86dffa469`

Canonical R0008 source identities:

- files: `121`
- logical bytes: `627326`
- `src/SHA256SUMS` SHA-256: `e056585d6a517ddbbbaebf08b68f17eb2d9d7ccd68d86df5cdee9fd4665f2419`
- R0008 source checkpoint SHA-256: `6686586ed777a7b0c37336d08143d388fdc301536b32c96eb35e8b20e5393953`

R0008 remote persistence is PASS. Its source bytes are immutable for R0009.

## Pinned full-BROray reference evidence

The Light source was derived from BROray Stable `3.0.0-r23`, technical candidate `3.0.0-r23c02`.

Relevant verified donor identities already recorded in the repository:

- Stable application SHA-256: `69679f6d7339b856faf28f69cb1800254984e5400201fe97247011ab166c3f85`
- updater platform SHA-256: `eaf2eafb62d1b108fe576d1fda09ae7a5d15ad90f71272abc23f321d397611b0`
- updater engine: `broray-updater/5`

Do not assume the current full BROray `main` is byte-equivalent to Stable.

## Deliverables

R0009 must produce an internal, not publicly published, installable candidate containing or securely bootstrapping:

1. exact R0008 application slot;
2. Light-specific updater control plane derived from updater-v5 semantics;
3. clean-install bootstrap/installer;
4. Light package metadata and lifecycle scripts;
5. exact Xray runtime acquisition/bootstrap contract for a clean router;
6. deterministic manifests and SHA-256 receipts;
7. Build A and Build B reproducibility evidence;
8. isolated-root install/update/rollback validation;
9. R0009 checkpoint and Codex handoff.

## Updater functional contract

Implement Light-specific paths/package/service topology while preserving mature updater-v5 safety semantics.

Required decisions:

- installed/current release is determined by Light `releaseId`, not OPKG revision history;
- older release may update to newer signed release;
- equal release must follow an explicit Light same-version policy and have tests;
- newer installed release must not be downgraded by ordinary Stable update;
- release index and downloadable objects require cryptographic/checksum validation;
- app-slot switch must be atomic;
- failed health gate must restore previous-good slot;
- request/global locking must prevent conflicting WebUI, updater, server activation, and failover operations;
- updater must not require full BROray route state or full five-service topology.

## Installable layout

Expected high-level runtime layout:

```text
/opt/broray-light/
  releases/<releaseId>/
  current -> releases/<releaseId>
  bin -> current/app/bin
  lib -> current/app/lib
  share -> current/app/share
  web-new -> current/app/web-new
  config/
  servers/
  subscriptions/
  runtime/xray
  backup/
  run/
  logs/

/opt/var/lib/broray-light/operations/
/opt/var/lib/broray-light-updater/
/opt/var/lock/broray-light/
/opt/var/lock/broray-light-updater/

/opt/etc/init.d/S24broray-light
```

The exact updater init/control filename is an R0009 implementation decision, but it must be Light-specific and recorded.

## Xray clean-install requirement

Canonical R0008 has a wrapper at the Light application path, not the actual Xray binary. Resolve the exact verified Xray runtime artifact from current pinned release evidence before packaging.

Required checks:

- architecture mapping is explicit;
- URL/source is authoritative and pinned;
- size and SHA-256 are verified before installation;
- executable mode is correct;
- runtime path is `/opt/broray-light/runtime/xray`;
- clean install fails closed if Xray cannot be verified or installed;
- existing verified Xray runtime is not unnecessarily replaced during application-only update.

Do not hardcode a checksum from memory.

## Isolated-root tests before hardware

No physical router is authorized during this stage. Use a disposable root filesystem/test harness.

Required scenarios:

- clean install into empty root;
- re-running installer safely;
- application update from older Light internal slot to newer test slot;
- equal-version update behavior;
- downgrade refusal;
- failed download/hash verification;
- malicious archive path rejection;
- lock contention/stale-owner handling;
- health check PASS switch;
- forced health check FAIL rollback;
- preservation of `config/`, `servers/`, `subscriptions/`, and `runtime/xray` across application slot replacement;
- removal/rollback behavior must not restore or delete foreign Lighttpd/Keenetic state without exact ownership proof.

## Reproducibility

Build A and Build B must start from clean independent build roots with the same canonical inputs.

Prefer byte-identical artifacts. If a container format inserts unavoidable nondeterminism, normalize/build deterministically or prove equivalence at the payload/member/mode/hash level and document why byte identity of the outer container is impossible.

Do not weaken reproducibility requirements merely to obtain PASS.

## Record format

Every substage must append a JSON object to `project/WORKLOG.jsonl` including:

- `at`
- `stage`
- `revision`
- `event`
- `status`
- input identities
- produced artifact identities
- first error/blocker if any
- exact next action

`project/R0009-STATE.json` is the current-state index and must never claim more than has actually passed.

Use `checkpoints/R0009/process-failures/*.json` for failed revisions.

## Stop conditions

Stop the current revision and record failure if any of these occur:

- canonical R0008 identity mismatch;
- updater-v5 donor identity mismatch;
- Xray artifact cannot be resolved or verified;
- non-VLESS protocol support is reintroduced;
- route/DNS/quality-history subsystem leaks back into runtime;
- native auth/session protection is weakened;
- full BROray co-ownership is silently adopted;
- Build A/B differ without a validated deterministic equivalence explanation;
- isolated install/update/rollback gate fails.

## Completion condition

R0009 is complete only when the first internal installable candidate is reproducibly built and all non-hardware gates pass.

At that point update `docs/CODEX-HANDOFF.md` with the exact next stage for physical Keenetic validation. Do not perform hardware testing unless separately authorized.
