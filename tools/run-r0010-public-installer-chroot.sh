#!/opt/bin/ash

set -eu

ROOT=/tmp/broray-light-r0010-p96-isolated-root
INPUT=/tmp/broray-light-r0010-p96-input
INSTALLER="$INPUT/broray-light-install-1.0.0-r1.sh"
PACKAGE="$INPUT/broray-light_1.0.0-r1_aarch64-3.10.ipk"
OPKG_SHIM="$INPUT/r0010-public-installer-opkg-shim.sh"
EXPECTED_INSTALLER_SHA256=da8c57ee3b68156462a2dea5cb2f3b6d1706ed754b1cd8904b745ee1fb86c51d
EXPECTED_PACKAGE_SHA256=707431aa20c01958edfe40ed04a70c24308a9dabc9ff26f758101c952827d432
EXPECTED_PACKAGE_SIZE=12799724
EXPECTED_XRAY_SHA256=4b8af237444801bf17b3dc10a1c5c24581fbe3d433eba3d78c6c3a0da1df56fc

fail()
{
    echo "R0010_PUBLIC_INSTALLER_ISOLATED_ERROR:$*" >&2
    exit 1
}

[ "$(id -u)" = 0 ] || fail 'root is required'
[ ! -e "$ROOT" ] || fail 'isolated root is not fresh'
[ -f "$INSTALLER" ] || fail 'public installer input is absent'
[ -f "$PACKAGE" ] || fail 'public package input is absent'
[ -f "$OPKG_SHIM" ] || fail 'isolated opkg shim is absent'
[ "$(sha256sum "$INSTALLER" | awk 'NR==1{print $1}')" = "$EXPECTED_INSTALLER_SHA256" ] || fail 'public installer identity mismatch before chroot'
[ "$(wc -c < "$PACKAGE" | tr -d ' ')" = "$EXPECTED_PACKAGE_SIZE" ] || fail 'public package size mismatch before chroot'
[ "$(sha256sum "$PACKAGE" | awk 'NR==1{print $1}')" = "$EXPECTED_PACKAGE_SHA256" ] || fail 'public package identity mismatch before chroot'

PRODUCTION_CURRENT_BEFORE="$(readlink /opt/broray-light/current)"
PRODUCTION_XRAY_BEFORE="$(sha256sum /opt/broray-light/runtime/xray | awk 'NR==1{print $1}')"

mkdir -p "$ROOT/opt/bin" "$ROOT/opt/lib" "$ROOT/tmp" "$ROOT/dev"
cp -a /opt/lib/. "$ROOT/opt/lib/"
cp /opt/bin/busybox "$ROOT/opt/bin/busybox"
for applet in ar ash awk chmod cp grep head id ln mkdir mv readlink rm sed sha256sum sh tail tar tr wc; do
    ln -s busybox "$ROOT/opt/bin/$applet"
done
ln -s busybox "$ROOT/opt/bin/curl"
cp "$OPKG_SHIM" "$ROOT/opt/bin/opkg"
chmod 755 "$ROOT/opt/bin/opkg"
cp "$INSTALLER" "$ROOT/tmp/install.sh"
cp "$PACKAGE" "$ROOT/tmp/public.ipk"
chmod 755 "$ROOT/tmp/install.sh"
: > "$ROOT/dev/null"

unset BRORAY_LIGHT_ROOT_PREFIX
BRORAY_LIGHT_PACKAGE_FILE=/tmp/public.ipk \
BRORAY_LIGHT_INSTALL_TMP=/tmp/verified-public.ipk \
BRORAY_LIGHT_SKIP_SERVICE_START=1 \
    /opt/sbin/chroot "$ROOT" /opt/bin/ash /tmp/install.sh

[ "$(sha256sum "$ROOT/tmp/install.sh" | awk 'NR==1{print $1}')" = "$EXPECTED_INSTALLER_SHA256" ] || fail 'installer changed inside chroot'
[ "$(sha256sum "$ROOT/tmp/public.ipk" | awk 'NR==1{print $1}')" = "$EXPECTED_PACKAGE_SHA256" ] || fail 'source package changed inside chroot'
[ "$(sha256sum "$ROOT/tmp/verified-public.ipk" | awk 'NR==1{print $1}')" = "$EXPECTED_PACKAGE_SHA256" ] || fail 'installer-published package identity mismatch'
[ "$(sha256sum "$ROOT/opt/broray-light/runtime/xray" | awk 'NR==1{print $1}')" = "$EXPECTED_XRAY_SHA256" ] || fail 'installed Xray identity mismatch'
[ -x "$ROOT/opt/broray-light/runtime/xray" ] || fail 'installed Xray is not executable'
[ "$(readlink "$ROOT/opt/broray-light/current")" = 'releases/1.0.0-r1' ] || fail 'current slot target mismatch'
[ "$(sed -n '1p' "$ROOT/opt/broray-light/config/version")" = '1.0.0-r1' ] || fail 'installed version identity mismatch'
[ -f "$ROOT/opt/broray-light/current/app/web-new/home.html" ] || fail 'installed WebUI is absent'
[ -d "$ROOT/opt/broray-light/run/web-new/sessions" ] || fail 'private WebUI session directory is absent'
[ ! -e "$ROOT/opt/broray" ] || fail 'full BROray ownership appeared inside isolated root'
XRAY_VERSION_LINE="$(/opt/sbin/chroot "$ROOT" /opt/broray-light/runtime/xray version | head -n 1)"
[ -n "$XRAY_VERSION_LINE" ] || fail 'installed Xray did not report a version'

PRODUCTION_CURRENT_AFTER="$(readlink /opt/broray-light/current)"
PRODUCTION_XRAY_AFTER="$(sha256sum /opt/broray-light/runtime/xray | awk 'NR==1{print $1}')"
[ "$PRODUCTION_CURRENT_AFTER" = "$PRODUCTION_CURRENT_BEFORE" ] || fail 'production current slot changed'
[ "$PRODUCTION_XRAY_AFTER" = "$PRODUCTION_XRAY_BEFORE" ] || fail 'production Xray changed'

echo 'RESULT=PASS'
echo "PUBLIC_INSTALLER_SHA256=$EXPECTED_INSTALLER_SHA256"
echo "PUBLIC_PACKAGE_SHA256=$EXPECTED_PACKAGE_SHA256"
echo "PUBLIC_PACKAGE_SIZE=$EXPECTED_PACKAGE_SIZE"
echo "INSTALLED_XRAY_SHA256=$EXPECTED_XRAY_SHA256"
echo "INSTALLED_XRAY_VERSION=$XRAY_VERSION_LINE"
echo 'CURRENT_TARGET=releases/1.0.0-r1'
echo 'INSTALLED_VERSION=1.0.0-r1'
echo 'PUBLIC_PACKAGE_LIFECYCLE=preinst+data+postinst'
echo 'PRODUCTION_STATE_UNCHANGED=true'

rm -rf /tmp/broray-light-r0010-p96-isolated-root
rm -rf /tmp/broray-light-r0010-p96-input
[ ! -e /tmp/broray-light-r0010-p96-isolated-root ] || fail 'isolated root cleanup failed'
[ ! -e /tmp/broray-light-r0010-p96-input ] || fail 'input cleanup failed'
echo 'TEMPORARY_ROOTS_REMOVED=true'

exit 0
