# Codex handoff

## Current state — R0013 / P89: external Xray compatibility checked

Actual ARM64 test-router processes using the unchanged active external VLESS/XHTTP/REALITY outbound: 26.2.6 FAIL on first HTTPS request (curl 35), despite config/start PASS. No retry. This supports the prior pinned BROray rejection; P88 localhost PASS must not be interpreted as external compatibility. 26.3.27, 26.6.27, 26.7.11, 26.7.28, 26.9.8 and 26.9.9 each PASS 3/3 HTTPS endpoints with certificate checks. Explicit 26.9.9 before/after controls PASS; all positive exit-IP hashes match. Installed 26.9.9 PID 4340/start 40388289 and durable hashes preserved; exact private tmpfs cleanup PASS. No installed-version switches, native lifecycle/browser claim, registry edit, release or product source changes. See checkpoints/R0013/XRAY-EXTERNAL-P89.md and JSON. Before release, incorporate the negative compatibility evidence; complete remaining WebUI/lifecycle/signing acceptance. candidateReady=false, releaseReady=false.

## Current state — R0013 / P88: bounded Xray compatibility PASS

User requested Xray version compatibility checks, not installation. Official ARM64 26.9.9, 26.9.8, 26.7.28, 26.7.11, 26.6.27, 26.3.27 and 26.2.6 passed 91 real localhost VLESS data paths, 182 generated config checks and 7 checks of the current active config. Installed generator bytes are manifest-bound. Exact original managed PID 18775/starttime 39982859 and runtime/config/manifest hashes were preserved. Router scratch used protected tmpfs and was removed. Router now has an active user configuration; the earlier P87 empty-state observation is historical, do not reset it. 26.9.9 remains installed; it is an official prerelease. Official latest stable is 26.3.27 as of 2026-09-11. WS/gRPC/legacy headers.Host deprecation warnings remain forward-compatibility risks. Shipped compatibility registry was deliberately not changed. Four fixture failures and a broad-PID snapshot false alarm are retained; raw failed evidence is immutable and exact managed identity was confirmed separately without repeating version tests. See checkpoints/R0013/XRAY-COMPATIBILITY-P88.md and JSON/evidence siblings. P83 regression run 34575296136 now has all five jobs successful. candidateReady=false; releaseReady=false; no 2.0.0 publication. Remaining acceptance still includes WebUI/backend controls, external VLESS paths, physical restart/persistence, signed update and final signing/publication/docs gates. No application source changes, install or restart in P88.

## Current state — R0013 / P87: full test-router replacement PASS

192.168.1.1 now has exact corrected P83 BROray-Light 2.0.0 (releaseId 2.0.0-r1), source commit 14813c3774207502039999e014062464043827d1. Full BROray and its stale S99 bootstrap were removed with verified private off-router backups. P83 independent Build A/B match 8/8; 100 native CGI/session tests and exact clean-package tests pass. P81 CGI PATH failure is resolved by P83; P84 native opkg replacement preserves durable config/Xray hashes; P85 actual Keenetic native browser login and 401/405 guards pass. All three pages load. Catalog is intentionally empty; no active VLESS or proxy interface yet. 18 invocation scratch files and 3 directories removed from router RAM; local backups remain in ignored private dist/R0013/private-target/p74. Do not commit those archives or credentials. candidateReady=false; releaseReady=false; no 2.0.0 publication. Next: R0013_P88_FUNCTIONAL_VLESS_AND_ALL_WEBUI_BACKEND_ACCEPTANCE_ON_REPLACED_TEST_TARGET. First collect final P83 component regression run 34575296136 (native-auth and prepared-app passed, live-entry still running at P87 snapshot); then actual VLESS/all buttons, restart/persistence/signed updater and signing/publication/docs gates. See checkpoints/R0013/REPORT.md and TARGET-REPLACEMENT-P87.json. Historical paragraphs below do not override this state.

## Current state — R0013 / P83

Full BROray on the explicitly authorized test router 192.168.1.1 was removed by its official full uninstall worker after verified private backups. Exact obsolete S99 bootstrap and completed handoff files were backed up and retired. P72 Light 2.0.0 installed via native opkg; S23/S24, slot manifest, Xray 26.9.9 and protected RAM passed P80. P72 independent A/B and all five component regression jobs passed. P81 physical browser login failed HTTP 500 before native auth: runtime guard preceded PATH initialization and could not find Entware stat. Failure is recorded; no login retry or router hotpatch. P83 adds early Entware PATH setup and empty/shadowed PATH CGI tests. Next: fresh A/B and native regression, controlled clean Light package replacement, then native login validation. Candidate/release readiness remains false; nothing published. Private backups: dist/R0013/private-target/p74 (never commit secrets). See project/R0013-STATE.json and checkpoints/R0013/CHECKPOINT.json.

## Current authorized state — R0013 / P72 (target replacement)

