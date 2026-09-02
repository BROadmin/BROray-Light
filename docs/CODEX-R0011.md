# CODEX R0011 — Russian guide on GitHub and WebUI Home

## Objective

Publish a complete Russian BROray-Light user guide in the GitHub repository and in a collapsible full-width section on the WebUI Home page, then deliver and validate the documentation update as the next immutable Stable revision.

Stage identifier:

`PUBLISH_RUSSIAN_GUIDE_AND_WEBUI_HOME_DOCUMENTATION_STABLE_1.0.0_R2`

Public version, package version, candidate ID, and release ID:

`1.0.0-r2`

Git tag:

`v1.0.0-r2`

Web asset cache token:

`1.0.0-r2-r0011`

## Canonical inputs

- R0010 evidence commit: `b21078406e950c3c32b63ecbe44787d4608978e7`
- R0010 release-source commit: `9e5fce9bfa7c82bfc2f2654d80fd3987c5259963`
- R0010 checkpoint SHA-256: `82d740011bd95cce3b97e893fefd4e397863a89e72d7dfe1959a536baaf8ddee`
- Existing immutable Stable: `1.0.0-r1`, tag `v1.0.0-r1`
- Canonical R0008 source commit remains `684b27bdb53e545047419baa87c63dd86dffa469`
- Full BROray documentation reference audit: `checkpoints/R0011/REFERENCE-AUDIT-P6.json`

## Publication authorization and boundaries

The user's request explicitly requires the instruction on GitHub and on the live site. R0011 is therefore authorized to update this repository, publish the new immutable `v1.0.0-r2` Stable release needed to deliver the WebUI bytes, and update the already authorized physical test router through the verified package/updater path.

R0011 must not overwrite or delete `v1.0.0-r1`, mutate `BROadmin/BROray`, change a production server, or expose credentials or signing material. The existing minisign trust root must be preserved. Release signing may use only the encrypted GitHub Actions secret `BRORAY_LIGHT_MINISIGN_PRIVATE_KEY`; its value must never be read or printed.

## Documentation scope

The GitHub documentation and the Home guide must cover:

1. what BROray-Light is and how it differs from full BROray;
2. Keenetic/Entware/architecture and package prerequisites;
3. verified clean installation and first login;
4. Home, Servers, and Subscriptions workflows;
5. naming, adding, updating, scheduling, and deleting subscriptions;
6. duplicate VLESS identity handling across manual and subscription imports;
7. server check, activation, ordering, deletion, and active-server restriction;
8. automatic server failover states and settings;
9. Keenetic managed proxy interface state and actions;
10. Xray update and same-version reinstall;
11. BROray-Light Stable update behavior;
12. diagnostics, security, persistence, removal, support, and license.

The embedded instruction must remain part of Home, not become a fourth functional WebUI page. It must be keyboard accessible, readable on desktop and mobile, and follow the current BROray visual system.

## Product invariants

- VLESS only.
- Exactly three functional WebUI pages: Home, Servers, Subscriptions.
- No Routes.
- No DNS-over-TLS management.
- No ratings, quality history, or scheduled quality refresh.
- Native Keenetic authentication and session protection remain unchanged.
- Deterministic failover, subscription auto-refresh, updater safety semantics, Xray ownership, and fail-closed full-product co-ownership remain unchanged.

## Acceptance gates

1. Active branch and all canonical R0010/R0008 inputs are verified.
2. Full BROray documentation is read-only audited and the Light inclusion/exclusion map is sealed.
3. The Russian GitHub guide is complete, internally consistent, and contains no secrets.
4. The Home guide contains all required topics without adding a functional page or API.
5. The Home guide is accessible, responsive, visually consistent, and its copy controls work.
6. Version, release ID, package version, tag, URLs, and cache token are exactly `1.0.0-r2`, `v1.0.0-r2`, and `1.0.0-r2-r0011` as applicable.
7. Existing WebUI controls and endpoint bindings remain covered and pass; documentation controls have explicit tests.
8. Static syntax, archive safety, forbidden-feature, authentication, and package lifecycle checks pass.
9. Build A and independent Build B are byte-identical for every artifact and all SHA-256 manifests verify.
10. Isolated-root clean install, update from r1, equal-version, downgrade refusal, rollback, persistence, and Xray checks pass.
11. `release.json` is signed by the existing public key using only the encrypted GitHub Actions secret; plaintext private material is absent.
12. Exact release-source commit is pushed and immutable tag `v1.0.0-r2` targets it.
13. The public GitHub release is latest, non-draft, non-prerelease, complete, and byte-verified.
14. The authorized physical router runs the exact public r2 package; services, Xray, persistence, authenticated WebUI, and live documentation pass.
15. R0011 checkpoint, validation, report, worklog, state, and aggregate SHA-256 records pass a final audit.

`candidateReady`, `releaseReady`, and `publicReleasePublished` remain false until all 15 gates pass.

## FIRST-ERROR policy

At the first material failure, stop that revision. Save a standalone JSON record under `checkpoints/R0011/process-failures/`, add its SHA-256 sidecar, update `project/R0011-STATE.json`, append `project/WORKLOG.jsonl`, and continue only under a named corrected revision.
