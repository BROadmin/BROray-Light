from pathlib import Path
import json, shutil, os, re, hashlib, textwrap, time

BASE=Path('/mnt/data')
DONOR=BASE/'_r23app'
PREP=BASE/'BROray-Light-R23-PREPARATION-R0007'
OUT=BASE/'BROray-Light-SOURCE-R0008'
TREE=OUT/'src'
if OUT.exists(): shutil.rmtree(OUT)
TREE.mkdir(parents=True)
mapobj=json.loads((PREP/'R23-DONOR-FILE-TREATMENT.json').read_text())
records={r['path']:r for r in mapobj['records']}

BIN_EXT={'.png','.ico'}
def is_text(p): return p.suffix.lower() not in BIN_EXT
def adapt_text(s):
    for a,b in [
        ('/opt/var/lib/broray-updater','/opt/var/lib/broray-light-updater'),
        ('/opt/var/lib/broray','/opt/var/lib/broray-light'),
        ('/opt/var/lock/broray','/opt/var/lock/broray-light'),
        ('/opt/etc/init.d/S24broray','/opt/etc/init.d/S24broray-light'),
        ('/opt/broray','/opt/broray-light'),
    ]: s=s.replace(a,b)
    return s

def write(rel, content, mode=0o644):
    p=TREE/rel; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(textwrap.dedent(content).lstrip('\n'))
    os.chmod(p,mode)

def copy_adapt(rel, brand=False):
    src=DONOR/rel; dst=TREE/rel; dst.parent.mkdir(parents=True,exist_ok=True)
    if is_text(src):
        s=adapt_text(src.read_text())
        if brand: s=s.replace('BROray','BROray-Light')
        dst.write_text(s); os.chmod(dst,src.stat().st_mode & 0o777)
    else: shutil.copy2(src,dst)

def replace_func(text,name,new):
    m=re.search(r'^'+re.escape(name)+r'\(\)\n\{',text,re.M)
    if not m: raise RuntimeError('missing function '+name)
    n=re.search(r'^[A-Za-z_][A-Za-z0-9_]*\(\)\n\{',text[m.end():],re.M)
    end=m.end()+n.start() if n else len(text)
    return text[:m.start()]+textwrap.dedent(new).lstrip('\n').rstrip()+'\n\n'+text[end:]

# Base copy: exact retained/ported plus selected safety-heavy ADAPT modules.
copy_paths=[]
for r in mapobj['records']:
    if r['treatment'] in {'RETAIN','PORT'}: copy_paths.append(r['path'])
copy_paths += [
 'app/bin/broray-server-probe',
 'app/lib/interface-core.sh','app/lib/interface-manage.sh','app/lib/interface-owner.sh','app/lib/interface-sync.sh','app/lib/interface.sh',
 'app/lib/keenetic-config-compare.sh','app/lib/keenetic-page.sh',
 'app/lib/server-xray-manager.sh','app/lib/server-subscription-service.sh','app/lib/subscription-service.sh',
 'app/lib/xray-control.sh','app/lib/xray-update.sh','app/lib/xray.sh',
 'app/web-new/api/keenetic/action-common.sh','app/web-new/api/keenetic/check-upstream.cgi','app/web-new/api/keenetic/create.cgi','app/web-new/api/keenetic/repair.cgi','app/web-new/api/keenetic/status.cgi','app/web-new/api/keenetic/sync-description.cgi',
 'app/web-new/api/xray/operation-status.cgi','app/web-new/api/xray/status.cgi','app/web-new/api/xray/update-check.cgi',
 'app/web-new/assets/js/common.js','app/web-new/assets/js/login.js',
]
for rel in sorted(set(copy_paths)):
    if (DONOR/rel).exists(): copy_adapt(rel, brand=rel.startswith('app/lib/interface') or rel.startswith('app/lib/keenetic'))

# Auth common needs path + generic lock release.
p=TREE/'app/web-new/api/auth-common.sh'
s=p.read_text()
s=s.replace('broray_routes_api_lock_release','broray_operation_lock_release')
s=s.replace('if command -v broray_operation_lock_release >/dev/null 2>&1; then','if command -v broray_operation_lock_release >/dev/null 2>&1; then')
p.write_text(s)

# Compact lock extracted from full routes lock semantics: updater interlock + stale-owner cleanup, no route state.
write('app/lib/operation-lock.sh', r'''#!/opt/bin/ash
BRORAY_LIGHT_LOCK_ROOT="${BRORAY_LIGHT_LOCK_ROOT:-/opt/var/lock/broray-light}"
BRORAY_LIGHT_GLOBAL_LOCK="$BRORAY_LIGHT_LOCK_ROOT/global-operation.lock"
BRORAY_LIGHT_UPDATER_LOCK="${BRORAY_LIGHT_UPDATER_LOCK:-/opt/var/lock/broray-light-updater/request.lock}"
broray_operation_lock_owner_alive(){ p="$1"; case "$p" in ''|*[!0-9]*) return 1;; esac; kill -0 "$p" 2>/dev/null; }
broray_operation_lock_acquire(){
  operation="${1:-operation}"; mkdir -p "$BRORAY_LIGHT_LOCK_ROOT" || return 1
  [ ! -e "$BRORAY_LIGHT_UPDATER_LOCK" ] || return 2
  if mkdir "$BRORAY_LIGHT_GLOBAL_LOCK" 2>/dev/null; then
    printf '%s\n' "$$" > "$BRORAY_LIGHT_GLOBAL_LOCK/pid" || return 1
    printf '%s\n' "$operation" > "$BRORAY_LIGHT_GLOBAL_LOCK/operation"
    date '+%Y-%m-%dT%H:%M:%S%z' > "$BRORAY_LIGHT_GLOBAL_LOCK/startedAt"; return 0
  fi
  old="$(cat "$BRORAY_LIGHT_GLOBAL_LOCK/pid" 2>/dev/null || true)"
  if ! broray_operation_lock_owner_alive "$old"; then
    rm -rf "$BRORAY_LIGHT_GLOBAL_LOCK" || return 1
    mkdir "$BRORAY_LIGHT_GLOBAL_LOCK" 2>/dev/null || return 2
    printf '%s\n' "$$" > "$BRORAY_LIGHT_GLOBAL_LOCK/pid" || return 1
    printf '%s\n' "$operation" > "$BRORAY_LIGHT_GLOBAL_LOCK/operation"
    date '+%Y-%m-%dT%H:%M:%S%z' > "$BRORAY_LIGHT_GLOBAL_LOCK/startedAt"; return 0
  fi
  return 2
}
broray_operation_lock_release(){
  [ -d "$BRORAY_LIGHT_GLOBAL_LOCK" ] || return 0
  owner="$(cat "$BRORAY_LIGHT_GLOBAL_LOCK/pid" 2>/dev/null || true)"; [ "$owner" = "$$" ] || return 1
  rm -rf "$BRORAY_LIGHT_GLOBAL_LOCK"
}
''',0o755)

# VLESS-only model.
write('app/lib/server.sh', r'''#!/opt/bin/ash
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
''',0o755)

write('app/lib/server-import.sh', r'''#!/opt/bin/ash
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
''',0o755)

write('app/lib/server-config-generator.sh', r'''#!/opt/bin/ash
BRORAY_BASE="${BRORAY_BASE:-${BRORAY_ROOT:-/opt/broray-light}}"; . "$BRORAY_BASE/lib/util.sh"; . "$BRORAY_BASE/lib/server.sh"
BRORAY_TMP="${BRORAY_TMP:-$BRORAY_BASE/tmp}"; BRORAY_SETTINGS="${BRORAY_SETTINGS:-$BRORAY_BASE/config/system/settings.json}"
broray_generate_server_config(){
 id="$1"; broray_server_exists "$id" || broray_die "сервер $id не найден"; sf="$(broray_server_path "$id")"; broray_server_validate "$sf"; mkdir -p "$BRORAY_TMP"; out="$BRORAY_TMP/config.$id.$$.json"
 socks_port="$(jq -r '.socksPort//2080' "$BRORAY_SETTINGS" 2>/dev/null || echo 2080)"; log_level="$(jq -r '.logLevel//"warning"' "$BRORAY_SETTINGS" 2>/dev/null || echo warning)"
 jq -n --slurpfile s "$sf" --argjson socksPort "$socks_port" --arg logLevel "$log_level" '
 def stream($x): ({network:$x.network,security:$x.security} + (if $x.security=="tls" then {tlsSettings:{serverName:($x.tls.serverName//$x.address),fingerprint:($x.tls.fingerprint//"chrome"),allowInsecure:($x.tls.allowInsecure//false),alpn:($x.tls.alpn//[])}} elif $x.security=="reality" then {realitySettings:{serverName:($x.reality.serverName//$x.address),fingerprint:($x.reality.fingerprint//"chrome"),publicKey:$x.reality.publicKey,shortId:($x.reality.shortId//""),spiderX:($x.reality.spiderX//"")}} else {} end) + (if $x.network=="ws" then {wsSettings:{path:($x.transport.path//"/"),headers:(if (($x.transport.host//"")|length)>0 then {Host:$x.transport.host} else {} end)}} elif $x.network=="grpc" then {grpcSettings:{serviceName:($x.transport.serviceName//"")}} elif $x.network=="httpupgrade" then {httpupgradeSettings:{path:($x.transport.path//"/"),host:($x.transport.host//"")}} elif $x.network=="xhttp" then {xhttpSettings:({path:($x.xhttp.path//"/"),mode:($x.xhttp.mode//"auto")} + (if (($x.xhttp.extra//{})|length)>0 then {extra:$x.xhttp.extra} else {} end))} else {} end));
 ($s[0]) as $x | {log:{loglevel:$logLevel},inbounds:[{tag:"socks-in",listen:"127.0.0.1",port:$socksPort,protocol:"socks",settings:{auth:"noauth",udp:true},sniffing:{enabled:true,destOverride:["http","tls","quic"],routeOnly:true}}],outbounds:[{tag:"proxy",protocol:"vless",settings:{vnext:[{address:$x.address,port:$x.port,users:[{id:$x.uuid,encryption:($x.encryption//"none")}+(if (($x.flow//"")|length)>0 then {flow:$x.flow} else {} end)]}]},streamSettings:stream($x)},{tag:"direct",protocol:"freedom"},{tag:"block",protocol:"blackhole"}],routing:{domainStrategy:"AsIs",rules:[{type:"field",inboundTag:["socks-in"],outboundTag:"proxy"}]}}' > "$out" || broray_die "не удалось сформировать конфигурацию Xray"
 jq -e . "$out" >/dev/null 2>&1 || broray_die "сформирован некорректный JSON Xray"; printf '%s\n' "$out"
}
''',0o755)

