#!/opt/bin/ash
BRORAY_BASE="${BRORAY_BASE:-${BRORAY_ROOT:-/opt/broray-light}}"
. "$BRORAY_BASE/lib/util.sh"
BRORAY_SERVERS="${BRORAY_SERVERS:-$BRORAY_BASE/servers}"
BRORAY_ACTIVE_SERVER_FILE="${BRORAY_ACTIVE_SERVER_FILE:-$BRORAY_BASE/config/active-server}"
broray_server_validate_id(){ id="$1"; [ -n "$id" ] || broray_die "не указан идентификатор сервера"; case "$id" in *[!A-Za-z0-9._-]*) broray_die "некорректный идентификатор сервера";; esac; }
broray_server_path(){ broray_server_validate_id "$1"; printf '%s/%s.json\n' "$BRORAY_SERVERS" "$1"; }
broray_server_exists(){ f="$(broray_server_path "$1")" || return 1; [ -f "$f" ] && [ ! -L "$f" ]; }
broray_server_validate(){
 f="$1"; [ -f "$f" ] && [ ! -L "$f" ] || broray_die "файл сервера недоступен"
 jq -e 'type=="object" and .schemaVersion==2 and (.id|type)=="string" and (.id|length)>0 and .protocol=="vless" and (.address|type)=="string" and (.address|length)>0 and (.port|type)=="number" and .port>=1 and .port<=65535 and (.uuid|type)=="string" and (.uuid|length)>0 and (.network=="raw" or .network=="ws" or .network=="grpc" or .network=="httpupgrade" or .network=="xhttp") and (.security=="none" or .security=="tls" or .security=="reality") and ((.flow//null)==null or .flow=="xtls-rprx-vision") and (if .security=="reality" then ((.reality.serverName|type)=="string" and (.reality.serverName|length)>0 and (.reality.publicKey|type)=="string" and (.reality.publicKey|length)>0) else true end)' "$f" >/dev/null 2>&1 || broray_die "некорректная запись VLESS-сервера"
}
broray_server_get_active_id(){ [ -s "$BRORAY_ACTIVE_SERVER_FILE" ] || broray_die "активный сервер не выбран"; cat "$BRORAY_ACTIVE_SERVER_FILE"; }
broray_server_set_active(){ id="$1"; broray_server_exists "$id" || broray_die "сервер не найден"; mkdir -p "${BRORAY_ACTIVE_SERVER_FILE%/*}"; t="$BRORAY_ACTIVE_SERVER_FILE.$$"; printf '%s\n' "$id" > "$t" && chmod 600 "$t" && mv "$t" "$BRORAY_ACTIVE_SERVER_FILE"; }
broray_server_current(){ id="$(broray_server_get_active_id)"; f="$(broray_server_path "$id")"; broray_server_validate "$f"; jq '.' "$f"; }
