# Codex handoff

## Current state

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