# Server subscription service: keep hardened r23 transactional sync; just adapt path/quality state name.
p=TREE/'app/lib/server-subscription-service.sh'; s=p.read_text().replace('run/server-quality','run/server-checks').replace('BRORAY_SERVER_SUB_QUALITY','BRORAY_SERVER_SUB_CHECKS'); p.write_text(s)

# Subscription service: VLESS-only extraction/staging while retaining download/transaction/sync logic.
p=TREE/'app/lib/subscription-service.sh'; sub=p.read_text()
if '. "$BRORAY_BASE/lib/server-import.sh"' not in sub[:2200]: sub=sub.replace('#!/opt/bin/ash\n','#!/opt/bin/ash\n\nBRORAY_BASE="${BRORAY_BASE:-${BRORAY_ROOT:-/opt/broray-light}}"\n. "$BRORAY_BASE/lib/server-import.sh"\n',1)
sub=sub.replace('BRORAY_SUB_USER_AGENT="BROray/3.0.0"','BRORAY_SUB_USER_AGENT="BROray-Light/0.1.0-dev"')
# keep default name; disable scheduler and make immediate update default true
sub=sub.replace("create_name=\"$(jq -r '.name // empty' \"$create_body\")\"", "create_name=\"$(jq -r '.name // \"Подписка\"' \"$create_body\")\"")
sub=sub.replace("create_auto=\"$(jq -r 'if has(\"autoUpdateEnabled\") then .autoUpdateEnabled else true end' \"$create_body\")\"", 'create_auto=false')
sub=sub.replace("create_immediate=\"$(jq -r 'if has(\"updateImmediately\") then .updateImmediately else false end' \"$create_body\")\"", "create_immediate=\"$(jq -r 'if has(\"updateImmediately\") then .updateImmediately else true end' \"$create_body\")\"")
sub=replace_func(sub,'broray_subscription_extract_nodes',r'''broray_subscription_extract_nodes()
{
 source_file="$1"; output_file="$2"; skipped_file="${3:-}"; : > "$output_file"; [ -z "$skipped_file" ] || : > "$skipped_file"
 temp="$BRORAY_SUB_TMP/extract.$$.txt"
 if grep -Eq '^[[:space:]]*(vless|vmess|trojan|ss|hysteria2|hy2|tuic|socks|socks5|http|https)://' "$source_file"; then cp "$source_file" "$temp"; else broray_subscription_decode_base64 "$source_file" "$temp" || cp "$source_file" "$temp"; fi
 tr '\r' '\n' < "$temp" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | while IFS= read -r line; do [ -n "$line" ] || continue; case "$line" in vless://*) printf '%s\n' "$line" >> "$output_file";; vmess://*|trojan://*|ss://*|hysteria2://*|hy2://*|tuic://*|socks://*|socks5://*|http://*|https://*) [ -z "$skipped_file" ] || printf '%s\n' "$line" >> "$skipped_file";; *) :;; esac; done
 rm -f "$temp"; [ -s "$output_file" ]
}''')
sub=replace_func(sub,'broray_subscription_stage_nodes',r'''broray_subscription_stage_nodes()
{
 stage_subscription_id="$1"; stage_nodes_file="$2"; stage_output_dir="$3"; stage_enabled="${4:-true}"; stage_raw_dir="$BRORAY_SUB_TMP/subscription-stage-raw.$$.d"; stage_warnings="$BRORAY_SUB_TMP/subscription-warnings.$$.txt"
 rm -rf "$stage_output_dir" "$stage_raw_dir"; mkdir -p "$stage_output_dir" "$stage_raw_dir" || return 1; : > "$stage_warnings"; BRORAY_SUB_ACCEPTED=0; BRORAY_SUB_REJECTED=0; stage_index=0
 while IFS= read -r stage_uri; do [ -n "$stage_uri" ] || continue; stage_index=$((stage_index+1)); stage_raw_id="subscription-${stage_subscription_id}-$(printf '%04d' "$stage_index")"
  if BRORAY_SERVERS="$stage_raw_dir" broray_server_import "$stage_uri" subscription "$stage_subscription_id" "$stage_index" >/dev/null 2>&1; then
   stage_raw_file="$stage_raw_dir/$stage_raw_id.json"; [ -f "$stage_raw_file" ] || { BRORAY_SUB_REJECTED=$((BRORAY_SUB_REJECTED+1)); continue; }
   stage_key="$(broray_server_subscription_import_key "$stage_raw_file")"; [ -n "$stage_key" ] || { BRORAY_SUB_REJECTED=$((BRORAY_SUB_REJECTED+1)); continue; }
   stage_stable_id="subscription-${stage_subscription_id}-$(printf '%s' "$stage_key" | cut -c 1-16)"; stage_file="$stage_output_dir/$stage_stable_id.json"
   [ ! -f "$stage_file" ] || { BRORAY_SUB_REJECTED=$((BRORAY_SUB_REJECTED+1)); continue; }
   stage_now="$(broray_subscription_now_iso)"
   if jq --arg id "$stage_stable_id" --arg subscriptionId "$stage_subscription_id" --arg importKey "$stage_key" --argjson nodeIndex "$stage_index" --arg updatedAt "$stage_now" --argjson enabled "$stage_enabled" '.id=$id|.source={type:"subscription",subscriptionId:$subscriptionId,importKey:$importKey,nodeIndex:$nodeIndex,enabled:$enabled,updatedAt:$updatedAt}' "$stage_raw_file" > "$stage_file" && broray_server_validate "$stage_file" >/dev/null 2>&1; then chmod 600 "$stage_file" || true; BRORAY_SUB_ACCEPTED=$((BRORAY_SUB_ACCEPTED+1)); else rm -f "$stage_file"; BRORAY_SUB_REJECTED=$((BRORAY_SUB_REJECTED+1)); fi
  else BRORAY_SUB_REJECTED=$((BRORAY_SUB_REJECTED+1)); fi
 done < "$stage_nodes_file"
 rm -rf "$stage_raw_dir"; BRORAY_SUB_WARNINGS_FILE="$stage_warnings"; export BRORAY_SUB_ACCEPTED BRORAY_SUB_REJECTED BRORAY_SUB_WARNINGS_FILE
 [ "$BRORAY_SUB_ACCEPTED" -gt 0 ] || { broray_subscription_set_error "NO_VALID_VLESS_NODES" "Ни один VLESS-сервер подписки не прошёл проверку."; return 1; }
 return 0
}''')
# Replace scheduler once if present.
if re.search(r'^broray_subscription_scheduler_once\(\)',sub,re.M): sub=replace_func(sub,'broray_subscription_scheduler_once','''broray_subscription_scheduler_once()\n{\n return 0\n}''')
p.write_text(sub)

