# R0009 completion report

R0009 is **PASS**. The internal installable candidate `0.1.0-r0009c01` was built from the immutable R0008 source commit `684b27bdb53e545047419baa87c63dd86dffa469`. It was not published.

## Produced candidate

- deterministic app-slot archive containing the exact R0008 Light application;
- Light-specific updater-v5 fork with `S23broray-light-updater`, signed release indexes, releaseId comparison, request/global locks, safe extraction, atomic switch, health gate and rollback;
- deterministic `aarch64-3.10` IPK with package lifecycle scripts and an exact Xray `26.7.28` bootstrap contract;
- clean installer with pinned package size and SHA-256;
- signed internal `release.json`, candidate manifest and SHA-256 manifest.

The clean-install contract places the verified Xray binary at `/opt/broray-light/runtime/xray`. Existing verified runtime and persistent `config`, `servers`, `subscriptions` data are preserved. Active full-BROray ownership is rejected fail-closed.

## Evidence

All 15 acceptance gates in `VALIDATION.json` are PASS. The corrected final Build A and Build B are byte-identical for all 8 artifacts. The disposable isolated-root suite passed 17/17 scenarios: clean install, installer rerun, exact Xray, signed update, equal-version no-op, downgrade refusal, rollback, persistence, malformed/hash-failed input rejection, lock contention/stale recovery and co-ownership safeguards.

The build-local `CANDIDATE-MANIFEST.json` intentionally records `candidateReady=false` because it is generated before validation. This checkpoint is the post-validation readiness attestation and records `candidateReady=true`.

No physical Keenetic, production server, public Stable/release, or `BROadmin/BROray` repository was changed. All 19 material process failures remain preserved as JSON receipts.

## Next stage

`PHYSICAL_KEENETIC_INSTALL_UPDATE_ROLLBACK_VALIDATION_OF_R0009_INTERNAL_CANDIDATE`

That stage requires separate authorization and must use the exact artifact hashes recorded by this checkpoint.
