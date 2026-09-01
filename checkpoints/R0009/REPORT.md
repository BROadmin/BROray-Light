# R0009 completion report

R0009 is **PASS**. Internal installable candidate `0.1.0-r0009c19` was produced from immutable R0008 source commit `684b27bdb53e545047419baa87c63dd86dffa469`, reproduced independently, installed and validated on the authorized Keenetic router, and not publicly published.

## Candidate and reproducibility

- Build A: `dist/R0009/R0009c19-P306-Build-A`
- Build B: `dist/R0009/R0009c19-P306-Build-B`
- Result: 8/8 artifacts byte-identical; both minisign verifications PASS.
- IPK: `bf73974e6aff89d6b43872d5ff62433b4748a4486db2f83d20b3337a23ca7b51`
- App archive: `d332fd192fab7826c7729c719a5e5a8d3708daec24c6a0832a6f3dbf06c5ef55`
- Updater archive: `c029afef72111d766eaa302d48fcfaa182ace542abecd036ee232f65be3a7985`
- Installer: `75fa590fe697ee8938a29fc402b63c91bb4d8609db3e8514889240aa8f2fecf1`
- Candidate manifest: `41a2889f038ce5563e58116e805980ce6284122c407bd09dfcb5118f10d1cff7`
- Release index: `607cc129389904da603467406f65085aa46a8658be80f4482df1df3761e942a0`
- Release signature: `6e5529132dfb26002ae689a5a69544ff8ca2f6671f810664fa6d922ef72f4830`
- Artifact sums: `f1b7b84c55cb334e3763f1cf53dc3db14e8f4d9b7628cb6dcf303459d93b4ac0`

## Validation

The c19 isolated-root suite passed 44/44 gates, including clean install, signed update, equal-version no-op, downgrade refusal, rollback, persistence, fail-closed ownership, global deduplication, UI contracts, Xray reinstall exposure, HTML no-store/versioned navigation, and receipt-owned migration from the prior HTML-only cache rule.

Authorized physical validation passed:

- installed package `broray-light 0.1.0-r0009c19`; primary and updater services healthy;
- six servers and two subscriptions persisted with zero duplicate identity/import groups;
- active server and exact Xray runtime persisted; equal-version Xray `26.7.28` reinstall completed and retained SHA-256 `4b8af237444801bf17b3dc10a1c5c24581fbe3d433eba3d78c6c3a0da1df56fc`;
- root and `.html` responses both return `Cache-Control: no-store, no-cache, must-revalidate` and `Pragma: no-cache`;
- authenticated c19 navigation loads only versioned CSS/JS/HTML paths;
- circular logo, green card labels, spacing, six server check results, boundary arrows and explanatory statuses render correctly;
- failover toggle and order dirty-state revert correctly; save succeeds with disabled failover semantics preserved;
- invalid VLESS is rejected, server check returns HTTP 204 with a new timestamp, subscription refresh succeeds and server counts are visible;
- BROray-Light reports the internal R0009 channel without claiming a public update channel;
- temporary transfer IPKs were removed after installation; no user data was removed;
- full BROray ownership is zero, routes via `Proxy0` are zero, and recovery marker is absent.

All 158 material failed revisions are preserved as JSON with SHA-256 sidecars. Final browser diagnostics confirm the requested green `rgb(78, 214, 157)` color for the subscription label and all five home card labels; blue rectangles in annotated screenshots are browser selection markers. The signing private key was never committed or transferred and is destroyed. The c19 public verification key SHA-256 is `9421289636a6a307a8ab874f2d680d249ec221a5d66506ce1ac8eabcebd99826`.

## Completion

All 20 R0009 acceptance gates PASS. `candidateReady=true` means ready as the first internal installable candidate; it does not authorize Stable publication.

Exact next stage: `DEFINE_AND_AUTHORIZE_R0010_BEFORE_ANY_STABLE_PUBLICATION`.
