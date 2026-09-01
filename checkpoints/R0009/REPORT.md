# R0009 completion report

R0009 is **PASS**. Internal installable candidate `0.1.0-r0009c13` was built from immutable R0008 source commit `684b27bdb53e545047419baa87c63dd86dffa469`, reproduced independently, validated in isolated roots, installed on the separately authorized Keenetic router, visually validated against the BROray reference, and not publicly published.

## Candidate and reproducibility

- Build A: `dist/R0009/R0009c13-Build-A`
- Build B: `dist/R0009/R0009c13-Build-B`
- Result: 8/8 artifacts byte-identical; both `SHA256SUMS` and both minisign verifications PASS.
- IPK SHA-256: `18136b993f2f153f33b2932c9fee50c167f3b16e2cbd44ac9137612e27cc86d2`
- App archive SHA-256: `ef3dc465de59946798243ac7c6a7c27a4818f6c90db98133eb3c47fe43c61065`
- Updater archive SHA-256: `4235d3f6ab5b2305920ec2ad16bfb077f82d0c72b454e0d7ded32c85530765ea`
- Installer SHA-256: `482db129e12de9156ca21a17981b2d1ebcc4f3de458992886735fcc0a74deecf`
- Candidate manifest SHA-256: `e8b07f6d9437745f3584da20d29c08c08fca82ef5320f0e6b675144eebcd47aa`
- Release index SHA-256: `9427a0f09c48d93b436cf070d3e0270e321ec98979f4a7386bc1b737fe6dc99a`
- Release signature SHA-256: `0f1ebbd2fb24f04d7104ce177026583535d3b440e7bbe4c6c755c84f8569d1dd`
- Artifact sums SHA-256: `9f5750907b53f8d9315de8093ded7f821ef013dfc5becefe3175f05b6e6b3b87`
- Canonical R0008 application bytes remain unchanged: 121 files, 627326 logical bytes, `src/SHA256SUMS` SHA-256 `e056585d6a517ddbbbaebf08b68f17eb2d9d7ccd68d86df5cdee9fd4665f2419`.

## Validation

The c13 isolated-root suite passed 33/33 gates: clean install, safe installer rerun, exact Xray bootstrap, signed update, equal-version no-op, downgrade refusal, checksum and malicious archive rejection, request/global locks, atomic slot switch, forced health rollback, persistence, exact foreign-state ownership, transient boot retry, permanent-failure fail-closed behavior, JSON-only activation, exact corrective overlay, displayed identity, named subscriptions, BROray theme and Xray update-check backend.

The authorized physical validation passed package install, signed r8-to-r9 update, equal-version no-op, downgrade refusal, forced rollback, persistence, native reboot, automatic startup, native KeenDNS publication and authentication. After reboot:

- installed package: `broray-light 0.1.0-r0009c13`;
- current slot: `releases/0.1.0-r9`;
- primary, updater and publication status: PASS;
- public URL: `https://brolight.tvervip.keenetic.link/`;
- local and external unauthenticated status tuple: `200,200,401`;
- final authenticated API lifecycle: all login, summary, info, subscriptions, activation, Xray and logout calls `200`; post-logout protected request `401`;
- external login page: BROray blue-black/slate/teal palette, 430 px centered card, Arial Cyrillic typography, 34 px padding, inline eye control and full-width submit PASS;
- versioned CSS/JS URLs prevent stale UI after package upgrade;
- active server name, two named subscriptions, Xray `26.7.28` and BROray-Light `0.1.0-r9` are visible through the API/UI contract;
- zero session files after logout;
- Xray SHA-256 remains `4b8af237444801bf17b3dc10a1c5c24581fbe3d433eba3d78c6c3a0da1df56fc`;
- config, servers, subscriptions, Xray, Lighttpd config and publication receipt persisted;
- full BROray ownership is zero and routes via `Proxy0` are zero.

All 104 material failed revisions are preserved as JSON checkpoints with SHA-256 sidecars. The ephemeral private signing key was not placed in the repository or transferred to the router and has been destroyed. The final public verification key SHA-256 is `401aad9c433c6c81b24412508774ae467a4c11a5752d2c6c0b286ae39079a93f`.

## Completion

All 20 recorded R0009 and authorized extension acceptance gates are PASS. `candidateReady=true` means ready as the first internal installable candidate; it does not authorize Stable publication.

Exact next stage: `DEFINE_AND_AUTHORIZE_R0010_BEFORE_ANY_STABLE_PUBLICATION`.