# Interface/Keenetic: remove route-state coupling while preserving r23 exact block validator.
owner=TREE/'app/lib/interface-owner.sh'; s=owner.read_text()
s=s.replace('BRORAY_ROUTES_CONFIG_FILE="${BRORAY_ROUTES_CONFIG_FILE:-$BRORAY_BASE/routes/config.json}"\nBRORAY_ROUTES_MANIFEST_DIR="${BRORAY_ROUTES_MANIFEST_DIR:-$BRORAY_BASE/routes/manifests}"\nBRORAY_ROUTES_SHARE_MANIFEST_DIR="${BRORAY_ROUTES_SHARE_MANIFEST_DIR:-$BRORAY_BASE/share/routes/manifests}"\nBRORAY_INTERFACE_NDMC="${BRORAY_INTERFACE_NDMC:-${BRORAY_ROUTES_CONFIG_NDMC:-ndmc}}"', 'BRORAY_INTERFACE_CONFIG_FILE="${BRORAY_INTERFACE_CONFIG_FILE:-$BRORAY_BASE/config/system/interface.json}"\nBRORAY_INTERFACE_NDMC="${BRORAY_INTERFACE_NDMC:-ndmc}"')
s=replace_func(s,'broray_interface_configured_name',r'''broray_interface_configured_name()
{
 local name
 [ -r "$BRORAY_INTERFACE_CONFIG_FILE" ] && [ ! -L "$BRORAY_INTERFACE_CONFIG_FILE" ] || return 1
 name="$(jq -r '.managedInterface//empty' "$BRORAY_INTERFACE_CONFIG_FILE" 2>/dev/null)"; broray_interface_name_valid "$name" || return 1; printf '%s\n' "$name"
}''')
s=replace_func(s,'broray_interface_sync_route_policy',r'''broray_interface_sync_selection()
{
 local name dir temp
 name="${1:-$(broray_interface_selected_name)}"; broray_interface_name_valid "$name" || return 1
 dir="${BRORAY_INTERFACE_CONFIG_FILE%/*}"; mkdir -p "$dir" || return 1; [ -d "$dir" ] && [ ! -L "$dir" ] || return 1; [ ! -L "$BRORAY_INTERFACE_CONFIG_FILE" ] || return 1
 temp="$BRORAY_INTERFACE_CONFIG_FILE.new.$$"
 if [ -f "$BRORAY_INTERFACE_CONFIG_FILE" ]; then jq --arg name "$name" '(if type=="object" then . else {} end)|.schemaVersion=1|.managedInterface=$name' "$BRORAY_INTERFACE_CONFIG_FILE" > "$temp" || { rm -f "$temp"; return 1; }; else jq -n --arg name "$name" '{schemaVersion:1,managedInterface:$name}' > "$temp" || { rm -f "$temp"; return 1; }; fi
 jq -e --arg name "$name" '.schemaVersion==1 and .managedInterface==$name' "$temp" >/dev/null 2>&1 || { rm -f "$temp"; return 1; }; chmod 600 "$temp" 2>/dev/null || true; mv -f "$temp" "$BRORAY_INTERFACE_CONFIG_FILE"
}''')
s=s.replace('broray_interface_sync_route_policy','broray_interface_sync_selection')
# Light owns only Light records; no implicit adoption of full BROray ownership.
s=s.replace('BROray-Light-Light','BROray-Light')
s=s.replace('r14c38-proxy-owned-interface/1','broray-light-proxy-owned-interface/1')
s=s.replace('r14c37-proxy-owned-interface/1','broray-light-proxy-owned-interface/1').replace('r14c36-proxy-owned-interface/1','broray-light-proxy-owned-interface/1').replace('r14c35-proxy-owned-interface/1','broray-light-proxy-owned-interface/1').replace('r14c34-proxy-owned-interface/1','broray-light-proxy-owned-interface/1')
s=s.replace('r14c01-proxy-provisional-create/1','broray-light-proxy-provisional-create/1')
# Normalize live ownership/reservation receipt identities to the Light product. Keep the r23 bounded proxy-connect-via parser semantics unchanged.
for _a,_b in [
 ('r14c21-proxy-runtime-selection-baseline/1','broray-light-proxy-runtime-selection-baseline/1'),
 ('candidate=3.0.0-r15c16','candidate=0.1.0-dev'),
 ('r14c21-proxy-create-reservation/1','broray-light-proxy-create-reservation/1'),
 ('candidateId:"3.0.0-r15c16"','candidateId:"0.1.0-dev"'),
 ('.candidateId=="3.0.0-r15c16"','.candidateId=="0.1.0-dev"'),
 ('r14c01-proxy-owner-quarantine/1','broray-light-proxy-owner-quarantine/1'),
 ('r14c21','BROray-Light'),
 ('R14C01','BROray-Light'),
]: s=s.replace(_a,_b)
s=s.replace('''(.contract=="broray-light-proxy-owned-interface/1" or
       .contract=="broray-light-proxy-owned-interface/1" or
       .contract=="broray-light-proxy-owned-interface/1" or
       .contract=="broray-light-proxy-owned-interface/1" or
       .contract=="broray-light-proxy-owned-interface/1")''','''.contract=="broray-light-proxy-owned-interface/1"''')
owner.write_text(s)
for rel in ['app/lib/interface-manage.sh','app/lib/interface-core.sh','app/lib/interface-sync.sh','app/lib/keenetic-page.sh']:
 p=TREE/rel; t=p.read_text().replace('broray_interface_sync_route_policy','broray_interface_sync_selection').replace('BROray-Light-Light','BROray-Light')
 t=t.replace('r14c01-proxy-ndmc-stage-evidence/1','broray-light-proxy-ndmc-stage-evidence/1').replace('R14C01','BROray-Light')
 p.write_text(t)

# Light-specific immutable write-policy contract: proxy interface only.
policy_id=hashlib.sha256(b'BROray-Light/proxy-interface/dynamic-bounded-v1/1').hexdigest()
write('app/lib/keenetic-write-policy.sh', f'''#!/opt/bin/ash
BRORAY_KEENETIC_WRITE_POLICY_SCHEMA_VERSION=1
BRORAY_KEENETIC_WRITE_POLICY_CANDIDATE_ID='BROray-Light-r0008'
BRORAY_KEENETIC_WRITE_POLICY_STAGE='staged'
BRORAY_KEENETIC_WRITE_POLICY_ENABLED=true
BRORAY_KEENETIC_WRITE_POLICY_SHA256='{policy_id}'
BRORAY_KEENETIC_PROXY_INTERFACE_SERIALIZATION='dynamic-bounded-v1'
broray_keenetic_write_policy_contract_valid(){{ [ "$BRORAY_KEENETIC_WRITE_POLICY_SCHEMA_VERSION" = 1 ] && [ "$BRORAY_KEENETIC_WRITE_POLICY_ENABLED" = true ] && [ "$BRORAY_KEENETIC_WRITE_POLICY_STAGE" = staged ] && [ "${{#BRORAY_KEENETIC_WRITE_POLICY_SHA256}}" -eq 64 ] && [ "$BRORAY_KEENETIC_PROXY_INTERFACE_SERIALIZATION" = dynamic-bounded-v1 ]; }}
broray_keenetic_write_policy_check(){{ [ "${{1:-}}" = proxy-interface ] || return 4; broray_keenetic_write_policy_contract_valid || return 3; return 0; }}
broray_keenetic_write_policy_sha256(){{ broray_keenetic_write_policy_contract_valid || return 1; printf '%s\\n' "$BRORAY_KEENETIC_WRITE_POLICY_SHA256"; }}
broray_keenetic_write_policy_proxy_interface_profile_check(){{ broray_keenetic_write_policy_check proxy-interface; }}
BRORAY_KEENETIC_WRITE_POLICY_LOADED=true
''',0o755)

# Xray internal lifecycle.
write('app/bin/broray-xray-start', r'''#!/opt/bin/ash
ROOT="${BRORAY_ROOT:-/opt/broray-light}"; CONFIG="$ROOT/config/config.json"; XRAY="$ROOT/runtime/xray"
[ -x "$XRAY" ] || { echo "Xray недоступен" >&2; exit 1; }; [ -s "$CONFIG" ] || { echo "Конфигурация Xray отсутствует" >&2; exit 1; }
XRAY_LOCATION_ASSET="$ROOT/bin"; export XRAY_LOCATION_ASSET; exec "$XRAY" run -c "$CONFIG"
''',0o755)
write('app/bin/xray', '#!/opt/bin/ash\nexec /opt/broray-light/runtime/xray "$@"\n',0o755)
write('app/bin/broray-xray-control', r'''#!/opt/bin/ash
ROOT="${BRORAY_ROOT:-/opt/broray-light}"
start(){ pidof xray >/dev/null 2>&1 && return 0; [ -s "$ROOT/config/config.json" ] || return 1; "$ROOT/bin/broray-xray-start" >>"$ROOT/logs/xray.log" 2>&1 & i=0; while [ "$i" -lt 10 ]; do pidof xray >/dev/null 2>&1 && return 0; i=$((i+1)); sleep 1; done; return 1; }
stop(){ pidof xray >/dev/null 2>&1 || return 0; killall xray 2>/dev/null || true; i=0; while [ "$i" -lt 10 ]; do pidof xray >/dev/null 2>&1 || return 0; i=$((i+1)); sleep 1; done; killall -9 xray 2>/dev/null || true; ! pidof xray >/dev/null 2>&1; }
restart(){ stop && start; }; status(){ pidof xray >/dev/null 2>&1; }
case "${1:-}" in start|stop|restart|status) "$1";; *) echo 'Usage: broray-xray-control {start|stop|restart|status}' >&2; exit 1;; esac
''',0o755)
# Patch donor Xray modules.
for rel in ['app/lib/xray-control.sh','app/lib/xray-update.sh','app/lib/xray.sh']:
 p=TREE/rel; t=p.read_text().replace('/opt/broray-light-light','/opt/broray-light').replace('/opt/etc/init.d/S24broray-light','/opt/broray-light/bin/broray-xray-control').replace('broray-xray-control-light','broray-xray-control').replace('.broray-r14c38-backup','.broray-light-backup'); p.write_text(t)
# xray update safe paths need Light namespace already adapted.
write('app/lib/xray-web-operation.sh', r'''#!/opt/bin/ash
BRORAY_ROOT="${BRORAY_ROOT:-/opt/broray-light}"; . "$BRORAY_ROOT/lib/operation-lock.sh"; . "$BRORAY_ROOT/lib/xray-control.sh"; . "$BRORAY_ROOT/lib/xray-update.sh"
broray_xray_web_update(){ rc=0; broray_operation_lock_acquire xray-update || rc=$?; [ "$rc" -eq 0 ] || return "$rc"; trap 'broray_operation_lock_release >/dev/null 2>&1 || true' EXIT; broray_xray_update_install update; }
''',0o755)
# Patch server manager for internal control + post-activation real probe rollback.
p=TREE/'app/lib/server-xray-manager.sh'; t=p.read_text(); t=t.replace('BRORAY_INIT="${BRORAY_INIT:-/opt/etc/init.d/S24broray-light}"','BRORAY_INIT="${BRORAY_INIT:-/opt/broray-light/bin/broray-xray-control}"').replace('BRORAY_XRAY="/opt/broray-light/runtime/xray"','BRORAY_XRAY="${BRORAY_XRAY:-$BRORAY_BASE/runtime/xray}"')
needle='    broray_interface_sync_description ||\n'
probe=r'''    probe_result="$BRORAY_BASE/tmp/post-activate-probe.$$.json"
    if ! "$BRORAY_BASE/bin/broray-server-probe" "$BRORAY_CONFIG" "$server_id" > "$probe_result" 2>/dev/null; then
        echo "Реальная проверка соединения не пройдена. Выполняется откат." >&2; rm -f "$probe_result"
        if [ -f "$backup_config" ]; then cp "$backup_config" "$BRORAY_CONFIG"; else rm -f "$BRORAY_CONFIG"; fi
        if [ -n "$previous_server_id" ]; then printf '%s\n' "$previous_server_id" > "$BRORAY_ACTIVE_SERVER_FILE"; else rm -f "$BRORAY_ACTIVE_SERVER_FILE"; fi
        "$BRORAY_INIT" restart >/dev/null 2>&1 || true; broray_die "проверка соединения после активации не пройдена"
    fi
    mkdir -p "$BRORAY_BASE/run/server-checks"; chmod 600 "$probe_result" 2>/dev/null || true; mv "$probe_result" "$BRORAY_BASE/run/server-checks/$server_id.json" || true

'''
if needle not in t: raise RuntimeError('server manager insertion missing')
t=t.replace(needle,probe+needle,1); p.write_text(t)

