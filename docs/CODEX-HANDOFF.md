# Codex handoff

## Current state

- Branch: `codex/r0009-updater-package`
- R0009 status: **PASS**
- Candidate: `0.1.0-r0009c08`
- Release ID: `0.1.0-r9`
- `candidateReady=true`
- Public release: not published
- Production server: not modified
- Ephemeral private signing key: destroyed

Canonical R0008 source commit `684b27bdb53e545047419baa87c63dd86dffa469` remains unchanged: 121 files, 627326 logical bytes, `src/SHA256SUMS` SHA-256 `e056585d6a517ddbbbaebf08b68f17eb2d9d7ccd68d86df5cdee9fd4665f2419`.

## Final evidence

- Checkpoint: `checkpoints/R0009/CHECKPOINT.json`
- Checkpoint SHA-256: `6aa1056a8f41ec59773787b565dd5c97bec2ec6db5181f1c5648e9e680791086`
- Validation: `checkpoints/R0009/VALIDATION.json`
- Validation SHA-256: `3431e69863eafc0a565de82b7d5254fe49fb4b04d0b0cbf4a597c6d9061440ea`
- Report: `checkpoints/R0009/REPORT.md`
- Build A/B: `dist/R0009/R0009c08-Build-A`, `dist/R0009/R0009c08-Build-B`
- Reproducibility: 8/8 byte-identical
- Isolated-root validation: 27/27 PASS
- Physical postboot validation: `checkpoints/R0009/physical-validation/POSTBOOT-P114-C08-AUTOSTART-WEB-AUTH-PERSISTENCE.json`
- Public validation URL: `https://brolight.tvervip.keenetic.link/`

The router ends with `broray-light 0.1.0-r0009c08`, `current -> releases/0.1.0-r9`, automatic service and publication startup PASS, persistence PASS, full BROray ownership zero, and Proxy0 routes zero.

## Exact next stage

`DEFINE_AND_AUTHORIZE_R0010_BEFORE_ANY_STABLE_PUBLICATION`

Stop here unless that stage is explicitly defined and authorized. Do not publish Stable or mutate a production server under the R0009 authorization.
