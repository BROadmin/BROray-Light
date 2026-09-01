# R0009 finalization report

R0009 is **PASS** and `candidateReady=true` for BROray-Light `1.0.0-r1`. The installable bytes were produced from immutable R0008 source commit `684b27bdb53e545047419baa87c63dd86dffa469`, reproduced independently, installed and fully validated on the separately authorized Keenetic router. Public Stable publication and production-server mutation were not performed.

All 20 acceptance gates passed. The final local audit passed, the ephemeral private signing key was destroyed, and only the public verification key remains.

## Candidate and reproducibility

- Build A: `dist/R0009/1.0.0-r1-P531-Final-Build-A`
- Build B: `dist/R0009/1.0.0-r1-P532-Final-Build-B`
- Result: 8/8 artifacts byte-identical; both minisign signatures and both artifact manifests verify.
- Application archive: `94f9a0a7a7b22f9dd80b8857ba418a5c93f2bfbf39782219e620f499db387531`
- Updater archive: `fb9edededff76248ee58c546deb39b64a2ae134c03f9c125424066703a6ed5e0`
- IPK: `d6add8cd0d27a8e8f29bd3f9c50f2ec889418da0f8e47d93b1a37703c8b6eca6`
- Clean installer: `2b961bbb8b49419166f069f38378c025fb15ae73dd5716cb12f86d436e003c65`
- Release index: `f5179ffdb94c5d50b41c8c188200c6230b49a13b0ec0c76feb700c52fb5e4bea`
- Release signature: `74c6af97367d477bcdb73893272bb17894023da084d315206ce8bd05ce8fd098`
- Candidate manifest: `9a049e1d403c3326dcd06f14aa9bd4562a88ded1d372d9425aea1fe59bf6e7b0`
- Artifact sums: `213a4040a24cd14d108ff077e54ff6e1959c51e7a2760da06f455306697184f9`

## Validation

The exact P531 Build A passed the complete isolated-root suite twice: 51/51 gates, zero failures. The suite covers clean install, safe rerun, signed update, equal-version behavior, downgrade refusal, checksum and malicious-archive rejection, request/global locks, atomic switch, forced rollback, persistence, exact Xray, fail-closed ownership, authentication/presentation contracts, subscription scheduling/deduplication, and server-delete pruning of failover references.

Authorized physical validation passed on the exact P531 package:

- package `broray-light 1.0.0-r1` installed with `current -> releases/1.0.0-r1`;
- primary and updater services healthy; unauthenticated protected API returns HTTP 401;
- Xray `26.7.28` is running at exact SHA-256 `4b8af237444801bf17b3dc10a1c5c24581fbe3d433eba3d78c6c3a0da1df56fc` after a successful equal-version reinstall;
- every login, server, failover, subscription, Keenetic, Xray and BROray-Light update control was exercised, including native confirmations and refusal paths;
- duplicate server identities are suppressed across manual and overlapping subscription imports;
- deletion prunes ordered/excluded failover references atomically;
- WebUI spacing, BROray-aligned colors, mobile cards, visible versions, interface name/status and explanatory state text were verified;
- Light update-check fails closed because no public channel was configured;
- final cleanup leaves zero servers, zero subscriptions, no active server, automatic switching disabled, no owned `Proxy0`, zero routes via `Proxy0`, and zero full-BROray ownership;
- the primary daemon was observed for 35 seconds after cleanup and did not recreate deleted test data;
- no router reboot was performed in the final corrective cycle; the earlier authorized native-reboot automatic-start receipt remains PASS.

All 273 material failed revisions through R315 are retained as machine-readable JSON with SHA-256 sidecars. No supplied credentials or private signing-key material are stored in the repository. Final local audit receipt: `checkpoints/R0009/FINAL-LOCAL-AUDIT-P556-FINAL-1.0.0-R1.json` (`98afd43ecd5362bbb234507efe29d24239852a5e31b30d692645d149da264cb0`). Signing-key destruction receipt: `checkpoints/R0009/SIGNING-KEY-DESTRUCTION-P558-FINAL-1.0.0-R1.json` (`4229c801993258ae3f636d1e4f2acc62295816dce83dd48779465a47fd2673e6`).

## Completion boundary

This is an internal release-ready candidate, not a public Stable publication. Exact next stage: `DEFINE_AND_AUTHORIZE_R0010_BEFORE_ANY_STABLE_PUBLICATION`.
