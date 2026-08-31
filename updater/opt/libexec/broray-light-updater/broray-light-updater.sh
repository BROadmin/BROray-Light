#!/opt/bin/ash

set -u

UPDATER_VERSION=5
UPDATER_ENGINE='broray-light-updater/5-light1'
ROOT_PREFIX="${BRORAY_LIGHT_ROOT_PREFIX:-}"
APP_ROOT="${BRORAY_LIGHT_APP_ROOT:-$ROOT_PREFIX/opt/broray-light}"
STATE_ROOT="${BRORAY_LIGHT_UPDATER_STATE_ROOT:-$ROOT_PREFIX/opt/var/lib/broray-light-updater}"
OPERATIONS_ROOT="${BRORAY_LIGHT_OPERATIONS_ROOT:-$ROOT_PREFIX/opt/var/lib/broray-light/operations}"
REQUEST_LOCK="${BRORAY_LIGHT_REQUEST_LOCK:-$ROOT_PREFIX/opt/var/lock/broray-light-updater/request.lock}"
GLOBAL_LOCK="${BRORAY_LIGHT_GLOBAL_LOCK:-$ROOT_PREFIX/opt/var/lock/broray-light/global-operation.lock}"
WORK_ROOT="${BRORAY_LIGHT_WORK_ROOT:-$ROOT_PREFIX/tmp/broray-light-updater}"
INDEX_URL="${BRORAY_LIGHT_RELEASE_INDEX_URL:-}"
SIGNATURE_BIN="${BRORAY_LIGHT_SIGNATURE_BIN:-$ROOT_PREFIX/opt/libexec/broray-light-updater/minisign}"
PUBLIC_KEY="${BRORAY_LIGHT_PUBLIC_KEY:-$ROOT_PREFIX/opt/share/broray-light/release.pub}"
SERVICE_INIT="${BRORAY_LIGHT_SERVICE_INIT:-$ROOT_PREFIX/opt/etc/init.d/S24broray-light}"
SERVICE_HOOK="${BRORAY_LIGHT_SERVICE_HOOK:-}"
HEALTH_HOOK="${BRORAY_LIGHT_HEALTH_HOOK:-}"
TEST_MODE="${BRORAY_LIGHT_TEST_MODE:-0}"
STATE_FILE="$STATE_ROOT/state.json"
TRANSACTION_FILE="$STATE_ROOT/transaction.json"
CURRENT_PATH="$APP_ROOT/current"
RELEASES_ROOT="$APP_ROOT/releases"
UPDATE_REQUEST_ACQUIRED=false
UPDATE_GLOBAL_ACQUIRED=false

now()
{
    date '+%Y-%m-%dT%H:%M:%S%z'
}

die()
{
    printf 'ERROR: %s\n' "$*" >&2
    return 1
}

valid_id()
{
    local invalid
    [ -n "$1" ] || return 1
    invalid="$(printf '%s' "$1" | tr -d 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-')"
    [ -z "$invalid" ]
}

valid_sha256()
{
    [ "$(printf '%s' "$1" | wc -c | tr -d ' ')" -eq 64 ] || return 1
    [ -z "$(printf '%s' "$1" | tr -d '0123456789abcdefABCDEF')" ]
}

release_parts()
{
    local value base revision old_ifs major minor patch
    value="$1"
    case "$value" in
        *-r*) ;;
        *) return 1 ;;
    esac
    base="${value%-r*}"
    revision="${value##*-r}"
    case "$revision" in ''|*[!0-9]*) return 1 ;; esac
    old_ifs="$IFS"
    IFS='.'
    set -- $base
    IFS="$old_ifs"
    [ "$#" -eq 3 ] || return 1
    major="$1"; minor="$2"; patch="$3"
    case "$major:$minor:$patch" in *[!0-9:]*) return 1 ;; esac
    printf '%s %s %s %s\n' "$major" "$minor" "$patch" "$revision"
}

release_relation()
{
    local installed available installed_parts available_parts old_ifs i1 i2 i3 i4 a1 a2 a3 a4
    installed="$1"; available="$2"
    [ -n "$installed" ] || { printf '%s\n' absent; return 0; }
    installed_parts="$(release_parts "$installed")" || { printf '%s\n' uncomparable; return 0; }
    available_parts="$(release_parts "$available")" || { printf '%s\n' uncomparable; return 0; }
    old_ifs="$IFS"; IFS=' '
    set -- $installed_parts; i1="$1"; i2="$2"; i3="$3"; i4="$4"
    set -- $available_parts; a1="$1"; a2="$2"; a3="$3"; a4="$4"
    IFS="$old_ifs"
    for pair in "$i1:$a1" "$i2:$a2" "$i3:$a3" "$i4:$a4"; do
        [ "${pair%%:*}" -lt "${pair#*:}" ] && { printf '%s\n' newer; return 0; }
        [ "${pair%%:*}" -gt "${pair#*:}" ] && { printf '%s\n' older; return 0; }
    done
    printf '%s\n' equal
}

