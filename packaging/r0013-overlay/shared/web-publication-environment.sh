#!/opt/bin/ash
# Private invocation scratch and shared operation serialization for publication.
. "${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/broray-light/lib/runtime-environment.sh" || return 1
[ "${BRORAY_LIGHT_WEB_ROOT:-$BRORAY_ROOT}" = "$BRORAY_ROOT" ] || return 1
[ "${BRORAY_LIGHT_WEB_LIFECYCLE_ROOT:-${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/libexec/broray-light-web-publish}" = "${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/libexec/broray-light-web-publish" ] || return 1
BRORAY_LIGHT_WEB_ROOT="$BRORAY_ROOT"
BRL_WEB_WORK="$(umask 077; mktemp -d "$BRL_RAM/tmp/web-publication.XXXXXX")" || return 1
brl_ram_dir_valid "$BRL_WEB_WORK" || return 1
BRL_WEB_WORK_ID="$(stat -c '%d:%i' "$BRL_WEB_WORK")"
BRORAY_LIGHT_WEB_TMP_ROOT="$BRL_WEB_WORK"
export BRORAY_LIGHT_WEB_ROOT BRORAY_LIGHT_WEB_TMP_ROOT
BRL_WEB_FENCE=false

brl_web_invocation_cleanup()
{
    local rc child
    rc=$?; trap - 0
    if brl_ram_dir_valid "$BRL_WEB_WORK" && [ "$(stat -c '%d:%i' "$BRL_WEB_WORK")" = "$BRL_WEB_WORK_ID" ]; then
        for child in "$BRL_WEB_WORK"/* "$BRL_WEB_WORK"/.[!.]* "$BRL_WEB_WORK"/..?*; do
            [ -e "$child" ] || [ -L "$child" ] || continue
            case "${child##*/}" in web-publish-*.$$.conf|web-publish-*.$$.json|web-publish-*.$$.out|web-publish-*.$$.conf.err|web-publish-*.$$.out.err) ;;
                *) rc=1; continue ;;
            esac
            if [ -f "$child" ] && [ ! -L "$child" ] && [ "$(stat -c '%u' "$child")" = 0 ]; then
                rm "$child" || rc=1
            else rc=1
            fi
        done
        rmdir "$BRL_WEB_WORK" || rc=1
    else rc=1
    fi
    if [ "$BRL_WEB_FENCE" = true ]; then brl_lock_release global || rc=1; fi
    exit "$rc"
}
trap brl_web_invocation_cleanup 0
trap 'exit 129' 1
trap 'exit 130' 2
trap 'exit 143' 15
umask 077
case "${1:-}" in
    ensure|delete) brl_lock_acquire global || return 1; BRL_WEB_FENCE=true ;;
    status) ;;
    *) return 1 ;;
esac
