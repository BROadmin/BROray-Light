# BROray-Light remote bootstrap — R0002

## Result before post-commit verification

`PASS_PENDING_POST_COMMIT_VERIFICATION`

The empty public repository `BROadmin/BROray-Light` exists and the connected GitHub identity has admin/push access. The repository is being populated with the approved BROray-Light scope and an immutable upstream Stable pin.

No changes are made to `BROadmin/BROray`, any production server, or any router.

## Upstream donor gate

The donor remains BROray Stable `3.0.0-r14`, technical candidate `r14c68`.

Application archive SHA-256:

`314be910e180d5bbac4677a9483e17f18406c8a4339a849edb2c1c8d7de4e382`

Current upstream `main` is not accepted as a byte-exact Stable donor. Application source import remains blocked until exact `r14c68` release-source bytes are obtained and verified.

## Light scope

- VLESS only;
- Home, Servers, Subscriptions only;
- automatic failover retained;
- no ratings or quality history;
- Keenetic managed-interface control on Home;
- no complex server editor;
- no separate system pages;
- no manual Xray maintenance UI;
- no WebUI remove/restore flow;
- one brand theme;
- one updater;
- one primary BROray-Light control service.
