#!/opt/bin/ash
# Read-only admission for the one supported legacy transition. The caller must
# first source runtime-ram.sh (definitions only; do NOT prepare old namespaces).
# Trust is inherited from the exact live r1 updater's signed-index transaction.
# No environment variable authorizes bypassing either legacy lock.

brl_r1_refuse()
{
    printf 'BRORAY_LIGHT_MIGRATION_REFUSED:%s\n' "$1" >&2
    return 1
}

brl_r1_regular()
{
    [ -f "$1" ] && [ ! -L "$1" ] || return 1
    case "$(stat -c '%u:%a' "$1" 2>/dev/null)" in 0:600|0:644|0:700|0:755) ;; *) return 1 ;; esac
}

brl_r1_directory()
{
    [ -d "$1" ] && [ ! -L "$1" ] || return 1
    case "$(stat -c '%u:%a' "$1" 2>/dev/null)" in 0:700|0:755) ;; *) return 1 ;; esac
}

brl_r1_lock_shape()
{
    brl_r1_directory "$1" && brl_r1_regular "$1/pid" &&
        brl_r1_regular "$1/operation" || return 1
    [ "$(cat "$1/operation")" = update ] || return 1
    [ "$(find "$1" -mindepth 1 -maxdepth 1 -print | wc -l | tr -d ' ')" = 2 ]
}

brl_r1_owner_ancestor()
{
    local cursor raw parent steps
    cursor="$$"; steps=0
    while [ "$steps" -lt 12 ]; do
        [ "$cursor" = "$1" ] && return 0
        raw="$(cat "/proc/$cursor/stat" 2>/dev/null)" || return 1
        parent="$(printf '%s\n' "${raw##*) }" | awk '{print $2}')" || return 1
        case "$parent" in ''|*[!0-9]*) return 1 ;; esac
        [ "$parent" -gt 1 ] && [ "$parent" != "$cursor" ] || return 1
        cursor="$parent"; steps=$((steps + 1))
    done
    return 1
}

brl_r1_owner_argv()
{
    tr '\000' '\n' < "/proc/$1/cmdline" | awk -v engine="$2" '
      {a[NR]=$0}
      END {
        shell=(a[1]=="/opt/bin/ash" || a[1]=="/bin/sh" || a[1]=="/bin/dash" || a[1]=="/usr/bin/dash");
        busybox=(a[1]=="/bin/busybox" || a[1]=="/usr/bin/busybox");
        ok=(NR==3 && shell && a[2]==engine && a[3]=="update") ||
           (NR==4 && busybox && a[2]=="ash" && a[3]==engine && a[4]=="update");
        exit !ok
      }'
}

brl_r1_manifest_valid()
{
    local slot expected_files expected_bytes actual_files actual_bytes
    slot="$1"; expected_files="$2"; expected_bytes="$3"
    brl_r1_regular "$slot/APP-SHA256SUMS" && brl_r1_regular "$slot/release.json" || return 1
    [ -z "$(find "$slot" \( -type l -o -type b -o -type c -o -type p -o -type s \) -print -quit)" ] || return 1
    # The canonical manifest has every app file plus exactly release.json.
    awk -v expected="$expected_files" '
      NF!=2 {bad=1; next}
      length($1)!=64 || $1~/[^a-f0-9]/ {bad=1}
      $2!="release.json" && $2!~/^app\// {bad=1}
      $2~/[^A-Za-z0-9_.\/-]/ || $2~/\.\./ || $2~/\/\.\// || $2~/\/\// {bad=1}
      {if(seen[$2]++)bad=1; if($2=="release.json")release++}
      END {exit (bad || release!=1 || NR!=expected+1)}' "$slot/APP-SHA256SUMS" || return 1
    actual_files="$(find "$slot/app" -type f | wc -l | tr -d ' ')"
    actual_bytes="$(find "$slot/app" -type f -exec wc -c {} \; | awk '{s+=$1} END {print s+0}')"
    [ "$actual_files" = "$expected_files" ] && [ "$actual_bytes" = "$expected_bytes" ] || return 1
    (cd "$slot" && sha256sum -c APP-SHA256SUMS >/dev/null 2>&1)
}

