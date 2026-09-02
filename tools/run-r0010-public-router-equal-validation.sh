#!/opt/bin/ash

set -eu

INPUT=/tmp/broray-light-r0010-p106-input
INSTALLER="$INPUT/broray-light-install-1.0.0-r1.sh"
PACKAGE="$INPUT/broray-light_1.0.0-r1_aarch64-3.10.ipk"
TARGET=/tmp/broray-light-r0010-p106-verified.ipk
APP_ROOT=/opt/broray-light
EXPECTED_INSTALLER_SHA256=da8c57ee3b68156462a2dea5cb2f3b6d1706ed754b1cd8904b745ee1fb86c51d
EXPECTED_PACKAGE_SHA256=707431aa20c01958edfe40ed04a70c24308a9dabc9ff26f758101c952827d432
EXPECTED_PACKAGE_SIZE=12799724
EXPECTED_XRAY_SHA256=4b8af237444801bf17b3dc10a1c5c24581fbe3d433eba3d78c6c3a0da1df56fc

fail()
{
    echo "R0010_PUBLIC_ROUTER_EQUAL_ERROR:$*" >&2
    exit 1
}

persistent_file_count()
{
    find "$APP_ROOT/config" "$APP_ROOT/servers" "$APP_ROOT/subscriptions" -type f | wc -l | tr -d ' '
}

persistent_digest()
{
    find "$APP_ROOT/config" "$APP_ROOT/servers" "$APP_ROOT/subscriptions" -type f \
        -exec sha256sum '{}' ';' | sort | sha256sum | awk 'NR==1{print $1}'
}

[ "$(id -u)" = 0 ] || fail 'root is required'
[ -f "$INSTALLER" ] || fail 'public installer input is absent'
[ -f "$PACKAGE" ] || fail 'public package input is absent'
[ ! -e "$TARGET" ] || fail 'verified package target already exists'
[ "$(sha256sum "$INSTALLER" | awk 'NR==1{print $1}')" = "$EXPECTED_INSTALLER_SHA256" ] || fail 'public installer identity mismatch'
[ "$(wc -c < "$PACKAGE" | tr -d ' ')" = "$EXPECTED_PACKAGE_SIZE" ] || fail 'public package size mismatch'
[ "$(sha256sum "$PACKAGE" | awk 'NR==1{print $1}')" = "$EXPECTED_PACKAGE_SHA256" ] || fail 'public package identity mismatch'
[ ! -e /opt/broray ] || fail 'full BROray ownership is present'
[ ! -e /opt/etc/init.d/S24broray ] || fail 'full BROray service ownership is present'
[ "$(readlink "$APP_ROOT/current")" = 'releases/1.0.0-r1' ] || fail 'unexpected current slot before installer'
opkg status broray-light | grep -q '^Version: 1.0.0-r1$' || fail 'installed package version mismatch before installer'

PERSISTENT_FILES_BEFORE="$(persistent_file_count)"
PERSISTENT_SHA256_BEFORE="$(persistent_digest)"
CURRENT_BEFORE="$(readlink "$APP_ROOT/current")"
XRAY_SHA256_BEFORE="$(sha256sum "$APP_ROOT/runtime/xray" | awk 'NR==1{print $1}')"
APP_MANIFEST_SHA256_BEFORE="$(sha256sum "$APP_ROOT/current/APP-SHA256SUMS" | awk 'NR==1{print $1}')"
[ "$XRAY_SHA256_BEFORE" = "$EXPECTED_XRAY_SHA256" ] || fail 'Xray identity mismatch before installer'
(cd "$APP_ROOT/current" && sha256sum -c APP-SHA256SUMS >/dev/null) || fail 'app manifest failed before installer'
/opt/etc/init.d/S24broray-light status || fail 'primary service is unhealthy before installer'
/opt/etc/init.d/S23broray-light-updater status || fail 'updater service is unhealthy before installer'

BRORAY_LIGHT_PACKAGE_FILE="$PACKAGE" BRORAY_LIGHT_INSTALL_TMP="$TARGET" /opt/bin/ash "$INSTALLER"
[ "$(sha256sum "$TARGET" | awk 'NR==1{print $1}')" = "$EXPECTED_PACKAGE_SHA256" ] || fail 'installer-published package identity mismatch'
opkg status broray-light | grep -q '^Version: 1.0.0-r1$' || fail 'installed package version mismatch after installer'

STABLE_CHECK_JSON="$(/opt/bin/broray-light-updaterctl check)" || fail 'Stable update check failed'
printf '%s\n' "$STABLE_CHECK_JSON" | jq -e \
    '.ok == true and .installedReleaseId == "1.0.0-r1" and .availableReleaseId == "1.0.0-r1" and .relation == "equal" and .updateAvailable == false and .downgradeRefused == false and .sameVersionPolicy == "NO_OP_SUCCESS"' \
    >/dev/null || fail 'Stable update check did not report exact equal/no-op semantics'

