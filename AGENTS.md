# BROray-Light — Codex working contract

This repository contains a separate lightweight product for Keenetic/KeeneticOS. Do not treat it as a UI mode of full BROray.

## Current authorized task

Work only on stage `R0012` in the already active branch `codex/r0009-updater-package`:

`RELOCATE_RUSSIAN_DOCUMENTATION_AND_REMOVE_EMBEDDED_WEBUI_GUIDE_STABLE_1.0.0_R3`

Read these files before changing code:

1. `docs/CODEX-HANDOFF.md`
2. `docs/CODEX-R0012.md`
3. `docs/CODEX-R0011.md`
4. `docs/CODEX-R0010.md`
5. `docs/CODEX-R0009.md`
6. `project/IMPLEMENTATION-STATE.json`
7. `project/INVARIANTS.json`
8. `project/R0012-STATE.json`
9. `project/R0011-STATE.json`
10. `project/R0010-STATE.json`
11. `project/R0009-STATE.json`
12. `project/WORKLOG.jsonl`
13. `checkpoints/R0012/START-P1.json`

R0012 corrects the user-rejected R0011 placement: the complete Russian instruction belongs on the `BROadmin/BROray-Light` GitHub landing page and in a distinct section on `docs.brovibe.cloud`, not inside the application WebUI. It is authorized to issue immutable Stable `1.0.0-r3`, validate it on the already authorized physical test router, and change only the documentation-site files under `BROadmin/BROray/site/docs.brovibe.cloud/` needed by the existing automatic publisher. It must not overwrite earlier releases, change the docs homepage content, change the production server, modify full-BROray application code, or introduce excluded full-product features.

## R0011 documentation release rules

- Preserve Stable `1.0.0-r1` and tag `v1.0.0-r1` byte-for-byte.
- Use release/package/candidate ID `1.0.0-r2`, tag `v1.0.0-r2`, and Web asset cache token `1.0.0-r2-r0011`.
- Keep exactly three functional WebUI pages. The embedded guide belongs to Home and must not introduce a new functional page or API.
- The Russian guide must document installation, first login, three-page operation, subscriptions and their auto-refresh, duplicate handling, failover, Keenetic interface, Xray reinstall/update, Light Stable update, diagnostics, persistence, removal, security, support, and license.
- Use the existing Stable minisign trust root. Sign only through the encrypted GitHub Actions secret `BRORAY_LIGHT_MINISIGN_PRIVATE_KEY`; never read or print its value and never recreate a plaintext local private key.
- Repeat Build A/B, isolated regression, WebUI control and endpoint audit, browser desktop/mobile validation, public-byte validation, and authorized physical-router validation.
- CHECKPOINT-FIRST and FIRST-ERROR remain mandatory under `checkpoints/R0011/`.

## R0010 release rules

- Keep public version and release ID `1.0.0-r1`; it has not previously been published.
- Preserve the R0009 candidate and evidence as immutable historical input.
- The R0009 internal bytes must not be published directly: their `internal.invalid` URLs, `internal-r0009` channel contract, absent default index URL, and destroyed signing key are a recorded R0010 first-error failure.
- Build a corrected Stable revision from the verified R0009/R0008 inputs without redesigning the product.
- Use the immutable GitHub release tag `v1.0.0-r1` and the Stable index URL `https://github.com/BROadmin/BROray-Light/releases/latest/download/release.json`.
- Use versioned GitHub release asset URLs for the application archive, IPK, and installer.
- Establish a new release signing identity. Store the private key only as an encrypted GitHub Actions secret and destroy all local plaintext copies after publication validation. Commit only the public key.
- Repeat independent Build A/B, complete isolated-root validation, all WebUI button checks, public URL/TLS/MIME/cache validation, exact published-byte verification, and authorized physical-router install/update/equal-version validation.
- CHECKPOINT-FIRST and FIRST-ERROR remain mandatory. Record every material failed revision under `checkpoints/R0010/process-failures/` before a corrected revision.
- Do not tag, publish, or call the result ready until every R0010 acceptance gate is PASS.

## Immutable input

Canonical R0008 source commit:

`684b27bdb53e545047419baa87c63dd86dffa469`

R0008 is already `SOURCE_TREE_REMOTE_PASS`. Do not rebuild architecture from full BROray. Do not replace `src/` with current `BROadmin/BROray/main`. Do not reopen R0008 unless a concrete failing R0009 validation proves a defect in R0008.

Canonical R0008 identities:

- source files: `121`
- source logical bytes: `627326`
- builder SHA-256: `472473d9eb3082dc0198d0b189df21198b458bd24a136bfb3901bdba469b5e39`
- `src/SHA256SUMS` SHA-256: `e056585d6a517ddbbbaebf08b68f17eb2d9d7ccd68d86df5cdee9fd4665f2419`
- source checkpoint SHA-256: `6686586ed777a7b0c37336d08143d388fdc301536b32c96eb35e8b20e5393953`

## Product invariants — non-negotiable

