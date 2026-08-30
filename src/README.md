# Source build gate

BROray-Light source must be built from the exact verified BROray Stable donor set, not from an assumed-equivalent upstream development tree.

Current verified donor:

```text
releaseId=3.0.0-r20
candidateId=3.0.0-r20c01
applicationSha256=ad231c899e0a93f90f65489b8b6588aa09ae94b43c1d838e13e4458079c862bd
```

Preparation R0006 classified all 284 exact application files into `RETAIN`, `PORT`, `ADAPT`, `REPLACE`, or `DROP`. The next allowed stage is to construct the Light source tree from that treatment map. Current upstream `BROadmin/BROray` `main` must not be substituted for the exact Stable application bytes.