The user explicitly authorized full replacement on test router 192.168.1.1: "Сделай полную замену на тестовом роутере". START-P71 records the scope. Preserve a verified private off-router backup before removing the installed full product through its audited uninstall worker. P73 backup stopped before creating an archive because /opt/usr/bin/tar is a stripped extractor; failure is retained. P74 uses verified /opt/bin/tar (GNU tar). P72 declares coreutils-stat and adds pre-write installer diagnostics/tests. New independent builds and local backup verification must pass before product removal. No production server or full-BROray repository changes are authorized.

## Historical P70 blocker and validated engineering baseline

BROray-Light public/package version 2.0.0 (internal updater releaseId 2.0.0-r1) is **BLOCKED_FAIL_CLOSED_USER_TARGET_DECISION_REQUIRED**. Read `docs/CODEX-R0013.md`, `project/R0013-STATE.json`, and `checkpoints/R0013/CHECKPOINT.json`. Keep branch `codex/r0009-updater-package` and preserve all R0012 work.

Independent unsigned Build A/B match 8/8 bytes; P64 has five successful jobs and 479 uniquely counted JSON tests. Prepared application lifecycle, isolated exact clean package, native HTTP/CGI/session and P66 Chromium fixture controls pass within the boundaries in `checkpoints/R0013/REPORT.md`. Full functional backend button acceptance, signing and physical target validation remain. `candidateReady=false`; 2.0.0 is not published.

Read-only SSH at 192.168.1.1 found full BROray package 3.0.0-r14, `/opt/broray`, and its S24 service. Light directory/service are absent. BusyBox stat lacks required -f/-c options and coreutils-stat is absent. No router mutations occurred. Do not install alongside, adopt, remove or alter full BROray without a new explicit target decision. Failures P67/P68/P69 and hashes are preserved.

Exact next action: `USER_SELECT_CLEAN_TEST_TARGET_OR_EXPLICITLY_AUTHORIZE_SEPARATELY_PLANNED_FULL_BROray_REMOVAL_THEN_RESOLVE_STAT_PREREQUISITE`.

## Historical R0010 state (not current device evidence)

R0010 `PUBLISH_AND_VALIDATE_BRORAY_LIGHT_STABLE_RELEASE` is complete with PASS on `codex/r0009-updater-package`. Stable `1.0.0-r1` is public at `https://github.com/BROadmin/BROray-Light/releases/tag/v1.0.0-r1`; GitHub release `381203509` is latest, public, non-draft and non-prerelease with all eight expected assets.

The immutable release-source commit is `9e5fce9bfa7c82bfc2f2654d80fd3987c5259963`. Annotated tag object `88107747fe9c76763a2c6fb2166fc8a840444078` dereferences exactly to that commit. Stable index is `https://github.com/BROadmin/BROray-Light/releases/latest/download/release.json`; visible version is `1.0.0-r1` and the cache-safe Web asset token is `1.0.0-r1-r0010`.

Build A `dist/R0010/1.0.0-r1-P50-Cache-Final-Build-A` and independent Build B `dist/R0010/1.0.0-r1-P53-Cache-Final-Build-B` are 8/8 byte-identical. Isolated validation is 52/52 PASS, the complete WebUI audit is 20 button actions and 23 endpoint bindings PASS, and all 20 R0010 acceptance gates are PASS.

The exact public installer and package passed a fresh BusyBox chroot clean-install validation and an authorized physical equal-version install/update validation. The router ends on `current -> releases/1.0.0-r1`, Xray `26.7.28`, both services healthy, public root HTTP 200 and protected API HTTP 401. Nineteen persistent user files retain aggregate SHA-256 `ff28e9aa7920cbfbcebcff91d2259224ca10f6943dceebd8cd0980192a7f00a8`.

Stable signing identity is minisign key ID `F8ABF7C93FAB7C1F`; `updater/release.pub` SHA-256 is `b1587b8407f0c0443a361ed29b839319b66912b1b71414bcf31e848c29eab696`. The encrypted GitHub Actions secret `BRORAY_LIGHT_MINISIGN_PRIVATE_KEY` is present, its value was never read, and the bounded local plaintext private key was deleted and proved absent. `candidateReady=true`, `releaseReady=true`, and `publicReleasePublished=true`.

## Historical R0009 baseline

- Branch: `codex/r0009-updater-package`
- R0009 status: **PASS**
- Candidate and release ID: `1.0.0-r1`
- `candidateReady=true`
- Acceptance gates: 20/20 PASS
- Isolated-root gates: 51/51 PASS
- Build A/B: 8/8 artifacts byte-identical
- Authorized physical WebUI and persistence validation: PASS
- Public release: not published
- Production server: not modified
- Ephemeral private signing key: destroyed

