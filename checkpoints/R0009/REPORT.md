# R0009 completion report

R0009 is **PASS**. Internal installable candidate `0.1.0-r0009c14` passed engineering, isolated-root, final local audit and authorized physical validation. It was built from immutable R0008 source commit `684b27bdb53e545047419baa87c63dd86dffa469`, reproduced independently, installed on the Keenetic router, visually validated against the BROray reference, and not publicly published.

## Candidate and reproducibility

- Build A: `dist/R0009/R0009c14-P231-Build-A`
- Build B: `dist/R0009/R0009c14-P231-Build-B`
- Result: 8/8 artifacts byte-identical; both `SHA256SUMS` and both minisign verifications PASS.
- IPK SHA-256: `43c7ddbb59e3cb68c68f9e280f2859b0ed6170d4ad5fb1f6f108d2010c0ca6ee`
- App archive SHA-256: `d058cabb9cfb150bf6526ecf5129fc0840226756bb728d3d6f49473e5e5e18c6`
- Updater archive SHA-256: `6af6609808b086c09705a21f67002e873f12b548f8be33beb9e39924d16e35e6`
- Installer SHA-256: `a9ffbed45d080648696ca73a32e62572889634eb097230005b829ecde76d903d`
- Candidate manifest SHA-256: `98057e449d0d5cd9cde3a05e1ce324b64e7de5b3fe81ba23345a38c6fcf6b1fb`
- Release index SHA-256: `284c7450fad06e22f0165ce96a44388d4aa8cd438d6783c2c424b8f6e95647a3`
- Release signature SHA-256: `c9d06c899c6280aabc12694591c5119eb487f0f69e85893876dbe2fdf6227509`
- Artifact sums SHA-256: `fa7ecde34f9485dfeee81897bedba01f560f319ca3af5df65c59959783d465c5`
- Canonical R0008 application bytes remain unchanged: 121 files, 627326 logical bytes, `src/SHA256SUMS` SHA-256 `e056585d6a517ddbbbaebf08b68f17eb2d9d7ccd68d86df5cdee9fd4665f2419`.

## Validation

The c14 isolated-root suite passed 36/36 gates: the previous 33 clean-install, updater, rollback, persistence and safety gates plus Keenetic CLI dispatch, equal-version Xray reinstall exposure, and global server deduplication with active/manual priority, backup, stale-order cleanup and idempotence.

The authorized physical validation passed package install, signed r8-to-r9 update, equal-version no-op, downgrade refusal, forced rollback, persistence, native reboot, automatic startup, native KeenDNS publication and authentication. After reboot:

- installed package: `broray-light 0.1.0-r0009c14`;
- current slot: `releases/0.1.0-r9`;
- primary, updater and publication status: PASS;
- public URL: `https://brolight.tvervip.keenetic.link/`;
- local and external unauthenticated status tuple: `200,200,401`;
- final authenticated API lifecycle: all login, summary, info, subscriptions, activation, Xray and logout calls `200`; post-logout protected request `401`;
- external pages: BROray blue-black/slate/teal palette, separated sections, 24 px action top margin, 6 px bottom margin and no text/button collisions PASS;
- versioned c14 CSS/JS URLs prevent stale assets after package upgrade;
- active server, two subscriptions, Xray `26.7.28`, BROray-Light `0.1.0-r9`, Keenetic `Готов` and connection state are visible;
- Xray `26.7.28` was safely reinstalled at the same version through the new UI/API path and retained its exact SHA-256;
- BROray-Light has an explicit update-check button and reports that the internal R0009 public channel is not configured;
- disabled auto-switch now renders `Выключено` with an explanation instead of ambiguous `Ожидание`;
- 11 overlapping subscription records were reconciled to 6 unique servers; 5 removed files are preserved in the app-owned backup, the active server remained present, and stale auto-switch references are zero;
- Xray SHA-256 remains `4b8af237444801bf17b3dc10a1c5c24581fbe3d433eba3d78c6c3a0da1df56fc`;
- config, servers, subscriptions, Xray, Lighttpd config and publication receipt persisted;
- full BROray ownership is zero and routes via `Proxy0` are zero.

All 123 material failed revisions are preserved as JSON checkpoints with SHA-256 sidecars. The ephemeral private signing key was not placed in the repository or transferred to the router and has been destroyed. The c14 public verification key SHA-256 is `79b436e96c19d9e268addfc0c780f34e1676d90b764d7fcd21a8327508063f7b`.

## Completion

All 20 recorded R0009 and authorized extension acceptance gates are PASS. `candidateReady=true` means ready as the first internal installable candidate; it does not authorize Stable publication.

Exact next stage: `DEFINE_AND_AUTHORIZE_R0010_BEFORE_ANY_STABLE_PUBLICATION`.
