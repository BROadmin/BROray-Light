# CODEX R0010 — public Stable release

## Objective

Publish and validate the first public BROray-Light Stable release from the completed R0009 candidate while preserving the exact R0008 source lineage and all Light safety invariants.

Stage identifier:

`PUBLISH_AND_VALIDATE_BRORAY_LIGHT_STABLE_RELEASE`

Public version, package version, candidate ID, and release ID:

`1.0.0-r1`

Git tag:

`v1.0.0-r1`

## Canonical inputs

- R0008 source commit: `684b27bdb53e545047419baa87c63dd86dffa469`
- R0009 final commit: `90431e9220ad17652189323785342a1c19b187b2`
- R0009 checkpoint SHA-256: `3d7f7407df7b8eba6b4cc7f423e1bcba5ce48c1108a1ca3d7f0a850a2f3fd2fe`
- R0009 status: `PASS`, 20/20 acceptance, 51/51 isolated, 8/8 Build A/B byte-identical

R0009 remains historical internal evidence. Its artifacts are not directly publishable because they contain `internal.invalid`, require the `internal-r0009` channel, have no default Stable index URL, and were signed by an intentionally destroyed private key. This is preserved as R0010 failure `R001`.

## Stable distribution contract

- Repository: `BROadmin/BROray-Light`
- Immutable release tag: `v1.0.0-r1`
- Stable index: `https://github.com/BROadmin/BROray-Light/releases/latest/download/release.json`
- Stable index signature: the index URL plus `.minisig`
- Versioned asset base: `https://github.com/BROadmin/BROray-Light/releases/download/v1.0.0-r1/`
- Channel field: `stable`
- Redirects are permitted only from HTTPS to HTTPS.
- The updater must default to the Stable index while retaining an explicit environment override for isolated tests.
- Published objects must be byte-identical to both independently reproduced final builds.
- The visible product/package version remains `1.0.0-r1`, while final CSS/JavaScript URLs use the distinct deterministic cache token `1.0.0-r1-r0010`. This prevents a browser from reusing JavaScript from the unpublished internal package that temporarily carried the same visible version.

## Signing-key governance

- Create a new minisign identity for the public Stable lineage.
- Commit only `updater/release.pub`.
- Store the private key in GitHub Actions secret `BRORAY_LIGHT_MINISIGN_PRIVATE_KEY` using GitHub encrypted-secret transport.
- Never place private-key bytes, passphrases, credentials, or access tokens in the repository, logs, checkpoints, command output, or release assets.
- Keep a local plaintext key only for the bounded signing/publication revision; destroy it after public signatures and remote-secret presence are verified.
- Future release signing must use the same governed secret so installed clients retain a stable trust root.

## Scope constraints

- VLESS only.
- No Routes.
- No DNS-over-TLS management.
- No ratings, quality history, or scheduled quality refresh.
- Preserve native authentication/session protection.
- Preserve updater locks, signed-index validation, downgrade refusal, atomic slot switching, health gate, rollback, and previous-good slot.
- Fail closed on ambiguous full BROray/BROray-Light co-ownership.
- Do not modify `BROadmin/BROray`.

## Required outputs

- Stable-specific updater and package metadata.
- Public clean installer.
- Independent Build A and Build B.
- Deterministic manifests and SHA-256 files.
- Signed Stable `release.json` and `release.json.minisig`.
- Isolated-root clean install, update, equal-version, downgrade refusal, rollback, persistence, and public installer tests.
- Automated WebUI button/API contract audit.
- Same-visible-version Web asset cache-collision regression coverage.
- Public URL TLS/redirect/MIME/cache and byte-identity evidence.
- Authorized physical-router replacement of the unpublished internal r1 package, then Stable check/equal-version and functional validation.
- Git tag and GitHub Release.
- `checkpoints/R0010/CHECKPOINT.json`, `VALIDATION.json`, `REPORT.md`, aggregate `SHA256SUMS`, and publication receipts.

## Acceptance gates

1. R0008 and R0009 input identities PASS.
2. R0010 start checkpoint and all process failures have valid SHA-256 sidecars.
3. Stable URLs, tag, channel, and updater default are exact.
4. Stable public signing identity is generated, verified, and committed without private material.
5. GitHub Actions encrypted secret is present and the plaintext private key is absent after publication.
6. Updater static/syntax and signed-index tests PASS for `stable`.
7. Package metadata/lifecycle and clean installer static/syntax tests PASS.
8. Build A and independent Build B are byte-identical for every release artifact.
9. All deterministic manifests and SHA-256 files verify.
10. Isolated clean install produces exact Xray and a healthy app slot.
11. Isolated newer update, equal-version no-op, downgrade refusal, rollback, and persistence PASS.
12. Automated WebUI page/button/API contract audit and the distinct final Web asset cache-token regression PASS.
13. No forbidden full-BROray routes/DNS/quality/protocol modules are introduced.
14. Exact release-source commit is pushed; tag `v1.0.0-r1` targets that commit. A later evidence-only checkpoint commit may record observations that can exist only after publication, but must not change release inputs or bytes.
15. GitHub Release is public, non-draft, non-prerelease, and contains the complete asset set.
16. Public HTTPS URLs, HTTPS-only redirects, expected content types, cache policy, sizes, and SHA-256 PASS.
17. Every published asset is byte-identical to Build A and Build B.
18. Public clean installer passes in an isolated root.
19. Authorized physical router runs the exact public package, Stable update-check reports equal/no-op, services and Xray are healthy, and state persists.
20. Final machine-readable records, repository secret scan, status, and checkpoint sealing PASS.

`releaseReady` and `publicReleasePublished` remain false until all 20 gates pass.

## FIRST-ERROR policy

At the first material failure, stop that revision. Save a standalone JSON record under `checkpoints/R0010/process-failures/`, add its SHA-256 sidecar, append `project/WORKLOG.jsonl`, update `project/R0010-STATE.json`, and start only a named corrected revision. Never silently retry the same revision.
