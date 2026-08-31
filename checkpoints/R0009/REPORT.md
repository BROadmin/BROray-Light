# R0009 completion report

R0009 is **PASS**. Internal installable candidate `0.1.0-r0009c08` was built from immutable R0008 source commit `684b27bdb53e545047419baa87c63dd86dffa469`, reproduced independently, validated in isolated roots, installed on the separately authorized Keenetic router, and not publicly published.

## Candidate and reproducibility

- Build A: `dist/R0009/R0009c08-Build-A`
- Build B: `dist/R0009/R0009c08-Build-B`
- Result: 8/8 artifacts byte-identical; both `SHA256SUMS` and both minisign verifications PASS.
- IPK SHA-256: `efc3fc67e792f1a783894a977b1c2abfa059d002e720ca9574bfe3ef6295c573`
- App archive SHA-256: `ca5ec62c0d6419e8ef0e2284c7bf8465d01baeea4bef0d37172cd640de453434`
- Updater archive SHA-256: `3d06380f85849e1d267473e9970ce48e4cadf6eb042b4245c1f2289b39dd8224`
- Installer SHA-256: `e2de68a19d5f94315d374c1266d043c467d979fefdbde8de4cd0bec093416ae0`
- Candidate manifest SHA-256: `eabb5ef2aa85114a95862e2151e7919c23a08cb6d1d283dd2b31bb1347f78340`
- Canonical R0008 application bytes remain unchanged: 121 files, 627326 logical bytes, `src/SHA256SUMS` SHA-256 `e056585d6a517ddbbbaebf08b68f17eb2d9d7ccd68d86df5cdee9fd4665f2419`.

## Validation

The c08 isolated-root suite passed 27/27 gates: clean install, safe installer rerun, exact Xray bootstrap, signed update, equal-version no-op, downgrade refusal, checksum and malicious archive rejection, request/global locks, atomic slot switch, forced health rollback, persistence, exact foreign-state ownership, transient boot retry and permanent-failure fail-closed behavior.

The authorized physical validation passed package install, signed r8-to-r9 update, equal-version no-op, downgrade refusal, forced rollback, persistence, native reboot, automatic startup, native KeenDNS publication and authentication. After reboot:

- installed package: `broray-light 0.1.0-r0009c08`;
- current slot: `releases/0.1.0-r9`;
- primary, updater and publication status: PASS;
- public URL: `https://brolight.tvervip.keenetic.link/`;
- local and external unauthenticated status tuple: `200,200,401`;
- login/session/protected/logout/post-logout tuple: `200,200,200,200,401`;
- zero session files after logout;
- Xray SHA-256 remains `4b8af237444801bf17b3dc10a1c5c24581fbe3d433eba3d78c6c3a0da1df56fc`;
- config, servers, subscriptions, Xray, Lighttpd config and publication receipt persisted;
- full BROray ownership is zero and routes via `Proxy0` are zero.

All material failed revisions are preserved as 64 JSON checkpoints with SHA-256 sidecars. Two enumerated trailing-empty-line warnings are retained because those exact shell bytes are already bound into the reproducible c08 IPK; both files pass `dash -n`. The ephemeral private signing key was not placed in the repository or transferred to the router and has been destroyed. The canonical LF public key SHA-256 is `8ed24e39ac0934947bc85f4a81dccb5dd28b44e9eeee0a26fe3ab80f37cc0aa8`.

## Completion

All 20 recorded R0009 and authorized extension acceptance gates are PASS. `candidateReady=true` means ready as the first internal installable candidate; it does not authorize Stable publication.

Exact next stage: `DEFINE_AND_AUTHORIZE_R0010_BEFORE_ANY_STABLE_PUBLICATION`.
