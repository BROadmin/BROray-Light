#!/opt/bin/ash
BRORAY_KEENETIC_WRITE_POLICY_SCHEMA_VERSION=1
BRORAY_KEENETIC_WRITE_POLICY_CANDIDATE_ID='BROray-Light-r0008'
BRORAY_KEENETIC_WRITE_POLICY_STAGE='staged'
BRORAY_KEENETIC_WRITE_POLICY_ENABLED=true
BRORAY_KEENETIC_WRITE_POLICY_SHA256='e13d739507fa3a70662ef7f2beb5cfec50ff01fe812a8577ca9f7cbc1f6f2430'
BRORAY_KEENETIC_PROXY_INTERFACE_SERIALIZATION='dynamic-bounded-v1'
broray_keenetic_write_policy_contract_valid(){ [ "$BRORAY_KEENETIC_WRITE_POLICY_SCHEMA_VERSION" = 1 ] && [ "$BRORAY_KEENETIC_WRITE_POLICY_ENABLED" = true ] && [ "$BRORAY_KEENETIC_WRITE_POLICY_STAGE" = staged ] && [ "${#BRORAY_KEENETIC_WRITE_POLICY_SHA256}" -eq 64 ] && [ "$BRORAY_KEENETIC_PROXY_INTERFACE_SERIALIZATION" = dynamic-bounded-v1 ]; }
broray_keenetic_write_policy_check(){ [ "${1:-}" = proxy-interface ] || return 4; broray_keenetic_write_policy_contract_valid || return 3; return 0; }
broray_keenetic_write_policy_sha256(){ broray_keenetic_write_policy_contract_valid || return 1; printf '%s\n' "$BRORAY_KEENETIC_WRITE_POLICY_SHA256"; }
broray_keenetic_write_policy_proxy_interface_profile_check(){ broray_keenetic_write_policy_check proxy-interface; }
BRORAY_KEENETIC_WRITE_POLICY_LOADED=true
