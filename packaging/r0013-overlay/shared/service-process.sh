#!/opt/bin/ash
# Exact Light process identities. No pgrep/substring or system-wide signals.
# Caller supplies the validated root and protected RAM namespace.

brl_service_start_id()
{
    case "$1" in ''|*[!0-9]*|0|1) return 1 ;; esac
    [ -r "/proc/$1/stat" ] || return 1
    sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | awk '$1!="Z" && $20~/^[0-9]+$/ {print $20}'
}

brl_service_role()
{
    case "$1" in
        daemon) BRL_ROLE_PID="$BRL_RAM/run/broray-lightd.pid"; BRL_ROLE_BIN="$ROOT/bin/broray-lightd" ;;
        web) BRL_ROLE_PID="$BRL_RAM/run/lighttpd.pid"; BRL_ROLE_BIN="$(command -v lighttpd)" || return 1 ;;
        auth) BRL_ROLE_PID="$BRL_RAM/run/web-new/native-auth/nginx.pid"; BRL_ROLE_BIN="$BRL_RAM/run/web-new/native-auth/broray-ndm-auth-nginx" ;;
        *) return 1 ;;
    esac
}

brl_service_identity()
{
    local role pid started ended executable expected shell
    role="$1"; pid="$2"
    started="$(brl_service_start_id "$pid")"; [ -n "$started" ] || return 1
    brl_service_role "$role" || return 1
    executable="$(readlink "/proc/$pid/exe")" || return 1
    case "$role" in
        daemon)
            shell="$(readlink "/proc/$$/exe")" || return 1
            [ "$executable" = "$shell" ] || return 1
            tr '\000' '\n' < "/proc/$pid/cmdline" | awk -v path="$BRL_ROLE_BIN" '
              NR==1 {next} NR==2 {if($0!=path)bad=1;next} {bad=1}
              END {exit (NR!=2 || bad)}' || return 1 ;;
        web)
            expected="$(readlink -f "$BRL_ROLE_BIN")" || return 1
            [ "$executable" = "$expected" ] || return 1
            tr '\000' '\n' < "/proc/$pid/cmdline" | awk -v config="$ROOT/config/lighttpd.conf" '
              NR==1 {next} NR==2 {if($0!="-f")bad=1;next} NR==3 {if($0!=config)bad=1;next} {bad=1}
              END {exit (NR!=3 || bad)}' || return 1 ;;
        auth)
            [ "$executable" = "$BRL_ROLE_BIN" ] || return 1
            tr '\000' '\n' < "/proc/$pid/cmdline" | awk -v binary="$BRL_ROLE_BIN" \
                -v config="$BRL_RAM/run/web-new/native-auth/nginx.conf" '
              NR==1 {title=("nginx: master process " binary " -p / -c " config); single=($0==title);next}
              NR==2 {if($0!="-p")bad=1;next} NR==3 {if($0!="/")bad=1;next}
              NR==4 {if($0!="-c")bad=1;next} NR==5 {if($0!=config)bad=1;next} {bad=1}
              END {exit !((NR==1 && single) || (NR==5 && !bad))}' || return 1 ;;
    esac
    ended="$(brl_service_start_id "$pid")"
    [ "$started" = "$ended" ] && kill -0 "$pid" 2>/dev/null || return 1
    printf '%s\n' "$started"
}

brl_service_pids()
{
    local role directory pid
    role="$1"
    for directory in /proc/[0-9]*; do
        pid="${directory##*/}"
        brl_service_identity "$role" "$pid" >/dev/null 2>&1 && printf '%s\n' "$pid"
    done
    return 0
}

brl_service_pidfile()
{
    local pid
    brl_service_role "$1" || return 1
    [ -e "$BRL_ROLE_PID" ] || [ -L "$BRL_ROLE_PID" ] || return 0
    brl_ram_file_valid "$BRL_ROLE_PID" || return 1
    pid="$(awk 'NR==1 && /^[0-9]+$/ && $0>1 {p=$0;next} {bad=1} END {if(NR==1&&!bad)print p;else exit 1}' "$BRL_ROLE_PID")" || return 1
    if [ -n "$(brl_service_start_id "$pid")" ]; then
        brl_service_identity "$1" "$pid" >/dev/null || return 1
        printf '%s\n' "$pid"
    fi
}

brl_service_running()
{
    local role pid pids
    role="$1"; pid="$(brl_service_pidfile "$role")" || return 1
    [ -n "$pid" ] || return 1
    pids="$(brl_service_pids "$role")"
    [ "$pids" = "$pid" ]
}

brl_service_before_start()
{
    local role pid pids
    role="$1"; pid="$(brl_service_pidfile "$role")" || return 2
    pids="$(brl_service_pids "$role")"
    if [ -n "$pids" ]; then
        [ -n "$pid" ] && [ "$pid" = "$pids" ] && return 0
        # Unrecorded/duplicate processes are not silently adopted.
        return 2
    fi
    brl_service_role "$role" || return 2
    [ ! -e "$BRL_ROLE_PID" ] || rm "$BRL_ROLE_PID" || return 2
    return 1
}

brl_service_stop_role()
{
    local role pid pids start current attempt signal
    role="$1"; pid="$(brl_service_pidfile "$role")" || return 1
    pids="$(brl_service_pids "$role")"
    [ -z "$pids" ] || { [ -n "$pid" ] && [ "$pids" = "$pid" ]; } || return 1
    if [ -n "$pids" ]; then
        start="$(brl_service_identity "$role" "$pid")" || return 1
        [ "$start" = "$(brl_service_identity "$role" "$pid")" ] || return 1
        signal=TERM; [ "$role" != auth ] || signal=QUIT
        kill "-$signal" "$pid" || return 1
        attempt=0
        while [ "$attempt" -lt 10 ]; do
            current="$(brl_service_start_id "$pid")"
            [ "$current" = "$start" ] || break
            sleep 1; attempt=$((attempt+1))
        done
        [ "$(brl_service_start_id "$pid")" != "$start" ] || return 1
        [ -z "$(brl_service_pids "$role")" ] || return 1
    fi
    brl_service_role "$role" || return 1
    if [ "$role" = auth ]; then
        # nginx workers share the private executable; none may survive the
        # master's graceful shutdown. Never signal an unclassified worker.
        for current in /proc/[0-9]*/exe; do
            [ "$(readlink "$current" 2>/dev/null)" != "$BRL_ROLE_BIN" ] || return 1
        done
    fi
    [ ! -e "$BRL_ROLE_PID" ] || { brl_ram_file_valid "$BRL_ROLE_PID" && rm "$BRL_ROLE_PID"; }
}