# Health-only server service.
write('app/lib/server-service.sh', r'''#!/opt/bin/ash
BRORAY_BASE="${BRORAY_BASE:-${BRORAY_ROOT:-/opt/broray-light}}"; . "$BRORAY_BASE/lib/util.sh"; . "$BRORAY_BASE/lib/server.sh"; . "$BRORAY_BASE/lib/server-config-generator.sh"; . "$BRORAY_BASE/lib/server-xray-manager.sh"
BRORAY_CHECK_STATE="${BRORAY_CHECK_STATE:-$BRORAY_BASE/run/server-checks}"; BRORAY_PROBE="${BRORAY_PROBE:-$BRORAY_BASE/bin/broray-server-probe}"
broray_server_check_path(){ broray_server_validate_id "$1"; printf '%s/%s.json\n' "$BRORAY_CHECK_STATE" "$1"; }
broray_server_summary(){ mkdir -p "$BRORAY_SERVERS" "$BRORAY_CHECK_STATE" "$BRORAY_BASE/tmp"; active="$(cat "$BRORAY_ACTIVE_SERVER_FILE" 2>/dev/null || true)"; tmp="$BRORAY_BASE/tmp/server-summary.$$.jsonl"; : > "$tmp"; for f in "$BRORAY_SERVERS"/*.json; do [ -f "$f" ] || continue; broray_server_validate "$f" || continue; id="$(jq -r .id "$f")"; c="$(broray_server_check_path "$id")"; if [ -f "$c" ]; then jq -n --slurpfile s "$f" --slurpfile c "$c" --arg active "$active" '($s[0])+{active:($s[0].id==$active),lastCheck:$c[0]}' >> "$tmp"; else jq -n --slurpfile s "$f" --arg active "$active" '($s[0])+{active:($s[0].id==$active),lastCheck:null}' >> "$tmp"; fi; done; jq -s --arg active "$active" '{schemaVersion:1,activeServerId:(if $active=="" then null else $active end),servers:.,count:length}' "$tmp"; rm -f "$tmp"; }
broray_server_details(){ id="$1"; broray_server_exists "$id" || broray_die "сервер не найден"; f="$(broray_server_path "$id")"; c="$(broray_server_check_path "$id")"; if [ -f "$c" ]; then jq -n --slurpfile s "$f" --slurpfile c "$c" '($s[0])+{lastCheck:$c[0]}'; else jq -n --slurpfile s "$f" '($s[0])+{lastCheck:null}'; fi; }
broray_server_check(){ id="$1"; broray_server_exists "$id" || broray_die "сервер не найден"; mkdir -p "$BRORAY_CHECK_STATE"; cfg="$(broray_generate_server_config "$id")"; tmp="$(broray_server_check_path "$id").$$"; rc=0; "$BRORAY_PROBE" "$cfg" "$id" > "$tmp" || rc=$?; rm -f "$cfg"; jq -e . "$tmp" >/dev/null 2>&1 || { rm -f "$tmp"; broray_die "пробник вернул некорректный JSON"; }; chmod 600 "$tmp"; mv "$tmp" "$(broray_server_check_path "$id")"; cat "$(broray_server_check_path "$id")"; return "$rc"; }
broray_server_activate(){ id="$1"; broray_server_exists "$id" || broray_die "сервер не найден"; broray_xray_apply_server "$id"; broray_server_details "$id"; }
broray_server_delete_safe(){ id="$1"; active="$(cat "$BRORAY_ACTIVE_SERVER_FILE" 2>/dev/null || true)"; [ "$id" != "$active" ] || broray_die "нельзя удалить активный сервер"; f="$(broray_server_path "$id")"; [ -f "$f" ] || broray_die "сервер не найден"; rm -f "$f" "$(broray_server_check_path "$id")"; jq -n --arg id "$id" '{deleted:true,id:$id}'; }
''',0o755)

# Health monitor and deterministic failover.
write('app/bin/broray-connection-monitor', r'''#!/opt/bin/ash
ROOT="${BRORAY_ROOT:-/opt/broray-light}"; STATE="$ROOT/run/connection-state.json"; mkdir -p "$ROOT/run" "$ROOT/tmp"; active="$(cat "$ROOT/config/active-server" 2>/dev/null || true)"; now="$(date '+%Y-%m-%dT%H:%M:%S%z')"; success=false; error=""
if [ -n "$active" ]; then if "$ROOT/bin/broray-servers" check "$active" monitor >/dev/null 2>"$ROOT/tmp/connection-monitor.err"; then success=true; else error="$(tail -c 600 "$ROOT/tmp/connection-monitor.err" 2>/dev/null)"; fi; else error="активный сервер не выбран"; fi
jq -n --arg serverId "$active" --arg checkedAt "$now" --arg error "$error" --argjson connected "$success" '{schemaVersion:1,connected:$connected,activeServerId:(if $serverId=="" then null else $serverId end),checkedAt:$checkedAt,error:(if $error=="" then null else $error end)}' > "$STATE.$$" && chmod 600 "$STATE.$$" && mv "$STATE.$$" "$STATE"; cat "$STATE"
''',0o755)
write('app/bin/broray-server-auto-switch', r'''#!/opt/bin/ash
ROOT="${BRORAY_ROOT:-/opt/broray-light}"; CFG="$ROOT/config/system/server-auto-switch.json"; STATE="$ROOT/run/server-auto-switch-state.json"; . "$ROOT/lib/operation-lock.sh"; mkdir -p "$ROOT/run" "$ROOT/tmp"; [ -r "$CFG" ] || exit 0; jq -e '.enabled==true' "$CFG" >/dev/null 2>&1 || exit 0
threshold="$(jq -r '.failureThreshold//3' "$CFG")"; cooldown="$(jq -r '.cooldownSeconds//600' "$CFG")"; prev="$(jq -r '.consecutiveFailures//0' "$STATE" 2>/dev/null || echo 0)"; active="$(cat "$ROOT/config/active-server" 2>/dev/null || true)"
if [ -n "$active" ] && "$ROOT/bin/broray-servers" check "$active" auto-switch >/dev/null 2>&1; then jq -n --arg active "$active" --arg now "$(date '+%Y-%m-%dT%H:%M:%S%z')" '{schemaVersion:1,activeServerId:$active,consecutiveFailures:0,lastCheckAt:$now,status:"healthy"}' > "$STATE.$$" && mv "$STATE.$$" "$STATE"; exit 0; fi
fails=$((prev+1)); if [ "$fails" -lt "$threshold" ]; then jq -n --arg active "$active" --argjson f "$fails" --arg now "$(date '+%Y-%m-%dT%H:%M:%S%z')" '{schemaVersion:1,activeServerId:$active,consecutiveFailures:$f,lastCheckAt:$now,status:"degraded"}' > "$STATE.$$" && mv "$STATE.$$" "$STATE"; exit 1; fi
last="$(jq -r '.lastSwitchEpoch//0' "$STATE" 2>/dev/null || echo 0)"; now_epoch="$(date +%s)"; [ $((now_epoch-last)) -ge "$cooldown" ] || exit 1
broray_operation_lock_acquire auto-switch || exit 1; trap 'broray_operation_lock_release >/dev/null 2>&1 || true' EXIT
ordered="$(jq -r '.orderedServerIds[]?' "$CFG")"; excluded="$(jq -r '.excludedServerIds[]?' "$CFG")"; for id in $ordered; do [ "$id" = "$active" ] && continue; printf '%s\n' "$excluded" | grep -Fxq "$id" && continue; if "$ROOT/bin/broray-servers" check "$id" auto-switch >/dev/null 2>&1 && "$ROOT/bin/broray-servers" activate "$id" >/dev/null 2>&1; then jq -n --arg old "$active" --arg id "$id" --arg now "$(date '+%Y-%m-%dT%H:%M:%S%z')" --argjson epoch "$now_epoch" '{schemaVersion:1,activeServerId:$id,previousServerId:$old,consecutiveFailures:0,lastCheckAt:$now,lastSwitchAt:$now,lastSwitchEpoch:$epoch,lastSwitchTarget:$id,status:"switched"}' > "$STATE.$$" && mv "$STATE.$$" "$STATE"; exit 0; fi; done
jq -n --arg active "$active" --argjson f "$fails" --arg now "$(date '+%Y-%m-%dT%H:%M:%S%z')" '{schemaVersion:1,activeServerId:$active,consecutiveFailures:$f,lastCheckAt:$now,status:"no-replacement"}' > "$STATE.$$" && mv "$STATE.$$" "$STATE"; exit 1
''',0o755)

# Commands.
write('app/bin/broray-servers', '#!/opt/bin/ash\nROOT="${BRORAY_ROOT:-/opt/broray-light}"; . "$ROOT/lib/server-service.sh"; . "$ROOT/lib/server-import.sh"\ncmd="${1:-summary}"; shift 2>/dev/null || true\ncase "$cmd" in summary|list) broray_server_summary;; show) broray_server_details "${1:-}";; import) broray_server_import "${1:-}" manual "" 0;; check) broray_server_check "${1:-}" "${2:-manual}";; activate|use) broray_server_activate "${1:-}";; delete) broray_server_delete_safe "${1:-}";; *) echo "usage: broray-servers summary|show|import|check|activate|delete" >&2; exit 1;; esac\n',0o755)
write('app/bin/broray-server', '#!/opt/bin/ash\nexec /opt/broray-light/bin/broray-servers "$@"\n',0o755)
copy_adapt('app/bin/broray-subscriptions')
write('app/bin/broray', '#!/opt/bin/ash\nROOT="${BRORAY_ROOT:-/opt/broray-light}"; cmd="${1:-info}"; shift 2>/dev/null || true\ncase "$cmd" in info|status) exec "$ROOT/bin/broray-system" info;; server|servers) exec "$ROOT/bin/broray-servers" "$@";; subscriptions) exec "$ROOT/bin/broray-subscriptions" "$@";; *) echo "BROray-Light: info | servers | subscriptions" >&2; exit 1;; esac\n',0o755)
write('app/bin/broray-system', '#!/opt/bin/ash\nROOT="${BRORAY_ROOT:-/opt/broray-light}"; VERSION="$(cat "$ROOT/config/version" 2>/dev/null || echo unknown)"; XRAY="$ROOT/runtime/xray"\ncase "${1:-info}" in info|status) jq -n --arg version "$VERSION" --arg xrayVersion "$($XRAY version 2>/dev/null | head -1 | awk \x27{print $2}\x27)" \x27{ok:true,product:"BROray-Light",version:$version,xrayVersion:(if $xrayVersion=="" then null else $xrayVersion end),releaseChannel:"stable"}\x27;; *) exit 1;; esac\n',0o755)

