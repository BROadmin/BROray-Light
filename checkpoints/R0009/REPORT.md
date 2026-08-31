# R0009 completion report

R0009 is **PASS**. Internal installable candidate `0.1.0-r0009c04` was reproducibly built from immutable R0008 source commit `684b27bdb53e545047419baa87c63dd86dffa469`, installed and validated on the separately authorized Keenetic router, and was not published.

## Candidate and reproducibility

- Build A and Build B are byte-identical for all 8 artifacts.
- The Entware `aarch64-3.10` IPK SHA-256 is `e679d560c21b233a9454ff4e6779237db8056ba906f11550e44a87d3f3d9423b`.
- The app-slot archive SHA-256 is `c156a34ad7b1e2c6b5390114a6fd0d0fad5135c20fa4d23d1a24043c93f3f7de`.
- The isolated-root suite passed 19/19 gates, including clean install, exact Xray, signed update, equal no-op, downgrade refusal, rollback, persistence, lock safety, coownership fail-closed, primary-service PID handoff, and BusyBox-safe atomic symlink replacement.

## Physical validation

The product-authorized full-BROray uninstall completed first and preserved its user-data backup. BROray-Light then passed real package installation, signed r8-to-r9 update, equal-version no-op, downgrade refusal with rc20, forced health rollback, final signed restore, and persistence after a native Keenetic reboot.

The final router state is:

- `broray-light 0.1.0-r0009c04`;
- `current -> releases/0.1.0-r9`;
- updater and primary init status PASS;
- exactly one `broray-lightd` and one Light `lighttpd`;
- HTTP root/home 200 and unauthenticated summary API 401;
- Xray `26.7.28`, 35389566 bytes, SHA-256 `4b8af237444801bf17b3dc10a1c5c24581fbe3d433eba3d78c6c3a0da1df56fc`;
- config, servers, subscriptions, and Xray identities unchanged across update, rollback, final restore, and reboot;
- full BROray package/paths, `Proxy0`, and routes via `Proxy0` all zero.

Two concrete physical-only defects were corrected without changing canonical R0008 application bytes: primary-daemon PID handoff and BusyBox `mv -f` destination-symlink dereference. All material failed revisions remain in `checkpoints/R0009/process-failures/`.

## Acceptance and continuation

All 15 R0009 acceptance gates are PASS and the six physical acceptance checks are PASS. `candidateReady=true` means ready as the first internal installable candidate; it does not authorize Stable publication.

No R0010 stage is defined in the repository. The exact next stage is `DEFINE_AND_AUTHORIZE_R0010_BEFORE_ANY_STABLE_PUBLICATION`.
