#!/bin/sh
# BROray-Light Go init v1

set -eu
ROOT=@ROOT@
RUN=@RUN@
INIT=@INIT@
BIN="$ROOT/bin/broray-light"
PIDFILE="$RUN/daemon.pid"

private_dir() (
    owner="$2"
    [ ! -L "$1" ] && cd -P "$1" || exit 1
    # BusyBox can omit stat -c. Terse stat on . keeps the filename one field.
    fields="$(stat -t .)" || exit 1
    set -f
    set -- $fields
    [ "$#" -ge 6 ] && [ "$4:$5" = "41c0:$owner" ]
)

ensure_run() {
    parent="${RUN%/*}"
    [ ! -L "$RUN" ] && [ ! -L "$parent" ] || return 1
    umask 077
    owner="$(id -u)" || return 1
    mkdir -p "$parent" || return 1
    private_dir "$parent" "$owner" || return 1
    mkdir -p "$RUN" || return 1
    private_dir "$RUN" "$owner"
}

read_pid() {
    pid=
    [ -f "$PIDFILE" ] && [ ! -L "$PIDFILE" ] || return 1
    IFS= read -r pid < "$PIDFILE" || return 1
    case "$pid" in
        ''|*[!0-9]*|0|1) return 1 ;;
    esac
}

running() {
    read_pid || return 1
    exe="$(readlink "/proc/$pid/exe" 2>/dev/null)" || return 1
    [ -n "$exe" ] && [ "$exe" = "$(readlink -f "$BIN")" ]
}

start() {
    ensure_run || return 1
    running && return 0
    [ ! -L "$PIDFILE" ] && [ ! -L "$PIDFILE.new" ] && [ ! -L "$RUN/daemon.log" ] || return 1
    [ -f "$BIN" ] && [ ! -L "$BIN" ] && [ -x "$BIN" ] || return 1
    : > "$RUN/daemon.log"
    nohup "$BIN" serve --root "$ROOT" --run "$RUN" </dev/null >>"$RUN/daemon.log" 2>&1 &
    pid=$!
    printf '%s\n' "$pid" > "$PIDFILE.new"
    mv -f "$PIDFILE.new" "$PIDFILE"
}

boot_start() {
    if [ -e "$ROOT/.light-go-install.json" ] || [ -L "$ROOT/.light-go-install.json" ] ||
       [ -e "$ROOT/.light-go-install" ] || [ -L "$ROOT/.light-go-install" ]; then
        if ! "$BIN" recover --root "$ROOT" --run "$RUN" --init-dir "$INIT" --restore-only; then
            previous="$ROOT/.light-go-install/binary"
            [ -f "$previous" ] && [ ! -L "$previous" ] || return 1
            "$previous" recover --root "$ROOT" --run "$RUN" --init-dir "$INIT" --restore-only || return 1
        fi
        [ -f "$BIN" ] || return 0
    fi
    start
}

stop() {
    ensure_run || return 1
    if running; then
        kill -TERM "$pid" || return 1
        ticks=0
        while running && [ "$ticks" -lt 20 ]; do
            sleep 1
            ticks=$((ticks + 1))
        done
        if running; then
            kill -KILL "$pid" || return 1
            ticks=0
            while running && [ "$ticks" -lt 5 ]; do
                sleep 1
                ticks=$((ticks + 1))
            done
            running && return 1
        fi
    fi
    rm -f "$PIDFILE"
}

case "${1:-}" in
    start) boot_start ;;
    start-installed) start ;;
    stop) stop ;;
    status) running ;;
    restart) stop && boot_start ;;
    *) echo "usage: $0 {start|stop|status|restart}" >&2; exit 2 ;;
esac