# Runtime defaults/service.
write('app/bin/broray-runtime-prepare', r'''#!/opt/bin/ash
set -eu; ROOT="${BRORAY_ROOT:-/opt/broray-light}"; for d in backup config config/system logs run servers subscriptions tmp web-new runtime; do mkdir -p "$ROOT/$d"; done; chmod 700 "$ROOT/backup" "$ROOT/config" "$ROOT/servers" "$ROOT/subscriptions" "$ROOT/tmp" 2>/dev/null || true
[ -s "$ROOT/config/system/settings.json" ] || cp "$ROOT/share/defaults/settings.json" "$ROOT/config/system/settings.json"; [ -s "$ROOT/config/system/server-auto-switch.json" ] || cp "$ROOT/share/defaults/server-auto-switch.json" "$ROOT/config/system/server-auto-switch.json"; [ -s "$ROOT/config/lighttpd.conf" ] || cp "$ROOT/share/defaults/lighttpd.conf" "$ROOT/config/lighttpd.conf"; [ -s "$ROOT/config/version" ] || cp "$ROOT/share/defaults/version" "$ROOT/config/version"
''',0o755)
write('app/bin/broray-lightd', r'''#!/opt/bin/ash
set -eu; ROOT="${BRORAY_ROOT:-/opt/broray-light}"; INTERVAL="${BRORAY_LIGHT_INTERVAL:-30}"; PIDFILE="$ROOT/run/broray-lightd.pid"; mkdir -p "$ROOT/run" "$ROOT/tmp"; printf '%s\n' "$$" > "$PIDFILE"; cleanup(){ rm -f "$PIDFILE"; }; trap 'cleanup; exit 0' HUP INT TERM; trap cleanup EXIT
while :; do if ! pidof xray >/dev/null 2>&1 && [ -x "$ROOT/runtime/xray" ] && [ -s "$ROOT/config/config.json" ]; then XRAY_LOCATION_ASSET="$ROOT/bin" "$ROOT/runtime/xray" run -test -c "$ROOT/config/config.json" >/dev/null 2>&1 && "$ROOT/bin/broray-xray-start" >>"$ROOT/logs/xray.log" 2>&1 & fi; "$ROOT/bin/broray-connection-monitor" >/dev/null 2>&1 || true; "$ROOT/bin/broray-server-auto-switch" >/dev/null 2>&1 || true; "$ROOT/bin/broray-home-snapshot" >/dev/null 2>&1 || true; sleep "$INTERVAL"; done
''',0o755)
write('init/S24broray-light', r'''#!/opt/bin/ash

ROOT="${BRORAY_ROOT:-/opt/broray-light}"
DAEMON="$ROOT/bin/broray-lightd"
DP="$ROOT/run/broray-lightd.pid"
WP="$ROOT/run/lighttpd.pid"

pid_alive()
{
    p="${1:-}"
    case "$p" in ''|*[!0-9]*) return 1 ;; esac
    kill -0 "$p" 2>/dev/null
}

start_web()
{
    w="$(cat "$WP" 2>/dev/null || true)"
    pid_alive "$w" && return 0
    LIGHTTPD="$(command -v lighttpd 2>/dev/null || true)"
    [ -n "$LIGHTTPD" ] || { echo "lighttpd недоступен" >&2; return 1; }
    "$LIGHTTPD" -f "$ROOT/config/lighttpd.conf" || return 1
    i=0
    while [ "$i" -lt 5 ]; do
        w="$(cat "$WP" 2>/dev/null || true)"
        pid_alive "$w" && return 0
        i=$((i + 1)); sleep 1
    done
    echo "lighttpd не подтвердил запуск" >&2
    return 1
}

start_daemon()
{
    d="$(cat "$DP" 2>/dev/null || true)"
    pid_alive "$d" && return 0
    "$DAEMON" >>"$ROOT/logs/broray-lightd.log" 2>&1 &
    i=0
    while [ "$i" -lt 5 ]; do
        d="$(cat "$DP" 2>/dev/null || true)"
        pid_alive "$d" && return 0
        i=$((i + 1)); sleep 1
    done
    echo "BROray-Light daemon не подтвердил запуск" >&2
    return 1
}

start()
{
    "$ROOT/bin/broray-runtime-prepare" || return 1
    mkdir -p "$ROOT/logs" "$ROOT/run" || return 1
    start_web || return 1
    start_daemon || return 1
}

stop()
{
    d="$(cat "$DP" 2>/dev/null || true)"
    pid_alive "$d" && kill "$d" 2>/dev/null || true
    w="$(cat "$WP" 2>/dev/null || true)"
    pid_alive "$w" && kill "$w" 2>/dev/null || true
    "$ROOT/bin/broray-xray-control" stop >/dev/null 2>&1 || true
    rm -f "$DP" "$WP"
}

restart(){ stop; sleep 1; start; }
status()
{
    d="$(cat "$DP" 2>/dev/null || true)"
    w="$(cat "$WP" 2>/dev/null || true)"
    pid_alive "$d" && pid_alive "$w"
}

case "${1:-}" in
    start|stop|restart|status) "$1" ;;
    *) echo 'Usage: S24broray-light {start|stop|restart|status}' >&2; exit 1 ;;
esac
''',0o755)

# Home snapshot includes Keenetic cached status.
write('app/bin/broray-home-snapshot', r'''#!/opt/bin/ash
ROOT="${BRORAY_ROOT:-/opt/broray-light}"; OUT="$ROOT/run/home-summary.json"; mkdir -p "$ROOT/run" "$ROOT/tmp"; servers="$($ROOT/bin/broray-servers summary 2>/dev/null || echo '{"count":0,"servers":[]}')"; subs="$($ROOT/bin/broray-subscriptions summary 2>/dev/null || echo '{"count":0}')"; xray="$(. "$ROOT/lib/xray.sh"; broray_xray_status_json_cached 2>/dev/null || echo '{}')"; keenetic="$(. "$ROOT/lib/keenetic-page.sh"; broray_keenetic_status_json_cached 2>/dev/null || echo '{}')"; conn="$(cat "$ROOT/run/connection-state.json" 2>/dev/null || echo '{}')"; failover="$(cat "$ROOT/run/server-auto-switch-state.json" 2>/dev/null || echo '{}')"; jq -n --argjson servers "$servers" --argjson subscriptions "$subs" --argjson xray "$xray" --argjson connection "$conn" --argjson failover "$failover" --argjson keenetic "$keenetic" --arg at "$(date '+%Y-%m-%dT%H:%M:%S%z')" '{schemaVersion:1,generatedAt:$at,servers:$servers,subscriptions:$subscriptions,xray:$xray,connection:$connection,failover:$failover,keenetic:$keenetic}' > "$OUT.$$" && mv "$OUT.$$" "$OUT"; cat "$OUT"
''',0o755)

# API common.
write('app/web-new/api/servers/common.sh', r'''#!/opt/bin/ash
. /opt/broray-light/web-new/api/auth-common.sh; . /opt/broray-light/lib/web-request-body.sh; . /opt/broray-light/lib/server-service.sh; . /opt/broray-light/lib/server-import.sh; . /opt/broray-light/lib/operation-lock.sh
broray_servers_api_lock(){ rc=0; broray_operation_lock_acquire "servers:${1:-action}" || rc=$?; case "$rc" in 0) trap 'broray_operation_lock_release >/dev/null 2>&1 || true' EXIT;; 2) broray_api_error "409 Conflict" "OPERATION_BUSY" "Другая операция уже выполняется.";; *) broray_api_error "500 Internal Server Error" "GLOBAL_LOCK_FAILED" "Не удалось получить блокировку.";; esac; }
broray_servers_api_read_body_to_file(){ f="$1"; rc=0; broray_web_request_body_to_file "$f" 65536 || rc=$?; [ "$rc" -eq 0 ] || broray_api_error "400 Bad Request" "REQUEST_BODY_INVALID" "Некорректное тело запроса."; jq -e 'type=="object"' "$f" >/dev/null 2>&1 || broray_api_error "400 Bad Request" "REQUEST_JSON_INVALID" "Ожидается JSON-объект."; }
broray_servers_api_body_field(){ printf '%s' "$1" | jq -r --arg f "$2" '.[$f]//empty'; }
broray_servers_api_run(){ out="/opt/broray-light/tmp/servers-api.$$.json"; err="$out.err"; mkdir -p /opt/broray-light/tmp; if "$@" >"$out" 2>"$err"; then payload="$(cat "$out")"; rm -f "$out" "$err"; broray_api_success "$payload"; else msg="$(tail -c 1000 "$err")"; rm -f "$out" "$err"; broray_api_error "400 Bad Request" "SERVER_OPERATION_FAILED" "Операция с сервером завершилась ошибкой." "$msg"; fi; }
''',0o755)
for rel in ['activate.cgi','check.cgi','delete.cgi','details.cgi','import.cgi','summary.cgi']:
 copy_adapt('app/web-new/api/servers/'+rel)
