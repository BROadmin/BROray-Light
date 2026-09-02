# Codex handoff

## Current state

R0010 `PUBLISH_AND_VALIDATE_BRORAY_LIGHT_STABLE_RELEASE` is authorized and in progress on `codex/r0009-updater-package`. Public version remains `1.0.0-r1`; no public release existed when R0010 started.

R0010 CHECKPOINT-FIRST evidence begins at `checkpoints/R0010/START-P1.json`. Direct publication of the R0009 bytes failed closed at `checkpoints/R0010/process-failures/FAILURE-R001-P2-R0009-INTERNAL-PUBLICATION-CONTRACT.json`: those bytes use `internal.invalid`, require channel `internal-r0009`, lack a default Stable index URL, and their private signing key was destroyed. No public, production, or router mutation occurred during that failed revision.

The corrected R0010 revision uses GitHub Releases, tag `v1.0.0-r1`, Stable index `https://github.com/BROadmin/BROray-Light/releases/latest/download/release.json`, versioned asset URLs, and a new Stable minisign identity whose private key must be retained only as encrypted GitHub Actions secret `BRORAY_LIGHT_MINISIGN_PRIVATE_KEY`.

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

`DEFINE_AND_AUTHORIZE_R0010_BEFORE_ANY_STABLE_PUBLICATION`

Stop here unless that stage is explicitly defined and authorized. Do not publish Stable or mutate a production server under the completed R0009 authorization.