atomic_text()
{
    local destination temporary
    destination="$1"; temporary="$destination.$$"
    cat > "$temporary" || { rm -f "$temporary"; return 1; }
    mv -f "$temporary" "$destination"
}

state_write()
{
    local state stage message error_code
    state="$1"; stage="$2"; message="$3"; error_code="${4:-}"
    mkdir -p "$STATE_ROOT" || return 1
    jq -n --arg state "$state" --arg stage "$stage" --arg message "$message" \
        --arg errorCode "$error_code" --arg at "$(now)" --arg engine "$UPDATER_ENGINE" '
        {schemaVersion:1,state:$state,stage:$stage,message:$message,
         errorCode:(if $errorCode=="" then null else $errorCode end),updatedAt:$at,engine:$engine}' |
        atomic_text "$STATE_FILE"
}

owner_alive()
{
    case "$1" in ''|*[!0-9]*) return 1 ;; esac
    kill -0 "$1" 2>/dev/null
}

lock_acquire()
{
    local lock operation owner
    lock="$1"; operation="$2"
    mkdir -p "${lock%/*}" || return 1
    if mkdir "$lock" 2>/dev/null; then
        printf '%s\n' "$$" > "$lock/pid" || return 1
        printf '%s\n' "$operation" > "$lock/operation" || return 1
        return 0
    fi
    [ -d "$lock" ] && [ ! -L "$lock" ] || return 3
    owner="$(cat "$lock/pid" 2>/dev/null || true)"
    owner_alive "$owner" && return 2
    rm -rf "$lock" || return 1
    mkdir "$lock" 2>/dev/null || return 2
    printf '%s\n' "$$" > "$lock/pid" || return 1
    printf '%s\n' "$operation" > "$lock/operation" || return 1
}

lock_release()
{
    local lock owner
    lock="$1"; [ -d "$lock" ] || return 0
    owner="$(cat "$lock/pid" 2>/dev/null || true)"
    [ "$owner" = "$$" ] || return 1
    rm -rf "$lock"
}

update_locks_cleanup()
{
    if [ "$UPDATE_GLOBAL_ACQUIRED" = true ]; then
        lock_release "$GLOBAL_LOCK" >/dev/null 2>&1 || true
        UPDATE_GLOBAL_ACQUIRED=false
    fi
    if [ "$UPDATE_REQUEST_ACQUIRED" = true ]; then
        lock_release "$REQUEST_LOCK" >/dev/null 2>&1 || true
        UPDATE_REQUEST_ACQUIRED=false
    fi
}

coownership_clear()
{
    [ ! -e "$ROOT_PREFIX/opt/broray" ] || return 1
    [ ! -e "$ROOT_PREFIX/opt/etc/init.d/S24broray" ] || return 1
    [ ! -e "$ROOT_PREFIX/opt/var/lock/broray/global-operation.lock" ] || return 1
}

ensure_layout()
{
    mkdir -p "$STATE_ROOT" "$OPERATIONS_ROOT" "$RELEASES_ROOT" "$WORK_ROOT" \
        "${REQUEST_LOCK%/*}" "${GLOBAL_LOCK%/*}"
}

fetch_file()
{
    local url output
    url="$1"; output="$2"
    case "$url" in
        https://*) ;;
        file://*) [ "$TEST_MODE" = 1 ] || return 1 ;;
        *) return 1 ;;
    esac
    rm -f "$output"
    curl -q --proto '=https,file' --proto-redir '=https' --tlsv1.2 \
        --connect-timeout 15 --max-time 600 --retry 2 -fsSL \
        -H 'Cache-Control: no-cache, no-store' -H 'Accept-Encoding: identity' \
        "$url" -o "$output"
}

signature_valid()
{
    local message signature
    message="$1"; signature="$2"
    [ -x "$SIGNATURE_BIN" ] && [ -r "$PUBLIC_KEY" ] || return 1
    "$SIGNATURE_BIN" -Vm "$message" -x "$signature" -p "$PUBLIC_KEY" -q >/dev/null 2>&1
}

