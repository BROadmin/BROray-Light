# Codex handoff

## Current accepted state — R0013 / 2.0.0 published

R0013 is PASS. candidateReady=true, releaseReady=true, publicReleasePublished=true. Immutable tag v2.0.0 resolves to `0d10636e3649726b18c5c90223279edab0bd223d`; exact build/source commit is `f4af30d98fd1f227e5116def825c09399437086f`. Release: https://github.com/BROadmin/BROray-Light/releases/tag/v2.0.0.

Read docs/CODEX-R0013.md, project/R0013-STATE.json, checkpoints/R0013/CHECKPOINT.json and VALIDATION.json. All26 final gates PASS, including20 prepublication gates, independent A/B8of8, six-job511-invocation CI,22 Chromium flows, authorized target tests,11 public assets, both latest aliases, GitHub Russian guide/history and live site.

Test router has Light2.0.0/internal2.0.0-r1, Xray26.9.9(upstream prerelease), active healthy Proxy0 and connected original user server. Six original server IDs and original subscription were preserved; disposable test subscription was removed. Do not clear/reset user data. P113 service restart and durable preservation PASS; P119 real public Stable check equal/no-update PASS. Exact26.2.6 archive remains forbidden after external HTTPS failure; do not use P88 localhost tests to override P89 external evidence.

Final docs: Light main `cf6217f2fdd5f0b55f80211c29f13db28abb42bd`; existing website source `9728483eea1087e9fbd14f23ebb03fa63aaadc94`. Homepage and /broray-light/ live SHA verified. The guide stays on GitHub/site, not in WebUI. Full BROray application and production-server configuration unchanged; only bounded docs source was published through the existing mechanism.

P116 draft-URL validation failure was resolved read-only in P116-V2; no release assets/tag were overwritten. P119 mobile doc-copy layout failure was corrected in site-only P120/P121. Earlier false interface health was a daemon TMPDIR lifetime bug, fixed in final P109 app bytes and fully retested. All failed revisions remain preserved. Historical current-state summaries are archived at checkpoints/R0013/history/P122-BEFORE-SEAL; they are not current instructions or current status.

Keep local branch codex/r0009-updater-package. Preserve all inherited dirty/untracked R0012 work; do not include it in a release. Private off-router backups remain ignored under dist/R0013/private-target and must never be committed. Completed invocation-owned RAM scratch was removed; no router reinstall, restart or service job is in flight.

## Exact next stage

`OPERATE_STABLE_2_0_0_COLLECT_USER_FEEDBACK_AUTHORIZE_NEXT_CHANGE`. User feedback/normal operation. Do not republish immutable v2.0.0, move tags, migrate documentation hosting or change product code without a new scoped request.