write('app/web-new/api/servers/auto-switch-save.cgi', r'''#!/opt/bin/ash
. /opt/broray-light/web-new/api/servers/common.sh; broray_api_require_method POST; broray_api_require_session; broray_servers_api_lock auto-switch-save; body="/opt/broray-light/tmp/auto-switch.$$.json"; trap 'rm -f "$body"; broray_operation_lock_release >/dev/null 2>&1 || true' EXIT; broray_servers_api_read_body_to_file "$body"; jq -e '(.enabled|type)=="boolean" and (.failureThreshold|type)=="number" and .failureThreshold>=1 and .failureThreshold<=10 and (.cooldownSeconds|type)=="number" and .cooldownSeconds>=0 and (.orderedServerIds|type)=="array" and (.excludedServerIds|type)=="array"' "$body" >/dev/null || broray_api_error "400 Bad Request" "FAILOVER_CONFIG_INVALID" "Некорректные настройки автопереключения."; jq '{schemaVersion:1,enabled,failureThreshold,cooldownSeconds,orderedServerIds,excludedServerIds,updatedAt:(now|todateiso8601)}' "$body" > /opt/broray-light/config/system/server-auto-switch.json.$$ && chmod 600 /opt/broray-light/config/system/server-auto-switch.json.$$ && mv /opt/broray-light/config/system/server-auto-switch.json.$$ /opt/broray-light/config/system/server-auto-switch.json; broray_api_success "$(cat /opt/broray-light/config/system/server-auto-switch.json)"
''',0o755)
write('app/web-new/api/servers/auto-switch-status.cgi', r'''#!/opt/bin/ash
. /opt/broray-light/web-new/api/auth-common.sh; broray_api_require_method GET; broray_api_require_session; cfg="$(cat /opt/broray-light/config/system/server-auto-switch.json 2>/dev/null || echo '{}')"; state="$(cat /opt/broray-light/run/server-auto-switch-state.json 2>/dev/null || echo '{}')"; broray_api_success "$(jq -n --argjson config "$cfg" --argjson state "$state" '{config:$config,state:$state}')"
''',0o755)

write('app/web-new/api/subscriptions/common.sh', r'''#!/opt/bin/ash
. /opt/broray-light/web-new/api/auth-common.sh; . /opt/broray-light/lib/web-request-body.sh; . /opt/broray-light/lib/subscription-service.sh; . /opt/broray-light/lib/operation-lock.sh
broray_subscriptions_api_lock(){ rc=0; broray_operation_lock_acquire "subscriptions:${1:-action}" || rc=$?; case "$rc" in 0) trap 'broray_operation_lock_release >/dev/null 2>&1 || true' EXIT;; 2) broray_api_error "409 Conflict" "OPERATION_BUSY" "Другая операция уже выполняется.";; *) broray_api_error "500 Internal Server Error" "GLOBAL_LOCK_FAILED" "Не удалось получить блокировку.";; esac; }
broray_subscriptions_api_read_body_to_file(){ f="$1"; rc=0; broray_web_request_body_to_file "$f" 65536 || rc=$?; [ "$rc" -eq 0 ] || broray_api_error "400 Bad Request" "REQUEST_BODY_INVALID" "Некорректное тело запроса."; jq -e 'type=="object"' "$f" >/dev/null 2>&1 || broray_api_error "400 Bad Request" "REQUEST_JSON_INVALID" "Ожидается JSON-объект."; }
broray_subscriptions_api_query(){ printf '%s' "${QUERY_STRING:-}" | tr '&' '\n' | awk -F= -v name="$1" '$1==name{sub(/^[^=]*=/,"");print;exit}'; }
broray_subscriptions_api_run(){ out="/opt/broray-light/tmp/sub-api.$$.json"; err="$out.err"; mkdir -p /opt/broray-light/tmp; if "$@" >"$out" 2>"$err"; then payload="$(cat "$out")"; rm -f "$out" "$err"; broray_api_success "$payload"; else msg="$(tail -c 1200 "$err")"; rm -f "$out" "$err"; broray_api_error "400 Bad Request" "SUBSCRIPTION_OPERATION_FAILED" "Операция с подпиской завершилась ошибкой." "$msg"; fi; }
''',0o755)
for rel in ['create.cgi','delete.cgi','details.cgi','list.cgi','refresh.cgi','servers.cgi','summary.cgi']:
 copy_adapt('app/web-new/api/subscriptions/'+rel)

# Xray web endpoints.
for rel in ['status.cgi','update-check.cgi','operation-status.cgi']: copy_adapt('app/web-new/api/xray/'+rel)
write('app/web-new/api/xray/update.cgi', r'''#!/opt/bin/ash
. /opt/broray-light/web-new/api/auth-common.sh; . /opt/broray-light/lib/xray-web-operation.sh; broray_api_require_method POST; broray_api_require_session; if payload="$(broray_xray_web_update 2>&1)"; then broray_api_success "$(jq -n --arg message "$payload" '{started:true,message:$message}')"; else broray_api_error "500 Internal Server Error" "XRAY_UPDATE_FAILED" "Обновление Xray завершилось ошибкой." "$payload"; fi
''',0o755)

# Keenetic API path fixes and locks.
for rel in ['app/web-new/api/keenetic/action-common.sh','app/web-new/api/keenetic/check-upstream.cgi','app/web-new/api/keenetic/create.cgi','app/web-new/api/keenetic/repair.cgi','app/web-new/api/keenetic/status.cgi','app/web-new/api/keenetic/sync-description.cgi']:
 p=TREE/rel; t=p.read_text().replace('/lib/routes-api-operation.sh','/lib/operation-lock.sh').replace('broray_routes_api_lock_acquire','broray_operation_lock_acquire').replace('broray_routes_api_lock_release','broray_operation_lock_release'); p.write_text(t)

# Product updater API is an explicit external control plane, built next stage.
write('app/web-new/api/broray/updater-api-common.sh', '#!/opt/bin/ash\n. /opt/broray-light/web-new/api/auth-common.sh\nBRORAY_LIGHT_UPDATER="${BRORAY_LIGHT_UPDATER:-/opt/libexec/broray-light-updater/broray-light-updater.sh}"\nbroray_light_updater_available(){ [ -x "$BRORAY_LIGHT_UPDATER" ]; }\n',0o755)
write('app/web-new/api/broray/info.cgi', '#!/opt/bin/ash\n. /opt/broray-light/web-new/api/auth-common.sh\nbroray_api_require_method GET; broray_api_require_session; broray_api_success "$(/opt/broray-light/bin/broray-system info)"\n',0o755)
write('app/web-new/api/broray/update-check.cgi', '#!/opt/bin/ash\n. /opt/broray-light/web-new/api/broray/updater-api-common.sh\nbroray_api_require_method GET; broray_api_require_session; broray_light_updater_available || broray_api_error "503 Service Unavailable" "UPDATER_UNAVAILABLE" "Обновитель BROray-Light недоступен."; if payload="$($BRORAY_LIGHT_UPDATER check --json 2>&1)"; then broray_api_success "$payload"; else broray_api_error "502 Bad Gateway" "UPDATE_CHECK_FAILED" "Проверка обновления не выполнена." "$payload"; fi\n',0o755)
write('app/web-new/api/broray/update-start.cgi', '#!/opt/bin/ash\n. /opt/broray-light/web-new/api/broray/updater-api-common.sh\nbroray_api_require_method POST; broray_api_require_session; broray_light_updater_available || broray_api_error "503 Service Unavailable" "UPDATER_UNAVAILABLE" "Обновитель BROray-Light недоступен."; if payload="$($BRORAY_LIGHT_UPDATER update --json 2>&1)"; then broray_api_success "$payload"; else broray_api_error "500 Internal Server Error" "UPDATE_FAILED" "Обновление BROray-Light завершилось ошибкой." "$payload"; fi\n',0o755)
write('app/web-new/api/broray/update-status.cgi', '#!/opt/bin/ash\n. /opt/broray-light/web-new/api/auth-common.sh\nbroray_api_require_method GET; broray_api_require_session; state=/opt/var/lib/broray-light-updater/state.json; [ -r "$state" ] && payload="$(cat "$state")" || payload=\x27{"state":"idle"}\x27; broray_api_success "$payload"\n',0o755)
write('app/web-new/api/home/summary.cgi', '#!/opt/bin/ash\n. /opt/broray-light/web-new/api/auth-common.sh\nbroray_api_require_method GET; broray_api_require_session; payload="$(/opt/broray-light/bin/broray-home-snapshot 2>/dev/null || cat /opt/broray-light/run/home-summary.json 2>/dev/null || echo \x27{}\x27)"; broray_api_success "$payload"\n',0o755)