index_valid()
{
    local index
    index="$1"
    jq -e --arg architecture 'aarch64-3.10' '
      .schemaVersion == 1 and .product == "BROray-Light" and .channel == "internal-r0009" and
      .candidate.architecture == $architecture and
      (.candidate.releaseId | type == "string") and
      (.candidate.candidateId | type == "string") and
      (.candidate.bundle.url | type == "string") and
      (.candidate.bundle.sizeBytes | type == "number" and . > 0 and floor == .) and
      (.candidate.bundle.sha256 | type == "string") and
      (.candidate.appSlot.fileCount | type == "number" and . > 0 and floor == .) and
      (.candidate.appSlot.logicalBytes | type == "number" and . > 0 and floor == .)
    ' "$index" >/dev/null 2>&1 || return 1
    valid_id "$(jq -r '.candidate.releaseId' "$index")" || return 1
    valid_id "$(jq -r '.candidate.candidateId' "$index")" || return 1
    valid_sha256 "$(jq -r '.candidate.bundle.sha256' "$index")"
}

current_release()
{
    [ -L "$CURRENT_PATH" ] || return 1
    [ -r "$CURRENT_PATH/release.json" ] || return 1
    jq -er '.releaseId' "$CURRENT_PATH/release.json"
}

fetch_verified_index()
{
    local index signature
    [ -n "$INDEX_URL" ] || return 1
    index="$WORK_ROOT/release.json"; signature="$index.minisig"
    fetch_file "$INDEX_URL" "$index" || return 1
    fetch_file "$INDEX_URL.minisig" "$signature" || return 1
    signature_valid "$index" "$signature" || return 1
    index_valid "$index" || return 1
    printf '%s\n' "$index"
}