Canonical R0008 source commit `684b27bdb53e545047419baa87c63dd86dffa469` remains unchanged: 121 files, 627326 logical bytes, `src/SHA256SUMS` SHA-256 `e056585d6a517ddbbbaebf08b68f17eb2d9d7ccd68d86df5cdee9fd4665f2419`.

## Historical R0009 evidence

- Checkpoint: `checkpoints/R0009/CHECKPOINT.json`
- Checkpoint SHA-256: `3d7f7407df7b8eba6b4cc7f423e1bcba5ce48c1108a1ca3d7f0a850a2f3fd2fe`
- Validation: `checkpoints/R0009/VALIDATION.json`
- Validation SHA-256: `172cbc7fab4985914c65c539e2595a330ef34dc86a013901391ca6ee20cf6c0d`
- Report: `checkpoints/R0009/REPORT.md`
- Report SHA-256: `004d44ccfbc34c8526447821ad3d211da44a2d007f094ee16d081fdc3f417c47`
- Aggregate SHA256SUMS SHA-256: `8dc0c79f4d4b9f6a23a1c65ab838b7c8fe843a9328c2752cb1d2bbcde95a4e4f`
- Build A: `dist/R0009/1.0.0-r1-P531-Final-Build-A`
- Build B: `dist/R0009/1.0.0-r1-P532-Final-Build-B`
- Reproducibility receipt: `checkpoints/R0009/REPRODUCIBILITY-P532-FINAL-1.0.0-R1.json`
- Isolated validation receipt: `checkpoints/R0009/ISOLATED-VALIDATION-P533-FINAL-1.0.0-R1.json`
- Final local audit: `checkpoints/R0009/FINAL-LOCAL-AUDIT-P556-FINAL-1.0.0-R1.json`
- Signing-key destruction: `checkpoints/R0009/SIGNING-KEY-DESTRUCTION-P558-FINAL-1.0.0-R1.json`
- Exact physical install: `checkpoints/R0009/physical-validation/INSTALL-P537-FINAL-P531-1.0.0-R1.json`
- Final physical functional state: `checkpoints/R0009/physical-validation/BROWSER-P545-P531-SUBSCRIPTION-CLEANUP-PERSISTENCE.json`

The router ends with `broray-light 1.0.0-r1`, `current -> releases/1.0.0-r1`, primary/updater services healthy, exact Xray `26.7.28`, zero test servers, zero test subscriptions, no active server, automatic switching disabled, no owned `Proxy0`, zero routes via `Proxy0`, and zero full-BROray ownership. No router reboot was performed in the final corrective cycle; the retained earlier native-reboot automatic-start receipt is PASS.

## R0010 final evidence

- Checkpoint: `checkpoints/R0010/CHECKPOINT.json`
- Checkpoint SHA-256: `82d740011bd95cce3b97e893fefd4e397863a89e72d7dfe1959a536baaf8ddee`
- Validation: `checkpoints/R0010/VALIDATION.json`
- Validation SHA-256: `517a1d3db56065fb343a12000ecf56daec5d67d7126c2fb3c1bf0db10dc8bdf6`
- Report: `checkpoints/R0010/REPORT.md`
- Report SHA-256: `95dc46326eafcb41d6ba4cf426c3652e4fd5d2378570b8ed6f62cde7f4cf9020`
- Aggregate SHA256SUMS SHA-256: `9233840af01227d14e5d29a1f01d181d29791e9ecfffee17783a474a8d12910c`
- Reproducibility: `checkpoints/R0010/REPRODUCIBILITY-P54-CACHE-CORRECTED-STABLE-1.0.0-R1.json`
- Isolated validation: `checkpoints/R0010/ISOLATED-VALIDATION-P58-CACHE-CORRECTED-STABLE-1.0.0-R1.json`
- WebUI audit: `checkpoints/R0010/WEBUI-BUTTON-AUDIT-P59-CACHE-CORRECTED-STABLE.json`
- Public installer isolated validation: `checkpoints/R0010/publication/PUBLIC-INSTALLER-ISOLATED-P101.json`
- Physical exact-public-package validation: `checkpoints/R0010/physical-validation/PUBLIC-PACKAGE-EQUAL-BACKEND-P106.json`
- Authenticated Stable-equal WebUI validation: `checkpoints/R0010/physical-validation/WEBUI-STABLE-EQUAL-P107.json`
- Plaintext signing-key destruction: `checkpoints/R0010/SIGNING-KEY-DESTRUCTION-P111.json`
- Corrected postseal audit: `checkpoints/R0010/POSTSEAL-AUDIT-P117.json`

All 50 R0010 material process failures are preserved individually with valid SHA-256 sidecars. Production server and `BROadmin/BROray` were not modified; the only physical target was the explicitly authorized router.

## Exact next stage

`DEFINE_AND_AUTHORIZE_R0011_BEFORE_ANY_POST_RELEASE_CHANGE`

Do not make post-release product changes until R0011 is explicitly defined and authorized.
