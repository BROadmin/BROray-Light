# BROray-Light R0008 — first independent source tree

`STATUS=PASS`

Base: BROray Stable `3.0.0-r23`, exact candidate `3.0.0-r23c02` application SHA-256 `69679f6d7339b856faf28f69cb1800254984e5400201fe97247011ab166c3f85`.

R0008 creates an independent Light source tree instead of hiding full BROray features. The generated tree has 121 files and 627326 bytes. Treatment execution covers all 287 donor files: all 156 DROP files are absent; all 7 RETAIN and 11 PORT files are present; ADAPT/REPLACE were either retained/adapted or dependency-pruned.

Validation: checksum 120/120, ash 79/79, JS 7/7, JSON 16/16, internal dependencies 64/64, expected WebUI APIs 29/29. Functional smokes pass for VLESS transports, duplicate rejection, subscription stable sync/fail-closed conflict, deterministic failover, r23 Keenetic ownership, one-service clean start, and forced post-activation rollback.

The builder reproduces the implementation byte-for-byte (119/119 implementation files). This stage does not include the Light updater or installable package and is not a release candidate.

Codex continuation is defined by `CODEX-HANDOFF.md`, `INVARIANTS.json`, and append-only `WORKLOG.jsonl`.