# WebUI exactly three functional pages + login.
write('app/web-new/assets/css/allpage.css', ''':root{color-scheme:dark;--bg:#0c1110;--panel:#131b18;--line:#24332d;--text:#f3f7f5;--muted:#9dafaa;--brand:#32b379;--danger:#ff706c}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,sans-serif}header,main,nav{max-width:1100px;margin:auto}header{padding:22px 20px 10px;display:flex;align-items:center;gap:12px}header img{width:34px;height:34px}nav{display:flex;gap:8px;padding:0 20px 18px}nav a{color:var(--muted);text-decoration:none;padding:9px 13px;border:1px solid var(--line);border-radius:10px}nav a:hover,nav a.active{color:var(--text);border-color:var(--brand)}main{padding:0 20px 40px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px}.card h2{margin:0 0 12px;font-size:18px}.muted{color:var(--muted)}button,input,textarea{font:inherit}button{background:var(--brand);color:#07110d;border:0;border-radius:10px;padding:10px 14px;font-weight:700;cursor:pointer}button.secondary{background:transparent;color:var(--text);border:1px solid var(--line)}input,textarea{width:100%;background:#0d1412;color:var(--text);border:1px solid var(--line);border-radius:10px;padding:10px}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.stack>*+*{margin-top:10px}.status{font-weight:700}.error{color:var(--danger)}.login-body{min-height:100vh;display:grid;place-items:center}.login-page{width:min(430px,100%);padding:20px}.login-card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:24px}@media(max-width:600px){nav{overflow:auto}.grid{grid-template-columns:1fr}}\n''')
write('app/web-new/assets/js/app-shell.js', "document.addEventListener('DOMContentLoaded',()=>{const p=location.pathname.split('/').pop()||'home.html';document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('active',a.getAttribute('href')===p));});\n")
write('app/web-new/assets/js/home.js', '''async function j(url,opts){const r=await fetch(url,opts);const x=await r.json();if(r.status===401){location.replace('/');throw new Error('Требуется вход')}if(!r.ok||x.success===false||x.ok===false)throw new Error(x.error?.message||x.message||'Ошибка');return x.data??x}function text(id,v){const e=document.getElementById(id);if(e)e.textContent=v??'—'}async function refreshHome(){try{const d=await j('api/home/summary.cgi');text('activeServer',d.servers?.activeServerId||'Не выбран');text('connection',d.connection?.connected?'Работает':'Нет соединения');text('xray',d.xray?.version||d.xray?.installedVersion);text('failover',d.failover?.status||'Ожидание');const k=d.keenetic||{};text('keeneticState',k.health?.severity||k.state||k.status||'Не проверено')}catch(e){text('homeError',e.message)}}async function keeneticAction(a){try{await j('api/keenetic/'+a+'.cgi',{method:'POST'});await refreshHome()}catch(e){text('homeError',e.message)}}async function xrayCheck(){try{const d=await j('api/xray/update-check.cgi');text('xrayUpdate',d.updateAvailable?'Доступно обновление':'Актуальная версия')}catch(e){text('homeError',e.message)}}async function lightCheck(){try{const d=await j('api/broray/update-check.cgi');text('lightUpdate',d.updateAvailable?'Доступно обновление':'Актуальная версия')}catch(e){text('homeError',e.message)}}document.addEventListener('DOMContentLoaded',refreshHome);\n''')
write('app/web-new/assets/js/servers-auto-switch.js', '''async function loadFailoverConfig(){try{const d=await api('api/servers/auto-switch-status.cgi');const c=d.config||{};document.getElementById('failoverEnabled').checked=c.enabled===true;document.getElementById('failureThreshold').value=c.failureThreshold||3;document.getElementById('cooldownSeconds').value=c.cooldownSeconds??600;window.BROrayLightFailoverConfig=c}catch(e){window.BROrayLightFailoverConfig={}}}function moveServerCard(card,delta){const box=document.getElementById('servers');if(delta<0&&card.previousElementSibling)box.insertBefore(card,card.previousElementSibling);if(delta>0&&card.nextElementSibling)box.insertBefore(card.nextElementSibling,card)}async function saveFailover(){const cards=[...document.querySelectorAll('#servers>[data-server-id]')];const body={enabled:document.getElementById('failoverEnabled').checked,failureThreshold:Number(document.getElementById('failureThreshold').value||3),cooldownSeconds:Number(document.getElementById('cooldownSeconds').value||600),orderedServerIds:cards.map(x=>x.dataset.serverId),excludedServerIds:cards.filter(x=>x.querySelector('[data-exclude]')?.checked).map(x=>x.dataset.serverId)};await api('api/servers/auto-switch-save.cgi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});window.BROrayLightFailoverConfig=body}document.addEventListener('DOMContentLoaded',loadFailoverConfig);\n''')
write('app/web-new/assets/js/servers.js', '''async function api(url,opts){const r=await fetch(url,opts);const x=await r.json();if(r.status===401){location.replace('/');throw new Error('Требуется вход')}if(!r.ok||x.success===false||x.ok===false)throw new Error(x.error?.message||x.message||'Ошибка');return x.data??x}async function loadServers(){const d=await api('api/servers/summary.cgi');if(!window.BROrayLightFailoverConfig)await loadFailoverConfig();const c=window.BROrayLightFailoverConfig||{};const order=new Map((c.orderedServerIds||[]).map((id,i)=>[id,i]));const servers=[...(d.servers||[])].sort((a,b)=>(order.get(a.id)??99999)-(order.get(b.id)??99999));const excluded=new Set(c.excludedServerIds||[]);const box=document.getElementById('servers');box.innerHTML='';for(const s of servers){const row=document.createElement('div');row.className='card';row.dataset.serverId=s.id;row.innerHTML=`<b>${s.name||s.id}</b><div class="muted">${s.address}:${s.port} · VLESS${s.active?' · активен':''}</div><label class="muted"><input data-exclude type="checkbox" ${excluded.has(s.id)?'checked':''}> Не использовать в автопереключении</label><div class="row"><button class="secondary" data-a="up">↑</button><button class="secondary" data-a="down">↓</button><button data-a="check">Проверить</button><button data-a="activate">Активировать</button><button class="secondary" data-a="delete">Удалить</button></div>`;row.onclick=async e=>{const a=e.target.dataset.a;if(!a)return;if(a==='up'){moveServerCard(row,-1);return}if(a==='down'){moveServerCard(row,1);return}const map={check:'check.cgi',activate:'activate.cgi',delete:'delete.cgi'};await api('api/servers/'+map[a],{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:s.id,serverId:s.id})});await loadServers()};box.appendChild(row)}}async function importServer(){const uri=document.getElementById('uri').value.trim();await api('api/servers/import.cgi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uri})});document.getElementById('uri').value='';await loadServers()}document.addEventListener('DOMContentLoaded',loadServers);\n''')
write('app/web-new/assets/js/subscriptions.js', '''async function sapi(url,opts){const r=await fetch(url,opts);const x=await r.json();if(r.status===401){location.replace('/');throw new Error('Требуется вход')}if(!r.ok||x.success===false||x.ok===false)throw new Error(x.error?.message||x.message||'Ошибка');return x.data??x}async function loadSubs(){const d=await sapi('api/subscriptions/list.cgi');const box=document.getElementById('subscriptions');box.innerHTML='';for(const s of d.subscriptions||d.items||[]){const el=document.createElement('div');el.className='card';el.dataset.subscriptionId=s.id;el.innerHTML=`<b>${s.name||s.id}</b><div class="muted">${s.lastUpdatedAt||'Не обновлялась'}${s.lastError?' · '+s.lastError:''}</div><div class="row"><button data-a="refresh">Обновить</button><button class="secondary" data-a="delete">Удалить</button></div>`;el.onclick=async e=>{const a=e.target.dataset.a;if(!a)return;const ep=a==='refresh'?'refresh.cgi':'delete.cgi';await sapi('api/subscriptions/'+ep,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:s.id})});await loadSubs()};box.appendChild(el)}}async function addSub(){const url=document.getElementById('subUrl').value.trim();await sapi('api/subscriptions/create.cgi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'Подписка',url,updateImmediately:true})});document.getElementById('subUrl').value='';await loadSubs()}document.addEventListener('DOMContentLoaded',loadSubs);\n''')
common='<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="assets/images/branding/favicon.ico"><link rel="stylesheet" href="assets/css/allpage.css"><script defer src="assets/js/common.js"></script><script defer src="assets/js/app-shell.js"></script>'
nav='<nav><a href="home.html">Главная</a><a href="servers.html">Серверы</a><a href="subscriptions.html">Подписки</a></nav>'
write('app/web-new/index.html','''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BROray-Light — Вход</title><link rel="icon" href="assets/images/branding/favicon.ico"><link rel="stylesheet" href="assets/css/allpage.css"></head><body class="login-body"><main class="login-page"><section class="login-card stack"><div class="row"><img src="assets/images/branding/broray-logo-64.png" width="44" height="44"><div><h1>BROray-Light</h1><div class="muted">VLESS для Keenetic</div></div></div><h2>Вход</h2><p class="muted">Используйте логин и пароль интерфейса Keenetic.</p><form id="login-form" class="stack"><label>Логин<input id="login" autocomplete="username" required></label><label>Пароль<span class="row"><input id="password" type="password" autocomplete="current-password" required><button id="password-toggle" type="button" class="secondary">Показать</button></span></label><div id="login-error" class="error" hidden></div><button id="login-submit" type="submit"><span class="button-label">Войти</span></button></form><p class="muted">Пароль не сохраняется BROray-Light и проверяется KeeneticOS.</p></section></main><script src="assets/js/common.js"></script><script src="assets/js/login.js"></script></body></html>\n''')
write('app/web-new/home.html',f'''<!doctype html><html><head><title>BROray-Light — Главная</title>{common}<script defer src="assets/js/home.js"></script></head><body><header><img src="assets/images/branding/broray-logo-64.png"><h1>BROray-Light</h1></header>{nav}<main><div id="homeError" class="error"></div><div class="grid"><section class="card"><h2>Активный сервер</h2><div id="activeServer" class="status">—</div><div id="connection" class="muted">—</div></section><section class="card"><h2>Автопереключение</h2><div id="failover">—</div><a href="servers.html">Настроить порядок серверов</a></section><section class="card"><h2>Keenetic</h2><div id="keeneticState" class="status">—</div><div class="row"><button onclick="keeneticAction('create')">Настроить</button><button class="secondary" onclick="keeneticAction('repair')">Исправить</button><button class="secondary" onclick="refreshHome()">Обновить</button></div></section><section class="card"><h2>Xray</h2><div id="xray">—</div><div id="xrayUpdate" class="muted"></div><div class="row"><button onclick="xrayCheck()">Проверить обновление</button><button onclick="j('api/xray/update.cgi',{{method:'POST'}}).then(refreshHome)">Обновить</button></div></section><section class="card"><h2>BROray-Light</h2><div id="lightUpdate" class="muted">Обновления через единый updater</div><div class="row"><button onclick="lightCheck()">Проверить обновление</button><button onclick="j('api/broray/update-start.cgi',{{method:'POST'}}).then(refreshHome)">Обновить</button></div></section></div></main></body></html>''')
write('app/web-new/servers.html',f'''<!doctype html><html><head><title>BROray-Light — Серверы</title>{common}<script defer src="assets/js/servers-auto-switch.js"></script><script defer src="assets/js/servers.js"></script></head><body><header><img src="assets/images/branding/broray-logo-64.png"><h1>Серверы</h1></header>{nav}<main><section class="card stack"><h2>Добавить VLESS</h2><textarea id="uri" rows="3" placeholder="vless://..."></textarea><button onclick="importServer()">Добавить</button></section><section class="card"><h2>Автопереключение</h2><div class="row"><label><input id="failoverEnabled" type="checkbox"> Включено</label><label>Ошибок <input id="failureThreshold" type="number" min="1" max="10" value="3"></label><label>Cooldown, сек <input id="cooldownSeconds" type="number" min="0" value="600"></label><button onclick="saveFailover()">Сохранить</button></div></section><div id="servers" class="grid"></div></main></body></html>''')
write('app/web-new/subscriptions.html',f'''<!doctype html><html><head><title>BROray-Light — Подписки</title>{common}<script defer src="assets/js/subscriptions.js"></script></head><body><header><img src="assets/images/branding/broray-logo-64.png"><h1>Подписки</h1></header>{nav}<main><section class="card stack"><h2>Добавить подписку</h2><input id="subUrl" placeholder="https://..."><button onclick="addSub()">Добавить</button><div class="muted">Импортируются только VLESS; остальные протоколы пропускаются.</div></section><div id="subscriptions" class="grid"></div></main></body></html>''')
write('app/web-new/build.json',json.dumps({'product':'BROray-Light','version':'0.1.0-dev','baseStable':'3.0.0-r23','baseCandidate':'3.0.0-r23c02','pages':['home','servers','subscriptions'],'theme':'brand'},indent=2)+'\n')
write('app/web-new/manifest.json',json.dumps({'name':'BROray-Light','short_name':'BROray-Light','start_url':'home.html','display':'standalone','theme_color':'#0c1110','background_color':'#0c1110'},indent=2)+'\n')

