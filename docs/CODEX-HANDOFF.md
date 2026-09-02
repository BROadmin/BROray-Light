# Codex handoff

## Current state

R0010 `PUBLISH_AND_VALIDATE_BRORAY_LIGHT_STABLE_RELEASE` is authorized and in progress on `codex/r0009-updater-package`. Public version remains `1.0.0-r1`; no public release exists yet.

R0010 CHECKPOINT-FIRST evidence begins at `checkpoints/R0010/START-P1.json`. Direct publication of the R0009 bytes failed closed at `checkpoints/R0010/process-failures/FAILURE-R001-P2-R0009-INTERNAL-PUBLICATION-CONTRACT.json`: those bytes use `internal.invalid`, require channel `internal-r0009`, lack a default Stable index URL, and their private signing key was destroyed. No public, production, or router mutation occurred during that failed revision.

The corrected R0010 revision uses GitHub Releases, tag `v1.0.0-r1`, Stable index `https://github.com/BROadmin/BROray-Light/releases/latest/download/release.json`, versioned asset URLs, and a new Stable minisign identity whose private key must be retained only as encrypted GitHub Actions secret `BRORAY_LIGHT_MINISIGN_PRIVATE_KEY`.

A physical browser gate found that the unpublished internal package and the prospective Stable package shared the same `1.0.0-r1` Web asset URLs, allowing old JavaScript to remain cached. Failure R017 and diagnosis P48 invalidate release-source commit `0bde5139137cc8166d1ef282a41cf9e697254c9b` and its builds. The targeted correction keeps the visible version `1.0.0-r1` and uses hidden CSS/JavaScript cache token `1.0.0-r1-r0010`.

The cache-corrected Build A at `dist/R0010/1.0.0-r1-P50-Cache-Final-Build-A` and independent Build B at `dist/R0010/1.0.0-r1-P53-Cache-Final-Build-B` are 8/8 byte-identical. Their package SHA-256 is `707431aa20c01958edfe40ed04a70c24308a9dabc9ff26f758101c952827d432`; the app archive SHA-256 is `2b2d22e9a172b28229aa19ca904f1810722da21b5d34f27eafd79d5acac1e5b0`. The new isolated suite is 52/52 PASS and the WebUI binding audit is 20 actions/23 endpoints PASS.

The router still runs the now-invalidated pre-cache-correction package. The next physical mutation must install only the exact cache-corrected package after a new release-source commit is created and pushed. The Stable private key remains temporarily present only in its bounded external signing directory until public byte/signature validation completes; its encrypted GitHub Actions secret is already present.

Until all 20 gates in `docs/CODEX-R0010.md` pass, `releaseReady=false` and `publicReleasePublished=false`.

## R0009 baseline

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

## Final evidence

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

## Exact next stage

`SEAL_AND_PUSH_CACHE_CORRECTED_RELEASE_SOURCE_COMMIT_THEN_INSTALL_AND_BROWSER_VALIDATE_THE_EXACT_CACHE_CORRECTED_PACKAGE`

R0010 publication, production mutation, and physical-router validation are explicitly authorized. Do not publish until the remaining R0010 gates pass on the cache-corrected bytes.