STABLE_NOOP_JSON="$(/opt/bin/broray-light-updaterctl update)" || fail 'Stable equal-version update command failed'
printf '%s\n' "$STABLE_NOOP_JSON" | jq -e \
    '.ok == true and .installedReleaseId == "1.0.0-r1" and .availableReleaseId == "1.0.0-r1" and .relation == "equal" and .updateAvailable == false and .sameVersionPolicy == "NO_OP_SUCCESS"' \
    >/dev/null || fail 'Stable equal-version update was not an exact successful no-op'

PERSISTENT_FILES_AFTER="$(persistent_file_count)"
PERSISTENT_SHA256_AFTER="$(persistent_digest)"
CURRENT_AFTER="$(readlink "$APP_ROOT/current")"
XRAY_SHA256_AFTER="$(sha256sum "$APP_ROOT/runtime/xray" | awk 'NR==1{print $1}')"
APP_MANIFEST_SHA256_AFTER="$(sha256sum "$APP_ROOT/current/APP-SHA256SUMS" | awk 'NR==1{print $1}')"
[ "$PERSISTENT_FILES_AFTER" = "$PERSISTENT_FILES_BEFORE" ] || fail 'persistent file count changed'
[ "$PERSISTENT_SHA256_AFTER" = "$PERSISTENT_SHA256_BEFORE" ] || fail 'persistent state digest changed'
[ "$CURRENT_AFTER" = "$CURRENT_BEFORE" ] || fail 'current slot changed during equal-version validation'
[ "$XRAY_SHA256_AFTER" = "$XRAY_SHA256_BEFORE" ] || fail 'Xray changed during equal-version validation'
[ "$APP_MANIFEST_SHA256_AFTER" = "$APP_MANIFEST_SHA256_BEFORE" ] || fail 'app manifest identity changed'
(cd "$APP_ROOT/current" && sha256sum -c APP-SHA256SUMS >/dev/null) || fail 'app manifest failed after installer'
/opt/etc/init.d/S24broray-light status || fail 'primary service is unhealthy after installer'
/opt/etc/init.d/S23broray-light-updater status || fail 'updater service is unhealthy after installer'
XRAY_VERSION_LINE="$("$APP_ROOT/runtime/xray" version | head -n 1)"
[ -n "$XRAY_VERSION_LINE" ] || fail 'Xray version output is absent'

PUBLIC_ROOT_STATUS="$(curl -ksS -o /dev/null -w '%{http_code}' 'https://brolight.tvervip.keenetic.link/')" || fail 'public WebUI root request failed'
PROTECTED_API_STATUS="$(curl -ksS -o /dev/null -w '%{http_code}' 'https://brolight.tvervip.keenetic.link/api/home/summary.cgi')" || fail 'protected WebUI API request failed'
[ "$PUBLIC_ROOT_STATUS" = 200 ] || fail 'public WebUI root is unhealthy'
[ "$PROTECTED_API_STATUS" = 401 ] || fail 'native authentication protection is unhealthy'

echo 'RESULT=PASS'
echo "PUBLIC_INSTALLER_SHA256=$EXPECTED_INSTALLER_SHA256"
echo "PUBLIC_PACKAGE_SHA256=$EXPECTED_PACKAGE_SHA256"
echo "PUBLIC_PACKAGE_SIZE=$EXPECTED_PACKAGE_SIZE"
echo 'INSTALLED_PACKAGE=broray-light 1.0.0-r1 aarch64-3.10'
echo "CURRENT_TARGET=$CURRENT_AFTER"
echo "XRAY_SHA256=$XRAY_SHA256_AFTER"
echo "XRAY_VERSION=$XRAY_VERSION_LINE"
echo "APP_MANIFEST_SHA256=$APP_MANIFEST_SHA256_AFTER"
echo "PERSISTENT_FILES=$PERSISTENT_FILES_AFTER"
echo "PERSISTENT_SHA256=$PERSISTENT_SHA256_AFTER"
echo "STABLE_CHECK_JSON=$(printf '%s\n' "$STABLE_CHECK_JSON" | jq -c .)"
echo "STABLE_NOOP_JSON=$(printf '%s\n' "$STABLE_NOOP_JSON" | jq -c .)"
echo "PUBLIC_ROOT_STATUS=$PUBLIC_ROOT_STATUS"
echo "PROTECTED_API_STATUS=$PROTECTED_API_STATUS"
echo 'PRIMARY_SERVICE=PASS'
echo 'UPDATER_SERVICE=PASS'
echo 'PERSISTENCE_UNCHANGED=true'

rm -f /tmp/broray-light-r0010-p106-verified.ipk
rm -rf /tmp/broray-light-r0010-p106-input
[ ! -e /tmp/broray-light-r0010-p106-verified.ipk ] || fail 'verified package cleanup failed'
[ ! -e /tmp/broray-light-r0010-p106-input ] || fail 'public input cleanup failed'
echo 'TEMPORARY_INPUTS_REMOVED=true'

exit 0
