# R0013 — selective update from current BROray Stable

The user authorized a BROray-Light update based on changes in current BROray, followed by implementation and release. This supersedes the mistaken automatic resumption of R0012/r4. Base the application on validated Light Stable `1.0.0-r1` (commit `9e5fce9bfa7c82bfc2f2654d80fd3987c5259963`), preserve canonical R0008 `src/`, and port only applicable changes from the exact published BROray `3.1.0-r09c02` archive. The GitHub release tag points to documentation, not the packaged runtime source. Pin both tag and archive provenance.

Keep branch `codex/r0009-updater-package`. Preserve all existing R0012 work, its hashes, and failed revisions; do not inherit it into a release automatically. Use a separate R0013 overlay and assemble accepted baseline inputs from the r1 Git objects. The user explicitly selected version `2.0.0` and immutable tag `v2.0.0` on 2026-09-10. Do not add an r-suffix or publish before acceptance.

Retain VLESS only; Home, Servers, Subscriptions; deterministic failover; native authentication and sessions; exact ownership and fail-closed co-install policy; signed Light updater, version ordering, equal-version no-op, atomic switch and rollback. Exclude Routes, DoT management, rankings, quality history and scheduled quality refresh. Adapt Xray controls to Home. Upstream compatibility evidence is evidence for BROray, not a Light PASS; validate the port independently.

All operational scratch on the router belongs in protected RAM paths. Keep installed runtime and user state durable. Any carried storage fix must be bounded, tested and explicitly included in the manifest.

Required gates: pinned donor and r1 identities; mapped upstream changes; BusyBox syntax; functional regression including every WebUI button/API; native authentication; archive and updater safety; isolated clean install, r1 update, equal version, downgrade refusal, rollback and persistence; independent Build A/B and hashes; existing signing trust root through encrypted Actions secret; authorized target validation; final immutable release and documentation byte checks. Existing R0010 acceptance tests are historical regression inputs, not proof for new bytes.

CHECKPOINT-FIRST and FIRST-ERROR apply under `checkpoints/R0013/`. Stop each failed validation revision, record a material failure as a separate JSON with SHA-256, diagnose, and use a named corrected revision. Update `project/R0013-STATE.json` and append `project/WORKLOG.jsonl` after meaningful stages. Keep readiness false until required gates pass.
