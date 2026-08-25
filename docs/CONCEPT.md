# BROray-Light — canonical concept

## 1. Home

Home contains four compact functional areas.

### Active server

- active server name;
- address and port;
- VLESS connection type;
- Xray process state;
- connection state;
- last check time;
- link to Servers.

### Automatic server switching

- enabled/disabled;
- current check status;
- consecutive failure counter;
- last failover target;
- enable/disable control.

Failover uses deterministic server order. It does not calculate a score or preserve quality history. Before activation the generated Xray configuration must be validated; after activation the real connection must be checked; failed activation must safely roll back.

### Keenetic

Managed from Home with no dedicated page:

- managed proxy-interface presence;
- Xray endpoint used by the interface;
- actual interface state;
- expected-vs-actual configuration state;
- Configure when missing;
- Repair when managed state differs;
- Refresh state.

Destructive Proxy0 removal is not exposed on Home.

### Updates

Two compact blocks:

- Xray: installed version, available version, check, update;
- BROray-Light: installed version, available version, check, update.

Both use one updater implementation.

## 2. Servers

VLESS only.

Supported user actions:

- import VLESS URI;
- inspect parsed parameters read-only;
- check server;
- activate server;
- rename display name;
- delete server;
- reorder servers;
- include/exclude server from automatic failover.

No complex field-by-field editor is provided. UUID, Reality parameters, SNI, fingerprint, flow, transport and related fields are parsed from the imported VLESS URI and shown read-only where useful.

## 3. Subscriptions

Supported user actions:

- add subscription URL;
- update subscription;
- list received servers;
- import VLESS servers;
- delete subscription;
- show last successful update;
- show last update error.

Non-VLESS entries are skipped without failing the complete subscription update. Duplicate protection remains mandatory.

## Runtime simplification

One BROray-Light application-control service owns:

- Xray supervision logic used by BROray-Light;
- active connection checks;
- automatic failover;
- operation locking/serialization;
- compact state snapshots for WebUI;
- Keenetic managed-interface operations;
- updater invocation.

Reliability mechanisms are not optional simplifications. Atomic file replacement, concurrency locks, Xray configuration validation, safe rollback, duplicate protection and state preservation remain required.
