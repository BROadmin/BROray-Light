#!/opt/bin/ash
set -eu
PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin
export PATH
[ -d '/tmp/brl-r13-backup-p73.ELnUPS' ] && [ ! -L '/tmp/brl-r13-backup-p73.ELnUPS' ]
[ "$(stat -c '%u:%a:%d:%i' '/tmp/brl-r13-backup-p73.ELnUPS')" = '0:700:13:45275739' ]
[ "$(find '/tmp/brl-r13-backup-p73.ELnUPS' -mindepth 1 -maxdepth 1 | wc -l)" -eq 3 ]
[ -d '/tmp/brl-r13-backup-p74.mBfUv5' ] && [ ! -L '/tmp/brl-r13-backup-p74.mBfUv5' ]
[ "$(stat -c '%u:%a:%d:%i' '/tmp/brl-r13-backup-p74.mBfUv5')" = '0:700:13:45303757' ]
[ "$(find '/tmp/brl-r13-backup-p74.mBfUv5' -mindepth 1 -maxdepth 1 | wc -l)" -eq 7 ]
[ -d '/tmp/brl-r13-install-p76.E7rJwm' ] && [ ! -L '/tmp/brl-r13-install-p76.E7rJwm' ]
[ "$(stat -c '%u:%a:%d:%i' '/tmp/brl-r13-install-p76.E7rJwm')" = '0:700:13:45373386' ]
[ "$(find '/tmp/brl-r13-install-p76.E7rJwm' -mindepth 1 -maxdepth 1 | wc -l)" -eq 8 ]
verify_file()
{
 [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%u:%h' "$1")" = 0:1 ]
 [ "$(sha256sum "$1" | awk '{print $1}')" = "$2" ]
}
verify_file '/tmp/brl-r13-backup-p73.ELnUPS/persistent-before.sha256' '3461f8074bf0a128fcfd367fe2f879eb8a49b2763177188c1ccffac4794a394f'
verify_file '/tmp/brl-r13-backup-p73.ELnUPS/roots.txt' '60c92dbd592b437c455dfc32e0ba6620a071580857dd27fe3b2d882ab5059bd1'
verify_file '/tmp/brl-r13-backup-p73.ELnUPS/owner' '3a7f7592645077f5a9871393eba5078bc9050969ce33832c2eb8cca812ce9ac8'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/ssh-connection.txt' '6f319497e01675c7d15164ce0fbcc64e2c76e48ea084d476f805ea0432cd913a'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/running-config.txt' 'f65237270300589a032da3062607bc9ab421e122471ed396fc98046186a8d144'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/persistent-after.sha256' '3461f8074bf0a128fcfd367fe2f879eb8a49b2763177188c1ccffac4794a394f'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/full-broray.tar.gz' 'fe51b6ccc3806a6a12e351b646af1e64e1def11bc5b49a5f0ce9343b63902c18'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/persistent-before.sha256' '3461f8074bf0a128fcfd367fe2f879eb8a49b2763177188c1ccffac4794a394f'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/roots.txt' '60c92dbd592b437c455dfc32e0ba6620a071580857dd27fe3b2d882ab5059bd1'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/owner' 'd6acb8ddc5860aef16cff2432b4602de7b76a9098bb4e316f2331024ee29f97f'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/p84-durable-after.sha256' 'a19728b1342d6095b5f4f9fbe51c290b6ebe7680cb0cf41744d704c03e7fa69b'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/p84-durable-before.sha256' 'a19728b1342d6095b5f4f9fbe51c290b6ebe7680cb0cf41744d704c03e7fa69b'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/broray-light_2.0.0-p83_aarch64-3.10.ipk' 'a31449263dfc5b772854fcd3f4d8624c334e3038715c61ae9996fd4fcd6adb79'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/broray-light-install-2.0.0-p83.sh' 'f8775988803ed70fd1eed455a6444e567ebad8109a252c430a7071f4aefda0c2'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/pre-uninstall-persistent.sha256' '3461f8074bf0a128fcfd367fe2f879eb8a49b2763177188c1ccffac4794a394f'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/broray-light_2.0.0_aarch64-3.10.ipk' '5b142793c7318c3620c494160d8c4413f44467e5e4d1e5e6e614fb88e142f7a7'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/broray-light-install-2.0.0.sh' 'ae98ec1b3150b17eeb979ceebbbaee987d10c1bf6641821073ceb7dd45e135d3'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/owner' '4384f6fad6eef489ffcce4f2c555da8994c52e5b0007124ab4d6050aee1e4734'
printf 'P86_18_EXACT_TEMP_FILES_VERIFIED\n'
verify_file '/tmp/brl-r13-backup-p73.ELnUPS/persistent-before.sha256' '3461f8074bf0a128fcfd367fe2f879eb8a49b2763177188c1ccffac4794a394f' && rm '/tmp/brl-r13-backup-p73.ELnUPS/persistent-before.sha256'
verify_file '/tmp/brl-r13-backup-p73.ELnUPS/roots.txt' '60c92dbd592b437c455dfc32e0ba6620a071580857dd27fe3b2d882ab5059bd1' && rm '/tmp/brl-r13-backup-p73.ELnUPS/roots.txt'
verify_file '/tmp/brl-r13-backup-p73.ELnUPS/owner' '3a7f7592645077f5a9871393eba5078bc9050969ce33832c2eb8cca812ce9ac8' && rm '/tmp/brl-r13-backup-p73.ELnUPS/owner'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/ssh-connection.txt' '6f319497e01675c7d15164ce0fbcc64e2c76e48ea084d476f805ea0432cd913a' && rm '/tmp/brl-r13-backup-p74.mBfUv5/ssh-connection.txt'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/running-config.txt' 'f65237270300589a032da3062607bc9ab421e122471ed396fc98046186a8d144' && rm '/tmp/brl-r13-backup-p74.mBfUv5/running-config.txt'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/persistent-after.sha256' '3461f8074bf0a128fcfd367fe2f879eb8a49b2763177188c1ccffac4794a394f' && rm '/tmp/brl-r13-backup-p74.mBfUv5/persistent-after.sha256'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/full-broray.tar.gz' 'fe51b6ccc3806a6a12e351b646af1e64e1def11bc5b49a5f0ce9343b63902c18' && rm '/tmp/brl-r13-backup-p74.mBfUv5/full-broray.tar.gz'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/persistent-before.sha256' '3461f8074bf0a128fcfd367fe2f879eb8a49b2763177188c1ccffac4794a394f' && rm '/tmp/brl-r13-backup-p74.mBfUv5/persistent-before.sha256'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/roots.txt' '60c92dbd592b437c455dfc32e0ba6620a071580857dd27fe3b2d882ab5059bd1' && rm '/tmp/brl-r13-backup-p74.mBfUv5/roots.txt'
verify_file '/tmp/brl-r13-backup-p74.mBfUv5/owner' 'd6acb8ddc5860aef16cff2432b4602de7b76a9098bb4e316f2331024ee29f97f' && rm '/tmp/brl-r13-backup-p74.mBfUv5/owner'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/p84-durable-after.sha256' 'a19728b1342d6095b5f4f9fbe51c290b6ebe7680cb0cf41744d704c03e7fa69b' && rm '/tmp/brl-r13-install-p76.E7rJwm/p84-durable-after.sha256'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/p84-durable-before.sha256' 'a19728b1342d6095b5f4f9fbe51c290b6ebe7680cb0cf41744d704c03e7fa69b' && rm '/tmp/brl-r13-install-p76.E7rJwm/p84-durable-before.sha256'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/broray-light_2.0.0-p83_aarch64-3.10.ipk' 'a31449263dfc5b772854fcd3f4d8624c334e3038715c61ae9996fd4fcd6adb79' && rm '/tmp/brl-r13-install-p76.E7rJwm/broray-light_2.0.0-p83_aarch64-3.10.ipk'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/broray-light-install-2.0.0-p83.sh' 'f8775988803ed70fd1eed455a6444e567ebad8109a252c430a7071f4aefda0c2' && rm '/tmp/brl-r13-install-p76.E7rJwm/broray-light-install-2.0.0-p83.sh'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/pre-uninstall-persistent.sha256' '3461f8074bf0a128fcfd367fe2f879eb8a49b2763177188c1ccffac4794a394f' && rm '/tmp/brl-r13-install-p76.E7rJwm/pre-uninstall-persistent.sha256'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/broray-light_2.0.0_aarch64-3.10.ipk' '5b142793c7318c3620c494160d8c4413f44467e5e4d1e5e6e614fb88e142f7a7' && rm '/tmp/brl-r13-install-p76.E7rJwm/broray-light_2.0.0_aarch64-3.10.ipk'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/broray-light-install-2.0.0.sh' 'ae98ec1b3150b17eeb979ceebbbaee987d10c1bf6641821073ceb7dd45e135d3' && rm '/tmp/brl-r13-install-p76.E7rJwm/broray-light-install-2.0.0.sh'
verify_file '/tmp/brl-r13-install-p76.E7rJwm/owner' '4384f6fad6eef489ffcce4f2c555da8994c52e5b0007124ab4d6050aee1e4734' && rm '/tmp/brl-r13-install-p76.E7rJwm/owner'
rmdir '/tmp/brl-r13-backup-p73.ELnUPS'
rmdir '/tmp/brl-r13-backup-p74.mBfUv5'
rmdir '/tmp/brl-r13-install-p76.E7rJwm'
printf 'P86_INVOCATION_SCRATCH_CLEANED_LOCAL_BACKUPS_RETAINED\n'
df -k /opt /tmp
