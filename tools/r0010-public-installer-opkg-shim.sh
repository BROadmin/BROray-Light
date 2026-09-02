#!/opt/bin/ash

set -eu

[ "$#" -eq 2 ] && [ "$1" = install ] || {
    echo 'isolated opkg shim accepts only: opkg install PACKAGE' >&2
    exit 64
}

PACKAGE="$2"
WORK=/tmp/opkg-work
[ -f "$PACKAGE" ] || {
    echo 'isolated opkg shim package is absent' >&2
    exit 65
}
[ ! -e "$WORK" ] || {
    echo 'isolated opkg shim work directory is not clean' >&2
    exit 66
}

mkdir -p "$WORK/control"
tar -xzf "$PACKAGE" -C "$WORK"
[ "$(sed -n '1p' "$WORK/debian-binary")" = '2.0' ] || {
    echo 'isolated opkg shim package format marker is invalid' >&2
    exit 67
}
[ -f "$WORK/control.tar.gz" ] && [ -f "$WORK/data.tar.gz" ] || {
    echo 'isolated opkg shim package carrier is incomplete' >&2
    exit 68
}

tar -xzf "$WORK/control.tar.gz" -C "$WORK/control"
/opt/bin/ash "$WORK/control/preinst"
tar -xzf "$WORK/data.tar.gz" -C /
BRORAY_LIGHT_SKIP_SERVICE_START=1 /opt/bin/ash "$WORK/control/postinst"

exit 0
