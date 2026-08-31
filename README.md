# BROray-Light

BROray-Light is a separate lightweight VLESS-only edition for Keenetic.

## Current implementation checkpoint

`R0008` is the first independent Light source tree built from exact BROray Stable `3.0.0-r23` / `r23c02` bytes. It is **not yet an installable release candidate**.

- functional pages: Home, Servers, Subscriptions;
- VLESS only;
- deterministic automatic failover without ratings/history;
- Keenetic managed proxy control on Home;
- one primary application service: `S24broray-light`;
- Light updater/installable package is the next stage.

For continuation, read **`docs/CODEX-HANDOFF.md` first**, then `project/INVARIANTS.json`, `project/IMPLEMENTATION-STATE.json`, and `project/WORKLOG.jsonl`.

Exact donor identity and R0007 preparation evidence remain in the repository.
