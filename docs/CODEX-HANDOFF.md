# BROray-Light — Codex hand-off after R0008

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

## Next allowed stage

`BUILD_LIGHT_UPDATER_INSTALLER_AND_INSTALLABLE_CANDIDATE_FROM_R0008`

The next stage should:

1. fork updater-v5 semantics for `broray-light` paths/package identity and one-service health topology;
2. preserve signed releaseId comparison, request/global locks, atomic app-slot switch, health gate and rollback;
3. create an installer/package using the exact R0008 source bytes;
4. build twice and compare outputs/reproducibility receipts;
5. only then begin physical Keenetic install/update testing.

Do not re-open R0008 architecture unless a concrete validation failure requires it.
