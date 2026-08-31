# BROray-Light — Codex hand-off after R0009

## Current canonical continuation point

R0009 and its separately authorized physical Keenetic validation are **PASS**. The final internal installable candidate is `0.1.0-r0009c04`, built from exact source commit `684b27bdb53e545047419baa87c63dd86dffa469`.

- canonical checkpoint: `checkpoints/R0009/CHECKPOINT.json`;
- validation: `checkpoints/R0009/VALIDATION.json` (15/15 PASS);
- reproducibility: `checkpoints/R0009/REPRODUCIBILITY-P31-C04.json` (Build A/B 8/8 byte-identical);
- isolated-root behavior: `checkpoints/R0009/ISOLATED-VALIDATION-P32-C04.json` (19/19 PASS);
- physical validation: `checkpoints/R0009/physical-validation/POST-BOOT-P43-C04-PERSISTENCE.json`;
- candidate package SHA-256: `e679d560c21b233a9454ff4e6779237db8056ba906f11550e44a87d3f3d9423b`.

No R0010 stage is defined in the repository. The exact next stage is therefore `DEFINE_AND_AUTHORIZE_R0010_BEFORE_ANY_STABLE_PUBLICATION`. Do not publish Stable/release or mutate a production server until that stage is explicitly specified and authorized.

The final router state is package `broray-light 0.1.0-r0009c04`, `current -> releases/0.1.0-r9`, healthy updater and primary services, exact Xray `26.7.28`, and persistent config/servers/subscriptions identities preserved across update, rollback, final restore, and reboot. Full BROray ownership, `Proxy0`, and routes via `Proxy0` are zero in post-boot checks.

## Physical-validation continuation update

Physical validation was subsequently authorized on Keenetic Peak KN-2710. Candidate `0.1.0-r0009c01` was rejected by the real Entware `opkg` because its outer IPK carrier was Debian `ar`; it is superseded.

Candidate c02 corrected the Entware carrier. Physical update then exposed two concrete device-only failures: c02 primary-service PID handoff and c03 BusyBox `mv -f` destination-symlink dereference. Candidate c04 contains both bounded corrections: package-owned singleton PID handoff and updater `mv -fT` atomic current-slot replacement. Canonical R0008 application source bytes remained unchanged.

The product-authorized full-BROray uninstall completed before Light installation. Final physical gates passed for signed update, equal-version no-op, downgrade refusal, forced rollback, final restore, native reboot persistence, native unauthenticated API rejection, and zero full-BROray/Proxy0 ownership. Material failures remain preserved under `checkpoints/R0009/process-failures/` and must not be silently retried by future work.

## R0008 provenance

## Canonical continuation point

R0008 builds the first independent BROray-Light source tree from exact BROray Stable `3.0.0-r23` / candidate `3.0.0-r23c02`.

R0008 source validation status: **PASS**. Remote persistence status is recorded separately in `checkpoints/R0008/REMOTE-PERSISTENCE.json`; if that file is absent, treat the source checkpoint as local-only.

Do **not** restart from full BROray `main`. Do **not** copy the complete r23 app and hide pages. R0008 is already the reduced source baseline.

## Source baseline

- exact donor application SHA-256: `69679f6d7339b856faf28f69cb1800254984e5400201fe97247011ab166c3f85`;
- preparation checkpoint: `R0007`;
- builder: `tools/build_broray_light_r0008.py`;
- generated source: `src/`;
- generated source files: `121`;
- generated source logical bytes: `627326`;
- builder SHA-256: `472473d9eb3082dc0198d0b189df21198b458bd24a136bfb3901bdba469b5e39`;
- `src/SHA256SUMS` SHA-256: `e056585d6a517ddbbbaebf08b68f17eb2d9d7ccd68d86df5cdee9fd4665f2419`.

## Product invariants

Read `INVARIANTS.json` before changing code. The non-negotiable summary is:

- VLESS only;
- three functional pages: Home, Servers, Subscriptions;
- deterministic automatic failover stays;
- no rankings, ratings, ping/jitter history or scheduled quality-refresh;
- Keenetic managed proxy status/configure/repair/refresh lives on Home;
- preserve r23 ownership/write-policy/rollback and zero-or-one `proxy connect via` validator;
- one primary app init: `S24broray-light`;
- Xray runtime is separate under `/opt/broray-light/runtime/xray`;
- updater is a separate Light control plane and is **not built yet**;
- full BROray and Light must not actively co-own proxy/web/runtime state; default is fail-closed.

## R0008 validation already completed

See `VALIDATION.json`. Important proven gates:

- builder reproducibility: 119/119 implementation files byte-identical;
- source checksum verification: 120/120;
- ash: 79/79;
- JS: 7/7;
- JSON: 16/16;
- internal path dependencies: 64 refs, 0 missing;
- expected WebUI API endpoints: 29/29;
- treatment map execution: 287/287, no DROP file present;
- VLESS import/config smoke: PASS;
- manual duplicate guard: PASS;
- subscription stable importKey/reorder: PASS;
- active subscription server disappearance: FAIL-CLOSED PASS;
- deterministic failover/exclusion: PASS;
- r23 Keenetic connect-via ownership validator: PASS;
- forced post-activation connectivity failure rollback: PASS;
- single-service clean start with no Xray config: PASS.

## Known process failures

All material failures are preserved under `process-failures/`. They are not current blockers. In particular:

- an early builder ordering error for `app/share/defaults`;
- read-only donor-derived working copy during interface-owner adaptation;
- one builder patch-point assumption failure;
- one subscription test-harness code/state-root mix-up (temporary source pollution was removed before final rebuild);
- Xray namespace was once double-adapted to `/opt/broray-light-light` and is fixed;
- first reproducibility pass differed only in historical ownership comments; fixed in builder.

Future Codex work must not repeat these approaches.

## What is NOT proven yet

R0008 is a **source-tree checkpoint**, not an installable release. It has not yet passed:

- physical Keenetic installation;
- real ndmc write mutations;
- real router Xray execution;
- Light updater installation/update/rollback path;
- reproducible `.ipk`/release carrier build;
- clean install / update / same-version reinstall on a physical router.

Do not label R0008 a release candidate.

## R0008 next-stage record (completed by R0009)

`BUILD_LIGHT_UPDATER_INSTALLER_AND_INSTALLABLE_CANDIDATE_FROM_R0008` — **PASS in R0009**

The next stage should:

1. fork updater-v5 semantics for `broray-light` paths/package identity and one-service health topology;
2. preserve signed releaseId comparison, request/global locks, atomic app-slot switch, health gate and rollback;
3. create an installer/package using the exact R0008 source bytes;
4. build twice and compare outputs/reproducibility receipts;
5. only then begin physical Keenetic install/update testing.

Do not re-open R0008 architecture unless a concrete validation failure requires it.