# Config seeds/defaults.
settings={'schemaVersion':1,'listenAddress':None,'socksPort':2080,'logLevel':'warning','autoRestart':True,'testBeforeApply':True,'backupBeforeApply':True}
failover={'schemaVersion':1,'enabled':False,'failureThreshold':3,'cooldownSeconds':600,'orderedServerIds':[],'excludedServerIds':[],'updatedAt':None}
write('state-seed/config/system/settings.json',json.dumps(settings,indent=2)+'\n'); write('state-seed/config/system/server-auto-switch.json',json.dumps(failover,indent=2)+'\n')
write('state-seed/config/lighttpd.conf','''server.modules = ( "mod_cgi" )\nserver.document-root = "/opt/broray-light/web-new"\nserver.bind = "127.0.0.1"\nserver.port = 8080\nserver.max-request-size = 5120\nserver.pid-file = "/opt/broray-light/run/lighttpd.pid"\nserver.errorlog = "/opt/broray-light/logs/lighttpd-error.log"\nindex-file.names = ( "index.html" )\nmimetype.assign = ( ".html" => "text/html; charset=utf-8", ".css" => "text/css; charset=utf-8", ".js" => "application/javascript; charset=utf-8", ".json" => "application/json; charset=utf-8", ".png" => "image/png", ".ico" => "image/x-icon" )\ncgi.assign = ( ".cgi" => "" )\nstatic-file.exclude-extensions = ( ".cgi" )\n''')
write('state-seed/config/version','0.1.0-dev\n'); (TREE/'app/share/defaults').mkdir(parents=True,exist_ok=True)
for srcname,dstname in [('state-seed/config/system/settings.json','app/share/defaults/settings.json'),('state-seed/config/system/server-auto-switch.json','app/share/defaults/server-auto-switch.json'),('state-seed/config/lighttpd.conf','app/share/defaults/lighttpd.conf'),('state-seed/config/version','app/share/defaults/version')]: shutil.copy2(TREE/srcname,TREE/dstname)

# Release metadata.
manifest={'schemaVersion':1,'product':'BROray-Light','version':'0.1.0-dev','baseStable':'3.0.0-r23','baseCandidate':'3.0.0-r23c02','protocols':['VLESS'],'webuiPages':['home','servers','subscriptions'],'services':['S24broray-light'],'excluded':['routes','DNS-over-TLS','VMess','Trojan','Shadowsocks','Hysteria2','scheduledQualityRefresh','serverRatings','qualityHistory','manualXrayMaintenance','WebUIRemoveRestore']}
write('release.json',json.dumps(manifest,indent=2)+'\n'); write('app/share/release/manifest.json',json.dumps(manifest,indent=2)+'\n')
write('app/share/release/requirements-traceability.json',json.dumps({'schemaVersion':1,'requirements':{'VLESS_ONLY':'R0008','THREE_PAGES':'R0008','DETERMINISTIC_FAILOVER':'R0008','KEENETIC_HOME':'R0008','SINGLE_PRIMARY_SERVICE':'R0008','UPDATER_V5_SEMANTICS':'NEXT_STAGE'}},indent=2)+'\n')
write('app/share/release/contracts/source-admission-contract.json',json.dumps({'schemaVersion':1,'baseApplicationSha256':'69679f6d7339b856faf28f69cb1800254984e5400201fe97247011ab166c3f85'},indent=2)+'\n')
write('app/share/release/contracts/capability-contract.json',json.dumps({'schemaVersion':1,'required':['Entware','jq','curl','lighttpd','lighttpd-mod-cgi','Keenetic proxy capability','Keenetic opkg capability']},indent=2)+'\n')
write('app/share/release/contracts/page-workflow-contract.json',json.dumps({'schemaVersion':1,'pages':['home','servers','subscriptions']},indent=2)+'\n')
write('app/share/release/contracts/physical-write-certification-contract.json',json.dumps({'schemaVersion':1,'writeProfiles':['proxy-interface'],'failClosed':True},indent=2)+'\n')
write('app/share/release/contracts/space-contract.json',json.dumps({'schemaVersion':1,'status':'TO_BE_MEASURED_FROM_FIRST_REPRODUCIBLE_PACKAGE'},indent=2)+'\n')
write('app/share/release/RELEASE-REQUIREMENTS.md','# BROray-Light release requirements\n\nVLESS only; exactly three functional pages; deterministic failover without ratings/history; r23 Keenetic ownership protections; one primary application service; updater-v5 releaseId/atomic/rollback semantics remain mandatory for the next stage.\n')
write('app/share/release/UPDATER-ARCHITECTURE.md','# Updater architecture\n\nNext stage forks updater-v5 semantics for independent BROray-Light identity and paths. R0008 intentionally contains only the application-side API contract.\n')

# Remove copied modules/UI not needed after dependency pruning.
for rel in ['app/lib/home-snapshot.sh','app/lib/lighttpd-guard.sh','app/lib/server-command.sh','app/web-new/assets/js/dialogs.js','app/web-new/assets/js/icons.js','app/web-new/assets/icons/broray-icons.svg']:
 p=TREE/rel
 if p.exists(): p.unlink()
# Old standalone init not copied; ensure one init only.
for p in (TREE/'init').glob('*'):
 if p.name!='S24broray-light': p.unlink()

# Final generic route-lock cleanup in adapted files.
for p in TREE.rglob('*'):
 if not p.is_file() or not is_text(p): continue
 try: txt=p.read_text()
 except UnicodeDecodeError: continue
 txt=txt.replace('/lib/routes-api-operation.sh','/lib/operation-lock.sh').replace('broray_routes_api_lock_acquire','broray_operation_lock_acquire').replace('broray_routes_api_lock_release','broray_operation_lock_release').replace('BROray-Light-Light','BROray-Light')
 p.write_text(txt)

# Provenance/treatment execution, excluding generated checksum/provenance files themselves.
actions=[]
for r in mapobj['records']:
 p=TREE/r['path']; actual='PRESENT' if p.exists() else 'ABSENT'
 if r['treatment']=='DROP': execution='DROP'
 elif p.exists(): execution='RETAINED_OR_ADAPTED'
 else: execution='OMITTED_AFTER_DEPENDENCY_PRUNE'
 actions.append({'path':r['path'],'plannedTreatment':r['treatment'],'execution':execution,'finalPresence':actual,'donorSha256':r['sha256'],'reason':r['reason']})
write('TREATMENT-EXECUTION.json',json.dumps({'schemaVersion':1,'baseCandidate':'3.0.0-r23c02','records':actions},indent=2,sort_keys=True)+'\n')

# Checksums/provenance.
def files_for_hash(): return [p for p in sorted(TREE.rglob('*')) if p.is_file() and p.name not in {'SHA256SUMS','SOURCE-PROVENANCE.json'}]
prov=[]
for p in files_for_hash():
 b=p.read_bytes(); prov.append({'path':p.relative_to(TREE).as_posix(),'size':len(b),'sha256':hashlib.sha256(b).hexdigest()})
write('SOURCE-PROVENANCE.json',json.dumps({'schemaVersion':1,'checkpoint':'R0008','baseStable':'3.0.0-r23','baseCandidate':'3.0.0-r23c02','baseApplicationSha256':'69679f6d7339b856faf28f69cb1800254984e5400201fe97247011ab166c3f85','files':prov},indent=2,sort_keys=True)+'\n')
lines=[]
for p in sorted(TREE.rglob('*')):
 if p.is_file() and p.name!='SHA256SUMS': lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(TREE).as_posix()}")
write('SHA256SUMS','\n'.join(lines)+'\n')
summary={'schemaVersion':1,'stage':'BUILD_LIGHT_SOURCE_TREE_FROM_R23_TREATMENT_MAP','status':'BUILT_PENDING_FINAL_VALIDATION','baseStable':'3.0.0-r23','baseCandidate':'3.0.0-r23c02','sourceFiles':sum(1 for p in TREE.rglob('*') if p.is_file()),'sourceBytes':sum(p.stat().st_size for p in TREE.rglob('*') if p.is_file())}
(OUT/'BUILD-SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