brl_r1_transition_admitted()
{
    local prefix root engine request global pid start path transaction work slot index files bytes sha size
    prefix="${BRORAY_LIGHT_ROOT_PREFIX:-}"
    case "$prefix" in ''|/*) ;; *) brl_r1_refuse PREFIX; return 1 ;; esac
    case "$prefix" in */../*|*/..|*/./*|*/.|*//*|*/) brl_r1_refuse PREFIX; return 1 ;; esac
    [ "$(id -u)" = 0 ] || { brl_r1_refuse NOT_ROOT; return 1; }
    root="$prefix/opt/broray-light"
    engine="$prefix/opt/libexec/broray-light-updater/broray-light-updater.sh"
    request="$prefix/opt/var/lock/broray-light-updater/request.lock"
    global="$prefix/opt/var/lock/broray-light/global-operation.lock"
    transaction="$prefix/opt/var/lib/broray-light-updater/transaction.json"
    work="$prefix/tmp/broray-light-updater"
    slot="$root/releases/2.0.0-r1"; index="$work/release.json"
    for path in "$prefix/opt/broray" "$prefix/opt/etc/init.d/S24broray" \
                "$prefix/opt/var/lock/broray/global-operation.lock"; do
        [ ! -e "$path" ] && [ ! -L "$path" ] || { brl_r1_refuse COOWNERSHIP; return 1; }
    done
    brl_r1_regular "$engine" &&
        [ "$(sha256sum "$engine" | awk '{print $1}')" = '773aaf37893ab100e7023d63c8061d8c4763a4d6186844bb3b671d758c145743' ] || {
        brl_r1_refuse ENGINE_IDENTITY; return 1;
    }
    brl_r1_lock_shape "$request" && brl_r1_lock_shape "$global" || { brl_r1_refuse LOCK_SHAPE; return 1; }
    pid="$(cat "$request/pid")"
    [ "$(cat "$global/pid")" = "$pid" ] || { brl_r1_refuse LOCK_OWNER_MISMATCH; return 1; }
    start="$(brl_process_start "$pid")" && kill -0 "$pid" 2>/dev/null || { brl_r1_refuse OWNER_NOT_LIVE; return 1; }
    brl_r1_owner_argv "$pid" "$engine" && brl_r1_owner_ancestor "$pid" || { brl_r1_refuse NOT_UPDATER_CHILD; return 1; }
    brl_r1_regular "$transaction" && [ "$(wc -c < "$transaction")" -le 16384 ] &&
        jq -e '.schemaVersion==1 and .phase=="target-active" and .previousRelease=="1.0.0-r1" and .targetRelease=="2.0.0-r1"' \
        "$transaction" >/dev/null 2>&1 || { brl_r1_refuse TRANSACTION; return 1; }
    for path in "$root" "$root/releases" "$slot" "$slot/app" "$work"; do
        brl_r1_directory "$path" || { brl_r1_refuse CONTAINER_OWNERSHIP; return 1; }
    done
    [ -L "$root/current" ] && [ "$(readlink "$root/current")" = 'releases/2.0.0-r1' ] &&
        jq -e '.product=="BROray-Light" and .releaseId=="2.0.0-r1" and .candidateId=="2.0.0-r1"' \
        "$slot/release.json" >/dev/null 2>&1 || { brl_r1_refuse CURRENT_BINDING; return 1; }
    brl_r1_regular "$index" && brl_r1_regular "$index.minisig" &&
        brl_r1_regular "$work/app.tar.gz" &&
        jq -e '.product=="BROray-Light" and .candidate.releaseId=="2.0.0-r1" and .candidate.candidateId=="2.0.0-r1"' \
        "$index" >/dev/null 2>&1 || { brl_r1_refuse SIGNED_TRANSACTION_INPUT; return 1; }
    # r1 has already verified this signature before creating target-active;
    # bind its still-live transaction input to the archive and installed slot.
    files="$(jq -r '.candidate.appSlot.fileCount' "$index")"
    bytes="$(jq -r '.candidate.appSlot.logicalBytes' "$index")"
    sha="$(jq -r '.candidate.bundle.sha256' "$index")"
    size="$(jq -r '.candidate.bundle.sizeBytes' "$index")"
    [ "$(wc -c < "$work/app.tar.gz" | tr -d ' ')" = "$size" ] &&
        [ "$(sha256sum "$work/app.tar.gz" | awk '{print $1}')" = "$sha" ] || { brl_r1_refuse ARCHIVE_BINDING; return 1; }
    brl_r1_manifest_valid "$slot" "$files" "$bytes" || { brl_r1_refuse SLOT_MANIFEST; return 1; }
    [ "$(brl_process_start "$pid")" = "$start" ] || { brl_r1_refuse OWNER_CHANGED; return 1; }
    BRL_LEGACY_UPDATER_PID="$pid"
    BRL_LEGACY_UPDATER_START="$start"
    return 0
}