- VLESS only.
- Exactly three functional WebUI pages: Home, Servers, Subscriptions.
- Deterministic automatic failover stays.
- No ratings, ranking, ping/jitter history, quality history, or scheduled quality-refresh.
- Keenetic managed proxy status/configure/repair/refresh lives on Home.
- Preserve r23 managed-interface ownership, write-policy, rollback, and zero-or-one `proxy connect via` validator.
- One primary application service: `S24broray-light`.
- Xray runtime remains separate at `/opt/broray-light/runtime/xray`.
- Updater is a separate BROray-Light control plane.
- Full BROray and BROray-Light must not actively co-own proxy/WebUI/runtime state; fail closed by default.
- Native authenticated WebUI/API session contract must remain intact.
- Router runtime scripts must remain BusyBox `ash` compatible. Do not introduce Bash-only runtime syntax.

## R0009 rules

R0009 must build the updater, installer/package, and first installable internal candidate from the exact R0008 bytes.

Do not publish a public BROray-Light release or invent a final product version during R0009. Use an internal candidate/build identifier until all R0009 gates pass.

The updater must be a Light-specific fork of mature BROray updater-v5 semantics, not a blind string replacement. Preserve:

- signed release index verification;
- releaseId comparison semantics;
- downgrade prevention;
- request/global locks and stale-owner handling;
- archive SHA-256 and size verification;
- safe extraction/path traversal rejection;
- atomic app-slot switch;
- post-switch health gate;
- automatic rollback;
- previous-good slot preservation.

Remove full-BROray-only behavior:

- `/opt/broray` product identity;
- full `broray` package identity;
- routes-operation awareness and resumable-route state;
- legacy full-BROray migrations that are not explicitly required by Light;
- five-service full-BROray health topology;
- full-BROray required-file assumptions.

Target namespaces:

- application: `/opt/broray-light`
- updater state: `/opt/var/lib/broray-light-updater`
- application operation state: `/opt/var/lib/broray-light/operations`
- global operation lock: `/opt/var/lock/broray-light/global-operation.lock`
- Xray runtime: `/opt/broray-light/runtime/xray`
- primary service: `/opt/etc/init.d/S24broray-light`
- updater service/control plane: use a distinct Light-specific init/control identity and record the choice in `project/R0009-STATE.json`

## Xray bootstrap rule

R0008 contains the Light wrapper but not a bundled Xray executable. R0009 must resolve and verify the exact Xray runtime artifact required for clean installation from the pinned Stable/release evidence. Do not reuse a remembered checksum without re-verification.

A clean install that leaves `/opt/broray-light/runtime/xray` absent is a hard FAIL.

## Required build discipline

- CHECKPOINT-FIRST.
- FIRST-ERROR: stop the current revision at the first material failure; do not silently retry the same revision.
- Split long validation into short independent gates.
- Never report background/asynchronous progress.
- Every completed stage must have an artifact/checkpoint and SHA-256.
- Build A and Build B must be independent and reproducible. If outputs differ, R0009 is not PASS.
- Do not mutate `BROadmin/BROray`, any production server, or a physical router during R0009 packaging work.

## Required records for Codex continuity

After every meaningful substage append one JSON object to `project/WORKLOG.jsonl`.

Maintain `project/R0009-STATE.json` with at least:

- status;
- current revision;
- canonical input commit/hash identities;
- completed gates;
- first active blocker, if any;
- produced artifact paths and SHA-256;
- next exact action.

Material failures go under `checkpoints/R0009/process-failures/` as separate JSON records. Never erase a failed revision from history.

At R0009 completion create:

- `checkpoints/R0009/CHECKPOINT.json`
- `checkpoints/R0009/REPORT.md`
- `checkpoints/R0009/VALIDATION.json`
- `checkpoints/R0009/SHA256SUMS`
- reproducibility receipt for Build A/B
- installer/package manifests and checksums
- updated `docs/CODEX-HANDOFF.md`
- updated `project/IMPLEMENTATION-STATE.json`

## Candidate acceptance gate

Do not mark an installable candidate ready until all of these are PASS:

1. canonical R0008 source identity verification;
2. exact Xray bootstrap artifact verification;
3. updater static/syntax tests;
4. package/installer static/syntax tests;
5. safe archive/path validation;
6. updater releaseId/downgrade decision tests;
7. global/request lock tests;
8. isolated-root clean install test;
9. isolated-root update test;
10. isolated-root same-version reinstall/no-op contract test as defined by the Light updater;
11. forced health failure rollback test;
12. persistence of servers/subscriptions/config/Xray runtime across app-slot update where applicable;
13. Build A/B byte reproducibility or a documented deterministic container-format equivalence gate if byte-identical outer packaging is technically impossible;
14. artifact SHA-256 manifest verification;
15. no full-BROray routes/DNS/quality-history modules reintroduced.

Physical Keenetic testing is the next stage after R0009, not part of this branch unless explicitly authorized.

## Known bad approaches — do not repeat

Do not repeat previously recorded failures, including:

- rebuilding Light from full BROray `main`;
- merely hiding excluded full-BROray pages/modules;
- assuming donor files are writable before adapting them;
- relying on external `hexdump` for router-safe identifiers;
- using non-local `ash` variables in nested functions where collisions are possible;
- omitting stable subscription `importKey`;
- leaving route-policy state in interface ownership modules;
- weakening native WebUI authentication during simplification;
- long monolithic validation commands that exceed tool/runtime limits;
- treating source-tree PASS as an installable release candidate.

If instructions conflict, fail closed and record the conflict instead of guessing.
