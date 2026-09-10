#!/opt/bin/ash
. "${BRORAY_LIGHT_ROOT_PREFIX:-}/opt/broray-light/lib/runtime-environment.sh" || return 1
BRORAY_LIGHT_LOCK_ROOT="$BRL_RAM/run/locks"
BRORAY_LIGHT_GLOBAL_LOCK="$BRL_GLOBAL_LOCK"
BRORAY_LIGHT_UPDATER_LOCK="$BRL_REQUEST_LOCK"

broray_operation_lock_acquire()
{
    brl_lock_acquire global
}

broray_operation_lock_release()
{
    brl_lock_release global
}
