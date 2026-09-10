# Protected bootstrap namespace, expanded into preinst/postinst by R0013 builder.
BOOTSTRAP_ROOT="$ROOT_PREFIX/tmp/broray-light-bootstrap"
BOOTSTRAP_MARKER="BROray-Light:bootstrap/1:@RELEASE_ID@"

bootstrap_ram_parent_valid()
{
    [ "$(id -u)" = 0 ] || return 1
    [ -d "$ROOT_PREFIX/tmp" ] && [ ! -L "$ROOT_PREFIX/tmp" ] || return 1
    [ "$(stat -c %u "$ROOT_PREFIX/tmp")" = 0 ] || return 1
    case "$(stat -f -c %T "$ROOT_PREFIX/tmp")" in tmpfs|ramfs) ;; *) return 1 ;; esac
}

bootstrap_owned()
{
    bootstrap_ram_parent_valid || return 1
    [ -d "$BOOTSTRAP_ROOT" ] && [ ! -L "$BOOTSTRAP_ROOT" ] || return 1
    [ "$(stat -c '%u:%a' "$BOOTSTRAP_ROOT")" = 0:700 ] || return 1
    [ -f "$BOOTSTRAP_ROOT/owner" ] && [ ! -L "$BOOTSTRAP_ROOT/owner" ] || return 1
    [ "$(stat -c '%u:%a' "$BOOTSTRAP_ROOT/owner")" = 0:600 ] || return 1
    [ "$(cat "$BOOTSTRAP_ROOT/owner")" = "$BOOTSTRAP_MARKER" ] || return 1
}

bootstrap_create()
{
    bootstrap_ram_parent_valid || return 1
    [ ! -e "$BOOTSTRAP_ROOT" ] && [ ! -L "$BOOTSTRAP_ROOT" ] || return 1
    (umask 077; mkdir "$BOOTSTRAP_ROOT") || return 1
    (umask 077; printf '%s\n' "$BOOTSTRAP_MARKER" >"$BOOTSTRAP_ROOT/owner") || return 1
    bootstrap_owned
}

bootstrap_cleanup()
{
    bootstrap_owned || return 1
    # Do not recurse, follow links or remove an unexpected recovery object.
    for leaf in "$BOOTSTRAP_ROOT"/* "$BOOTSTRAP_ROOT"/.[!.]* "$BOOTSTRAP_ROOT"/..?*; do
        [ -e "$leaf" ] || [ -L "$leaf" ] || continue
        case "$leaf" in
            "$BOOTSTRAP_ROOT/owner"|"$BOOTSTRAP_ROOT/xray-@XRAY_VERSION@") ;;
            *) return 1 ;;
        esac
        [ -f "$leaf" ] && [ ! -L "$leaf" ] && [ "$(stat -c %u "$leaf")" = 0 ] || return 1
    done
    rm -f "$BOOTSTRAP_ROOT/xray-@XRAY_VERSION@" || return 1
    rm -f "$BOOTSTRAP_ROOT/owner" || return 1
    rmdir "$BOOTSTRAP_ROOT"
}
