#!/opt/bin/ash

# Immutable package-owned write policy for the one BROray-Light KeenDNS path.
# The policy identity is SHA-256 of:
# BROray-Light|web-publish|1|brolight|http|8080|ndns|ssl-redirect|public|dynamic-bounded-v1|fail-closed

BRORAY_LIGHT_WEB_POLICY_SCHEMA_VERSION=1
BRORAY_LIGHT_WEB_POLICY_CANDIDATE_ID='0.1.0-r0009c08'
BRORAY_LIGHT_WEB_POLICY_STAGE='staged'
BRORAY_LIGHT_WEB_POLICY_ENABLED=true
BRORAY_LIGHT_WEB_POLICY_SHA256='e3e0e68b10ef69fce1c504f2689d1ecbd3f8b6b78ee6e7ab03d8ea73d63607dc'
BRORAY_LIGHT_WEB_POLICY_SERIALIZATION='dynamic-bounded-v1'

broray_light_web_policy_valid()
{
    [ "$BRORAY_LIGHT_WEB_POLICY_SCHEMA_VERSION" = 1 ] &&
    [ "$BRORAY_LIGHT_WEB_POLICY_CANDIDATE_ID" = '0.1.0-r0009c08' ] &&
    [ "$BRORAY_LIGHT_WEB_POLICY_STAGE" = staged ] &&
    [ "$BRORAY_LIGHT_WEB_POLICY_ENABLED" = true ] &&
    [ "$BRORAY_LIGHT_WEB_POLICY_SERIALIZATION" = dynamic-bounded-v1 ] &&
    [ "$BRORAY_LIGHT_WEB_POLICY_SHA256" = e3e0e68b10ef69fce1c504f2689d1ecbd3f8b6b78ee6e7ab03d8ea73d63607dc ]
}

broray_light_web_policy_require()
{
    [ "${1:-}" = web-publish ] || return 4
    broray_light_web_policy_valid || return 3
}

broray_light_web_policy_sha256()
{
    broray_light_web_policy_valid || return 1
    printf '%s\n' "$BRORAY_LIGHT_WEB_POLICY_SHA256"
}

broray_light_web_policy_serialization()
{
    broray_light_web_policy_require web-publish || return $?
    [ "${1:-}" = profile ] || return 4
    printf '%s\n' "$BRORAY_LIGHT_WEB_POLICY_SERIALIZATION"
}

BRORAY_LIGHT_WEB_POLICY_LOADED=true
