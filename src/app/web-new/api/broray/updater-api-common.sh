#!/opt/bin/ash
. /opt/broray-light/web-new/api/auth-common.sh
BRORAY_LIGHT_UPDATER="${BRORAY_LIGHT_UPDATER:-/opt/libexec/broray-light-updater/broray-light-updater.sh}"
broray_light_updater_available(){ [ -x "$BRORAY_LIGHT_UPDATER" ]; }
