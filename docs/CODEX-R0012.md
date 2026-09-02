# CODEX R0012 — relocation of the Russian guide and corrective Stable

## Objective

Correct the placement error from R0011 without redesigning BROray-Light:

1. publish the complete Russian guide in the default-branch README of `BROadmin/BROray-Light`;
2. publish a distinct BROray-Light section at `https://docs.brovibe.cloud/broray/#broray-light`, without adding a product card or guide section to the docs homepage;
3. remove the long-form guide from the application WebUI while preserving all three functional pages and every existing control;
4. deliver the WebUI correction as the next immutable Stable `1.0.0-r3`.

Stage identifier:

`RELOCATE_RUSSIAN_DOCUMENTATION_AND_REMOVE_EMBEDDED_WEBUI_GUIDE_STABLE_1.0.0_R3`

Public version, package version, candidate ID, and release ID:

`1.0.0-r3`

Git tag and Web asset cache token:

`v1.0.0-r3` and `1.0.0-r3-r0012`

## Canonical input

- R0011 release-source commit: `6d44c164f3ce7e99195a806f0a191bd66d3b8ed2`
- Immutable prior Stable: `1.0.0-r2`, tag `v1.0.0-r2`
- R0011 public package SHA-256: `aab765609dd5fe9e266e680e4d8a1ccf7db6880702ef07aa7996b98b05393c87`
- Corrected-scope checkpoint: `checkpoints/R0011/SCOPE-CORRECTION-P72.json`
- R0012 start checkpoint: `checkpoints/R0012/START-P1.json`

## Mutation boundaries

- Keep the local BROray-Light checkout on `codex/r0009-updater-package`.
- Preserve `v1.0.0-r1` and `v1.0.0-r2` byte-for-byte.
- The only permitted change in `BROadmin/BROray` is documentation-site material under `site/docs.brovibe.cloud/` required for the separate Light section and its checksum manifest.
- Do not add a BROray-Light content card or guide section to `site/docs.brovibe.cloud/index.html`.
- Do not change the docs production server or installed deployer. The Light documentation must use an already allowlisted deployed file.
- Do not change product behavior, VLESS parsing, subscriptions, deduplication, failover, Keenetic ownership, Xray, updater safety, authentication, or lifecycle semantics.
- Do not add Routes, DNS-over-TLS management, ratings, quality history, or scheduled quality refresh.
- Do not expose credentials or signing material.

## Required source correction

- Keep the complete Russian `README.md` and `docs/USER-GUIDE-RU.md`.
- Remove only the `.guide-card` section from packaged Home HTML.
- Remove only the guide copy helpers and guide setup from Home JavaScript.
- Remove only `.guide-*` and `.copy-guide-button` styles.
- Keep the existing dashboard and all functional button/endpoint bindings.
- Set the release manifest documentation fact `homeGuideIncluded` to `false`.

## Documentation publication contract

The GitHub default branch receives exactly the public documentation files needed by the repository landing page; it must not receive the development/release branch wholesale.

The docs portal uses a distinct section with anchor `broray-light` in the existing deployed `broray/index.html`. This is the safe form of the user-authorized “new section or page” because the installed production deployer has a fixed allowlist and cannot publish a new path without server mutation.

The guide must cover requirements, verified installation, login, initial setup, Home, Servers, Subscriptions, auto-refresh, duplicate handling, failover, Keenetic interface, Xray update/reinstall, Light update, diagnostics, persistence, removal, security, support, and license.

## Acceptance gates

1. Active BROray-Light branch and canonical R0011 inputs are exact.
2. R0012 start checkpoint and contract are complete and hashed.
3. The WebUI guide removal is surgical; three-page navigation, IDs, controls, endpoints, native authentication, and responsive layout pass.
4. README and companion guide are complete, contain no secrets, and reference the final `1.0.0-r3` release and exact verified installation artifacts.
5. The external docs section is complete, styled by the existing site system, reachable by anchor, responsive, and does not alter the docs homepage content.
6. The GitHub default branch changes only `README.md` and `docs/USER-GUIDE-RU.md` from its audited base.
7. The docs-site repository changes only the permitted deployed guide file and checksum manifest from its audited base.
8. Version, tag, cache token, URLs, manifests, and policy IDs are exactly `1.0.0-r3`, `v1.0.0-r3`, and `1.0.0-r3-r0012` as applicable.
9. Static syntax, forbidden-feature, authentication, archive-safety, lifecycle, and all WebUI functional button/endpoint tests pass.
10. Build A and independent Build B are byte-identical and all SHA-256 manifests verify.
11. Isolated-root clean install, r2→r3 update, equal-version no-op, downgrade refusal, rollback, persistence, and Xray checks pass.
12. `release.json` is signed with the existing encrypted GitHub Actions signing secret and verifies against the existing public key; no plaintext key is retained.
13. Exact release-source commit is pushed and immutable tag `v1.0.0-r3` targets it.
14. Public release is latest, non-draft, non-prerelease, complete, and byte-verified.
15. The authorized physical router runs the exact public r3 package; services, Xray, user persistence, authentication, and the absence of the embedded guide pass.
16. The public GitHub root and docs portal section are fetched independently and match their sealed content/checksums.
17. R0012 checkpoint, report, validation, worklog, state, and aggregate hashes pass final audit.

`candidateReady` and `releaseReady` remain false until all required pre-publication gates pass. `publicReleasePublished` remains false until the immutable public release exists and its bytes verify.

## FIRST-ERROR

At the first material failure, stop that revision. Save a separate JSON record under `checkpoints/R0012/process-failures/`, add its SHA-256 sidecar, update `project/R0012-STATE.json`, append `project/WORKLOG.jsonl`, and continue only under a named corrected revision.