archive_safe()
{
    local archive listing line
    archive="$1"; listing="$WORK_ROOT/archive.list"
    tar -tzf "$archive" > "$listing" 2>/dev/null || return 1
    [ -s "$listing" ] || return 1
    while IFS= read -r line; do
        line="$(printf '%s' "$line" | tr -d '\r')"
        case "$line" in
            /*|*\\*|../*|*/../*|*/..|..|'') return 1 ;;
            app|app/*|release.json|SLOT-MANIFEST.json|APP-SHA256SUMS) ;;
            *) return 1 ;;
        esac
    done < "$listing" || return 1
    tar -tvzf "$archive" 2>/dev/null | while IFS= read -r line; do
        case "$line" in -*) ;; d*) ;; *) exit 1 ;; esac
    done
}

slot_valid()
{
    local slot expected_release expected_candidate expected_files expected_bytes actual_files actual_bytes unsafe
    slot="$1"; expected_release="$2"; expected_candidate="$3"; expected_files="$4"; expected_bytes="$5"
    [ -d "$slot/app/bin" ] && [ -d "$slot/app/lib" ] && [ -d "$slot/app/share" ] &&
        [ -d "$slot/app/web-new" ] && [ -x "$slot/app/bin/broray" ] &&
        [ -x "$slot/app/bin/broray-runtime-prepare" ] && [ -r "$slot/release.json" ] &&
        [ -r "$slot/SLOT-MANIFEST.json" ] && [ -r "$slot/APP-SHA256SUMS" ] || return 1
    unsafe="$(find "$slot" \( -type l -o -type b -o -type c -o -type p -o -type s \) -print -quit 2>/dev/null)"
    [ -z "$unsafe" ] || return 1
    (cd "$slot" && sha256sum -c APP-SHA256SUMS >/dev/null 2>&1) || return 1
    jq -e --arg release "$expected_release" --arg candidate "$expected_candidate" \
        '.product=="BROray-Light" and .releaseId==$release and .candidateId==$candidate' \
        "$slot/release.json" >/dev/null 2>&1 || return 1
    actual_files="$(find "$slot/app" -type f | wc -l | tr -d ' ')"
    actual_bytes="$(find "$slot/app" -type f -exec wc -c {} \; | awk '{s += $1} END {print s + 0}')"
    [ "$actual_files" = "$expected_files" ] && [ "$actual_bytes" = "$expected_bytes" ]
}

service_call()
{
    if [ -n "$SERVICE_HOOK" ]; then "$SERVICE_HOOK" "$1" "$APP_ROOT"; else "$SERVICE_INIT" "$1"; fi
}

slot_health()
{
    local release
    release="$1"
    [ "$(current_release 2>/dev/null || true)" = "$release" ] || return 1
    [ -x "$APP_ROOT/bin/broray" ] || return 1
    if [ -n "${BRORAY_LIGHT_XRAY_EXECUTABLE_HOOK:-}" ]; then
        "$BRORAY_LIGHT_XRAY_EXECUTABLE_HOOK" "$APP_ROOT/runtime/xray" || return 1
    else
        [ -x "$APP_ROOT/runtime/xray" ] || return 1
    fi
    if [ -n "$HEALTH_HOOK" ]; then "$HEALTH_HOOK" "$release" "$APP_ROOT"; else service_call status; fi
}

switch_current()
{
    local release temporary
    release="$1"; temporary="$APP_ROOT/.current.$$.new"
    rm -f "$temporary"
    ln -s "releases/$release" "$temporary" || return 1
    mv -fT "$temporary" "$CURRENT_PATH"
}

transaction_write()
{
    local phase previous target
    phase="$1"; previous="$2"; target="$3"
    jq -n --arg phase "$phase" --arg previous "$previous" --arg target "$target" --arg at "$(now)" \
        '{schemaVersion:1,phase:$phase,previousRelease:$previous,targetRelease:$target,updatedAt:$at}' |
        atomic_text "$TRANSACTION_FILE"
}

rollback_to()
{
    local previous
    previous="$1"
    service_call stop >/dev/null 2>&1 || true
    switch_current "$previous" || return 1
    printf '%s\n' "$previous" | atomic_text "$APP_ROOT/config/version" || return 1
    service_call start || return 1
    slot_health "$previous"
}

command_check()
{
    local index installed available relation update_available downgrade_refused
    ensure_layout || return 1
    index="$(fetch_verified_index)" || { state_write error verify-index 'Signed release index verification failed.' INDEX_VERIFY_FAILED || true; return 1; }
    installed="$(current_release 2>/dev/null || true)"
    available="$(jq -r '.candidate.releaseId' "$index")"
    relation="$(release_relation "$installed" "$available")"
    [ "$relation" != uncomparable ] || return 1
    update_available=false; downgrade_refused=false
    [ "$relation" = newer ] && update_available=true
    [ "$relation" = older ] && downgrade_refused=true
    jq -n --arg installed "$installed" --arg available "$available" --arg relation "$relation" \
        --argjson updateAvailable "$update_available" --argjson downgradeRefused "$downgrade_refused" \
        '{ok:true,installedReleaseId:(if $installed=="" then null else $installed end),availableReleaseId:$available,
          relation:$relation,updateAvailable:$updateAvailable,downgradeRefused:$downgradeRefused,
          sameVersionPolicy:"NO_OP_SUCCESS"}'
}

command_update()
{
    local index installed available candidate relation bundle_url bundle_size bundle_sha bundle actual_size actual_sha
    local staging final previous files bytes rollback_ok
    ensure_layout || return 1
    coownership_clear || { state_write error admission 'Full BROray ownership is present or ambiguous.' COOWNERSHIP_CONFLICT || true; return 1; }
    lock_acquire "$REQUEST_LOCK" update || { state_write error request-lock 'Updater request lock is busy or unsafe.' REQUEST_LOCKED || true; return 1; }
    UPDATE_REQUEST_ACQUIRED=true
    trap 'update_locks_cleanup' 0 1 2 15
    if ! lock_acquire "$GLOBAL_LOCK" update; then state_write error global-lock 'Global operation lock is busy or unsafe.' GLOBAL_LOCKED || true; return 1; fi
    UPDATE_GLOBAL_ACQUIRED=true
    state_write running verify-index 'Verifying signed release index.' || return 1
    index="$(fetch_verified_index)" || { state_write error verify-index 'Signed release index verification failed.' INDEX_VERIFY_FAILED || true; return 1; }
    installed="$(current_release 2>/dev/null || true)"; available="$(jq -r '.candidate.releaseId' "$index")"
    candidate="$(jq -r '.candidate.candidateId' "$index")"; relation="$(release_relation "$installed" "$available")"
    case "$relation" in
        equal) state_write success no-op 'Installed release equals signed release; no mutation.'; command_check; update_locks_cleanup; trap - 0 1 2 15; return 0 ;;
        older) state_write error decision 'Installed release is newer; downgrade refused.' DOWNGRADE_REFUSED || true; return 20 ;;
        newer) ;;
        *) state_write error decision 'Installed release is absent or uncomparable.' RELEASE_UNCOMPARABLE || true; return 1 ;;
    esac
    bundle_url="$(jq -r '.candidate.bundle.url' "$index")"; bundle_size="$(jq -r '.candidate.bundle.sizeBytes' "$index")"
    bundle_sha="$(jq -r '.candidate.bundle.sha256' "$index")"; files="$(jq -r '.candidate.appSlot.fileCount' "$index")"
    bytes="$(jq -r '.candidate.appSlot.logicalBytes' "$index")"; bundle="$WORK_ROOT/app.tar.gz"
    state_write running download 'Downloading verified application slot.' || return 1
    fetch_file "$bundle_url" "$bundle" || { state_write error download 'Application slot download failed.' DOWNLOAD_FAILED || true; return 1; }
    actual_size="$(wc -c < "$bundle" | tr -d ' ')"; actual_sha="$(sha256sum "$bundle" | awk 'NR==1{print $1}')"
    [ "$actual_size" = "$bundle_size" ] && [ "$actual_sha" = "$bundle_sha" ] || {
        state_write error verify-bundle 'Application archive size or SHA-256 mismatch.' BUNDLE_VERIFY_FAILED || true; return 1; }
    archive_safe "$bundle" || { state_write error safe-extract 'Application archive contains unsafe paths or member types.' ARCHIVE_UNSAFE || true; return 1; }
    staging="$RELEASES_ROOT/.stage-$available-$$"; final="$RELEASES_ROOT/$available"
    [ ! -e "$final" ] || { state_write error stage 'Target release slot already exists.' TARGET_EXISTS || true; return 1; }
    mkdir -p "$staging" || return 1
    tar -xzf "$bundle" -C "$staging" || { rm -rf "$staging"; state_write error extract 'Application archive extraction failed.' EXTRACT_FAILED || true; return 1; }
    slot_valid "$staging" "$available" "$candidate" "$files" "$bytes" || {
        rm -rf "$staging"; state_write error validate-slot 'Extracted application slot validation failed.' SLOT_INVALID || true; return 1; }
    mv "$staging" "$final" || return 1
    previous="$installed"
    transaction_write prepared "$previous" "$available" || return 1
    service_call stop || { state_write error stop 'Primary service did not stop.' SERVICE_STOP_FAILED || true; return 1; }
    switch_current "$available" || { service_call start >/dev/null 2>&1 || true; state_write error switch 'Atomic app-slot switch failed.' SWITCH_FAILED || true; return 1; }
    printf '%s\n' "$available" | atomic_text "$APP_ROOT/config/version" || {
        rollback_to "$previous" >/dev/null 2>&1 || true; state_write error switch 'Version state update failed; rollback attempted.' VERSION_STATE_FAILED || true; return 1; }
    transaction_write target-active "$previous" "$available" || return 1
    if ! service_call start || ! slot_health "$available"; then
        rollback_ok=false; rollback_to "$previous" && rollback_ok=true
        if [ "$rollback_ok" = true ]; then
            transaction_write rolled-back "$previous" "$available" || true
            state_write error rollback 'Post-switch health failed; previous-good slot restored.' POST_SWITCH_HEALTH_FAILED || true
        else
            state_write error rollback-failed 'Post-switch health and automatic rollback failed.' ROLLBACK_FAILED || true
        fi
        return 1
    fi
    transaction_write committed "$previous" "$available" || return 1
    state_write success complete 'Application update completed and passed health gate.' || return 1
    rm -f "$TRANSACTION_FILE"
    update_locks_cleanup; trap - 0 1 2 15
    jq -n --arg previous "$previous" --arg installed "$available" '{ok:true,updated:true,previousReleaseId:$previous,installedReleaseId:$installed}'
}

command_recover()
{
    local phase previous target current
    ensure_layout || return 1
    [ -r "$TRANSACTION_FILE" ] || return 0
    phase="$(jq -r '.phase // empty' "$TRANSACTION_FILE" 2>/dev/null || true)"
    previous="$(jq -r '.previousRelease // empty' "$TRANSACTION_FILE" 2>/dev/null || true)"
    target="$(jq -r '.targetRelease // empty' "$TRANSACTION_FILE" 2>/dev/null || true)"
    valid_id "$previous" && valid_id "$target" || return 1
    current="$(current_release 2>/dev/null || true)"
    case "$phase:$current" in
        committed:*|rolled-back:*) rm -f "$TRANSACTION_FILE"; return 0 ;;
        target-active:$target)
            if slot_health "$target"; then rm -f "$TRANSACTION_FILE"; return 0; fi
            rollback_to "$previous" && rm -f "$TRANSACTION_FILE" && return 0
            return 1 ;;
        prepared:$previous) rm -f "$TRANSACTION_FILE"; return 0 ;;
        *) return 1 ;;
    esac
}

case "${1:-}" in
    check) command_check ;;
    update) command_update ;;
    status) [ -r "$STATE_FILE" ] && cat "$STATE_FILE" || printf '%s\n' '{"state":"idle"}' ;;
    recover) command_recover ;;
    relation) release_relation "${2:-}" "${3:-}" ;;
    *) echo 'Usage: broray-light-updater.sh {check|update|status|recover|relation}' >&2; exit 2 ;;
esac
