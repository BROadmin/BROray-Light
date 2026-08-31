#!/opt/bin/ash
BRORAY_BASE="${BRORAY_BASE:-${BRORAY_ROOT:-/opt/broray-light}}"
. "$BRORAY_BASE/lib/util.sh"; . "$BRORAY_BASE/lib/parser-vless.sh"; . "$BRORAY_BASE/lib/server.sh"
BRORAY_TMP="${BRORAY_TMP:-$BRORAY_BASE/tmp}"
broray_server_generate_id(){
 source_type="$1"; source_id="${2:-}"; source_index="${3:-0}"
 case "$source_type" in
  subscription) case "$source_id" in ''|*[!A-Za-z0-9._-]*) broray_die "некорректный ID подписки";; esac; case "$source_index" in ''|*[!0-9]*) broray_die "некорректный номер узла";; esac; printf 'subscription-%s-%04d\n' "$source_id" "$source_index";;
  manual) mkdir -p "$BRORAY_SERVERS"; i=0; while [ "$i" -lt 32 ]; do nonce="$(dd if=/dev/urandom bs=16 count=1 2>/dev/null | sha256sum | awk 'NR==1{print substr($1,1,10)}')"; [ -n "$nonce" ] || nonce="$(printf '%s:%s:%s' "$$" "$(date +%s)" "$i" | sha256sum | awk 'NR==1{print substr($1,1,10)}')"; id="manual-$(date '+%Y%m%d%H%M%S')-$nonce"; [ ! -e "$BRORAY_SERVERS/$id.json" ] && { printf '%s\n' "$id"; return; }; i=$((i+1)); done; broray_die "не удалось создать ID сервера";;
  *) broray_die "неподдерживаемый источник сервера";;
 esac
}
broray_server_identity_key(){ jq -cS '{protocol,address:(.address|ascii_downcase),port,uuid,flow:(.flow//""),network,security,serverName:(.reality.serverName//.tls.serverName//""),publicKey:(.reality.publicKey//""),shortId:(.reality.shortId//""),path:(.xhttp.path//.transport.path//""),serviceName:(.transport.serviceName//"")}' "$1" 2>/dev/null | sha256sum | awk 'NR==1{print $1}'; }
broray_server_import(){
 uri="$1"; source_type="${2:-manual}"; source_id="${3:-}"; source_index="${4:-0}"
 case "$uri" in vless://*) ;; *) broray_die "BROray-Light поддерживает только VLESS";; esac
 broray_parse_vless "$uri"; id="$(broray_server_generate_id "$source_type" "$source_id" "$source_index")"; mkdir -p "$BRORAY_SERVERS" "$BRORAY_TMP"
 out="$BRORAY_TMP/server-import.$$.json"
 jq -n --arg id "$id" --arg name "$BRORAY_NAME" --arg uri "$uri" --arg address "$BRORAY_ADDRESS" --argjson port "$BRORAY_PORT" --arg uuid "$BRORAY_UUID" --arg encryption "$BRORAY_ENCRYPTION" --arg flow "${BRORAY_FLOW:-}" --arg network "$BRORAY_NETWORK" --arg security "$BRORAY_SECURITY" --arg sourceType "$source_type" --arg sourceId "$source_id" --argjson sourceIndex "$source_index" --arg sni "$BRORAY_SNI" --arg fp "$BRORAY_FP" --argjson insecure "$BRORAY_ALLOW_INSECURE" --argjson alpn "$BRORAY_ALPN" --arg pbk "$BRORAY_PBK" --arg sid "$BRORAY_SID" --arg spx "$BRORAY_SPX" --arg host "$BRORAY_HOST" --arg path "$BRORAY_PATH" --arg serviceName "$BRORAY_SERVICE_NAME" --arg mode "$BRORAY_MODE" --arg headerType "$BRORAY_HEADER_TYPE" --argjson extra "$BRORAY_EXTRA" '{schemaVersion:2,id:$id,name:$name,source:(if $sourceType=="subscription" then {type:$sourceType,subscriptionId:$sourceId,nodeIndex:$sourceIndex} else {type:$sourceType} end),uri:$uri,protocol:"vless",address:$address,port:$port,uuid:$uuid,encryption:$encryption,flow:(if $flow=="" then null else $flow end),network:$network,security:$security,tls:{serverName:$sni,fingerprint:$fp,allowInsecure:$insecure,alpn:$alpn},reality:{serverName:$sni,fingerprint:$fp,publicKey:$pbk,shortId:$sid,spiderX:$spx},transport:{host:$host,path:$path,serviceName:$serviceName,mode:$mode,headerType:$headerType,extra:$extra},xhttp:{path:$path,mode:$mode,extra:$extra}}' > "$out" || broray_die "не удалось создать запись VLESS"
 broray_server_validate "$out"; key="$(broray_server_identity_key "$out")"; [ -n "$key" ] || broray_die "не удалось вычислить идентификатор VLESS-сервера"
 jq --arg key "$key" '.identityKey=$key' "$out" > "$out.keyed" && mv "$out.keyed" "$out" || broray_die "не удалось записать идентификатор сервера"
 if [ "$source_type" = manual ]; then for existing in "$BRORAY_SERVERS"/*.json; do [ -f "$existing" ] || continue; if jq -e --arg key "$key" '.identityKey==$key' "$existing" >/dev/null 2>&1; then rm -f "$out"; broray_die "такой VLESS-сервер уже добавлен"; fi; done; fi
 dest="$(broray_server_path "$id")"; [ ! -e "$dest" ] || broray_die "сервер уже существует"; chmod 600 "$out" && mv "$out" "$dest" || broray_die "не удалось сохранить сервер"; jq '.' "$dest"
}
