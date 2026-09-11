#!/usr/bin/env python3
"""Explicit external-path diagnostic; never replaces the installed runtime."""
import argparse
import json
import sys
import io
import re
import zipfile
import shlex
from diagnose_r0013_xray_compatibility import REPO, Target, digest, now, save

CHECKPOINTS = REPO / 'checkpoints/R0013'


def seal(path, obj):
    receipt = save(path, obj)
    with path.with_name(path.name + '.sha256').open('x', encoding='ascii') as stream:
        stream.write(receipt['sha256'] + '  ' + path.name + '\n')
    return receipt


def record(event, receipt):
    with (REPO / 'project/WORKLOG.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'at': now(), 'stage': 'R0013_P89', **event, 'receipt': receipt}, ensure_ascii=False) + '\n')
    path = REPO / 'project/R0013-STATE.json'
    state = json.loads(path.read_text(encoding='utf-8'))
    state['currentRevision'] = event['revision']
    state['xrayExternalDiagnostic'] = {**event, **receipt}
    state['nextExactAction'] = event['nextExactAction']
    state['activeFailure'] = event.get('activeFailure')
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def snapshot(target):
    result = target.command(r'''set -eu
test "$(uname -m)" = aarch64
test ! -e /opt/broray; test ! -L /opt/broray
test "$(stat -f -c %T /tmp)" = tmpfs
sha256sum /opt/broray-light/runtime/xray /opt/broray-light/current/APP-SHA256SUMS /opt/broray-light/lib/xray-process.sh
find /opt/broray-light/config /opt/broray-light/servers /opt/broray-light/subscriptions -type f -exec sha256sum {} \; | sort | sha256sum
readlink /opt/broray-light/current
. /opt/broray-light/lib/xray-process.sh
pid="$(broray_xray_runtime_pid)"
printf 'managedPid=%s\n' "$pid"
broray_xray_runtime_identity "$pid"
''')
    return result['stdout']


def preflight():
    result_path = CHECKPOINTS / 'XRAY-EXTERNAL-PREFLIGHT-P89-V2.json'
    assert not result_path.exists(), 'No same-revision retry'
    report = {'schemaVersion': 1, 'revision': 'p89-external-preflight-v2', 'at': now(), 'routerWrites': False}
    target = None
    try:
        target = Target()
        report['identityAndState'] = snapshot(target)
        report['resourcePreflight'] = target.command(r'''set -eu
df -k /tmp; awk '/MemAvailable:/{print}' /proc/meminfo
command -v curl; curl -V | head -n 1
if netstat -lnt | awk '{print $4}' | grep -Eq ':39490$'; then exit 41; fi
test "$(df -k /tmp | awk 'END{print $4}')" -gt 100000
test "$(awk '/MemAvailable:/{print $2}' /proc/meminfo)" -gt 120000
/opt/broray-light/runtime/xray version | head -n 1
''')['stdout']
        raw = target.command('cat /opt/broray-light/config/config.json')['stdout']
        config = json.loads(raw)
        report['activeConfigSha256'] = digest(raw.encode())
        report['configShape'] = {
            'topKeys': sorted(config),
            'inbounds': [{k: x[k] for k in ('listen', 'port', 'protocol') if k in x} for x in config.get('inbounds', [])],
            'outbounds': [{'protocol': x.get('protocol'), 'network': x.get('streamSettings', {}).get('network'),
                           'security': x.get('streamSettings', {}).get('security')} for x in config.get('outbounds', [])],
            'routingPresent': bool(config.get('routing')), 'dnsPresent': bool(config.get('dns')),
        }
        vless = [x for x in config['outbounds'] if x.get('protocol') == 'vless']
        assert len(vless) == 1, 'Require exactly one active VLESS outbound'
        outbound = vless[0]
        assert outbound['protocol'] == 'vless', 'Active outbound is not VLESS'
        assert outbound['streamSettings']['network'] == 'xhttp', 'Active transport is not the historical XHTTP scenario'
        assert outbound['streamSettings']['security'] == 'reality', 'Active security is not REALITY'
        report['outboundIdentitySha256'] = digest(json.dumps(outbound, sort_keys=True, separators=(',', ':')).encode())
        report['status'] = 'PASS_READ_ONLY_EXTERNAL_SCENARIO_PREFLIGHT'
    except Exception as exc:
        report['status'] = 'FIRST_ERROR'
        report['error'] = str(exc)
        seal(CHECKPOINTS / 'process-failures/FAILURE-P89-EXTERNAL-PREFLIGHT-V2.json',
             {'revision': report['revision'], 'at': now(), 'error': str(exc), 'retryPerformed': False,
              'nextRevision': 'p89-external-preflight-v3-only-after-diagnosis', 'routerWrites': False})
    finally:
        if target:
            target.client.close()
        receipt = seal(result_path, report)
        record({'revision': report['revision'], 'status': report['status'],
                'nextExactAction': 'P89_SEAL_EXTERNAL_MATRIX_REVISION' if report['status'].startswith('PASS') else 'P89_DIAGNOSE_PREFLIGHT_FIRST_ERROR'}, receipt)
        print(json.dumps(report, ensure_ascii=False))
        print(json.dumps(receipt))
    return 0 if report['status'].startswith('PASS') else 1


class ExternalTarget(Target):
    def prepare(self):
        self.work = self.command(r'''set -eu; umask 077
test "$(stat -f -c %T /tmp)" = tmpfs
test "$(df -k /tmp | awk 'END{print $4}')" -gt 100000
test "$(awk '/MemAvailable:/{print $2}' /proc/meminfo)" -gt 120000
if netstat -lnt | awk '{print $4}' | grep -Eq ':39490$'; then exit 41; fi
mktemp -d /tmp/brl-r13-external-p89.XXXXXX
''')['stdout'].strip()
        assert re.fullmatch(r'/tmp/brl-r13-external-p89\.[A-Za-z0-9]{6}', self.work)
        self.command(f'test ! -L {self.work}; test "$(stat -c %u:%a {self.work})" = 0:700')


ORDER = ['v26.3.27', 'v26.6.27', 'v26.7.11', 'v26.7.28', 'v26.9.8', 'v26.9.9']
ENDPOINTS = [('https://www.gstatic.com/generate_204', 204, 'empty'),
             ('https://www.cloudflare.com/cdn-cgi/trace', 200, 'trace'),
             ('https://example.com/', 200, 'example')]


def matrix():
    out = REPO / 'dist/R0013/p89-external-v4'
    out.mkdir(parents=True, exist_ok=False)
    reference = json.loads((CHECKPOINTS / 'XRAY-EXTERNAL-PREFLIGHT-P89-V2.json').read_text())
    assert reference['status'].startswith('PASS')
    source = REPO / 'dist/R0013/p88-xray-compat-v5'
    binaries = json.loads((source / 'report.json').read_text())['versions']
    report = {'schemaVersion': 1, 'revision': 'p89-external-v4', 'startedAt': now(),
              'scope': 'Physical ARM64 router, unchanged current external VLESS/XHTTP/REALITY outbound; diagnostic localhost SOCKS and no direct fallback; no installed-runtime switch or browser claim.',
              'outboundIdentitySha256': reference['outboundIdentitySha256'],
              'priorBROray2626RejectionSuperseded': False, 'versions': [], 'candidateReady': False,
              'runnerSha256': digest(__import__('pathlib').Path(__file__).read_bytes())}
    target = None
    active_row = None
    failure_path = None
    try:
        target = ExternalTarget()
        report['before'] = snapshot(target)
        assert report['before'] == reference['identityAndState'], 'Target changed since preflight'
        raw = target.command('cat /opt/broray-light/config/config.json')['stdout']
        assert digest(raw.encode()) == reference['activeConfigSha256'], 'Active config changed'
        current = json.loads(raw)
        outbound = next(x for x in current['outbounds'] if x.get('protocol') == 'vless')
        assert digest(json.dumps(outbound, sort_keys=True, separators=(',', ':')).encode()) == report['outboundIdentitySha256']
        assert not outbound.get('proxySettings'), 'Unexpected chained outbound'
        assert not outbound.get('streamSettings', {}).get('sockopt', {}).get('dialerProxy'), 'Unexpected dialer proxy'
        target.prepare()
        report['ramWorkDirectory'] = target.work
        config = {'log': {'loglevel': 'warning', 'access': 'none', 'error': 'none'},
                  'inbounds': [{'listen': '127.0.0.1', 'port': 39490, 'protocol': 'socks',
                                'settings': {'auth': 'noauth', 'udp': False}}],
                  'outbounds': [outbound]}
        target.put('config.json', json.dumps(config, ensure_ascii=False).encode())
        report['diagnosticConfigSha256'] = digest(json.dumps(config, ensure_ascii=False).encode())
        for tag in ORDER:
            active_row = {'tag': tag, 'startedAt': now(), 'requests': []}
            report['versions'].append(active_row)
            reference_binary = next(x for x in binaries if x['tag'] == tag)
            archive = (source / (tag + '.zip')).read_bytes()
            assert digest(archive) == reference_binary['archiveSha256'], 'Archive identity mismatch'
            with zipfile.ZipFile(io.BytesIO(archive)) as package:
                binary = package.read('xray')
            assert digest(binary) == reference_binary['binarySha256'], 'Binary identity mismatch'
            active_row.update(archiveSha256=digest(archive), binarySha256=digest(binary))
            target.put('xray', binary, 0o700)
            validation = target.command(f'{target.work}/xray run -test -c {target.work}/config.json', check=False)
            active_row['configValidation'] = {'exitCode': validation['exitCode'],
                'configurationOK': 'Configuration OK.' in validation['stdout'],
                'outputSha256': digest((validation['stdout'] + validation['stderr']).encode())}
            assert validation['exitCode'] == 0 and active_row['configValidation']['configurationOK'], tag + ': config failed'
            target.files.update(['process.pid', 'runtime.log'])
            start = target.command(f'''set -eu; umask 077; cd {target.work}
test ! -e runtime.log; test ! -e process.pid
trap '' HUP
./xray run -c {target.work}/config.json >runtime.log 2>&1 </dev/null &
pid=$!; printf '%s\\n' "$pid" >process.pid
for n in $(seq 1 8); do
 kill -0 "$pid"
 if netstat -lnt | grep -q '127.0.0.1:39490 '; then
  test "$(readlink /proc/$pid/exe)" = {target.work}/xray
  printf 'pid=%s\\n' "$pid"; awk '{{print $22}}' /proc/$pid/stat; exit 0
 fi
 sleep 1
done
exit 42
''', timeout=15, check=False)
            active_row['start'] = start
            assert start['exitCode'] == 0, tag + ': start failed'
            for index, (url, expected, kind) in enumerate(ENDPOINTS, 1):
                body, err = f'body-{index}', f'curl-{index}.log'
                target.files.update([body, err])
                result = target.command(f"umask 077; curl -q --noproxy '' --socks5-hostname 127.0.0.1:39490 --proto '=https' --connect-timeout 10 --max-time 25 --silent --show-error --fail --output {target.work}/{body} --write-out '%{{http_code}} %{{ssl_verify_result}} %{{size_download}} %{{time_total}}' {shlex.quote(url)} 2>{target.work}/{err}", timeout=32, check=False)
                row = {'url': url, 'exitCode': result['exitCode'], 'metrics': result['stdout'], 'at': now()}
                active_row['requests'].append(row)
                private_err = target.command(f'if test -f {target.work}/{err}; then cat {target.work}/{err}; fi')['stdout']
                row['stderrSha256'] = digest(private_err.encode())
                row['timeout'] = result['exitCode'] == 28
                row['tlsConnectionFailed'] = result['exitCode'] == 35
                row['certificateVerificationFailed'] = result['exitCode'] in [51, 60]
                parts = result['stdout'].split()
                assert result['exitCode'] == 0, f'{tag}: HTTPS request {index} failed with curl exit {result["exitCode"]}'
                assert len(parts) == 4 and parts[0] == str(expected) and parts[1] == '0', f'{tag}: HTTPS status/certificate gate failed'
                response = target.command(f'head -c 65536 {target.work}/{body}')['stdout']
                row['bodySha256'] = digest(response.encode())
                if kind == 'empty': assert parts[2] == '0', 'Nonempty 204'
                if kind == 'trace':
                    assert '\nip=' in '\n' + response and '\nh=' in '\n' + response, 'Not Cloudflare trace'
                    row['egressIpSha256'] = digest(next(x for x in response.splitlines() if x.startswith('ip=')).encode())
                if kind == 'example': assert 'Example Domain' in response, 'Not example.com response'
                row['status'] = 'PASS_HTTPS_CERTIFICATE_AND_CONTENT'
                target.remove([body, err])
                print(f'{tag}: HTTPS {index}/3 PASS', flush=True)
            target.command(f'''set -eu
pid="$(cat {target.work}/process.pid)"
test "$(readlink /proc/$pid/exe)" = {target.work}/xray
kill -TERM "$pid"
for n in $(seq 1 8); do
 if test "$(readlink /proc/$pid/exe 2>/dev/null || :)" != {target.work}/xray; then exit 0; fi
 sleep 1
done
exit 43
''', timeout=12)
            active_row['status'] = 'PASS_3_OF_3_EXTERNAL_HTTPS'
            receipt = seal(out / (tag + '.json'), active_row)
            record({'revision': report['revision'], 'status': active_row['status'], 'tag': tag,
                    'nextExactAction': 'CONTINUE_NEXT_UNTESTED_VERSION'}, receipt)
            target.remove(['xray', 'process.pid', 'runtime.log'])
        report['status'] = 'PASS_REMAINING_5_VERSIONS_AND_FINAL_2699_CONTROL'
    except Exception as exc:
        report['status'] = 'FIRST_ERROR'
        report['error'] = str(exc)
        if active_row: active_row['status'] = 'FAIL_STOPPED_NO_RETRY'
        if target and target.work:
            diagnostics = target.command(f'if test -f {target.work}/runtime.log; then sha256sum {target.work}/runtime.log; wc -c <{target.work}/runtime.log; fi', check=False)
            report['runtimeDiagnosticsIdentity'] = diagnostics
        failure_path = 'checkpoints/R0013/process-failures/FAILURE-P89-EXTERNAL-V4.json'
        failure = seal(REPO / failure_path, {'revision': report['revision'], 'at': now(),
            'error': str(exc), 'version': active_row, 'retryPerformed': False,
            'nextRevision': 'p89-external-v5-only-after-first-error-diagnosis'})
        record({'revision': report['revision'], 'status': 'FIRST_ERROR', 'activeFailure': failure_path,
                'nextExactAction': 'P89_DIAGNOSE_EXTERNAL_FAILURE_WITHOUT_RETRY'}, failure)
    finally:
        if target:
            try:
                report['cleanup'] = target.cleanup()
                report['after'] = snapshot(target)
                report['installedStatePreserved'] = report['before'] == report['after']
                assert report['installedStatePreserved'], 'Managed runtime or durable state changed'
            except Exception as exc:
                report['cleanupError'] = str(exc)
                report['status'] = 'CLEANUP_OR_PRESERVATION_BLOCKED'
                cleanup_failure = seal(CHECKPOINTS / 'process-failures/FAILURE-P89-EXTERNAL-V4-CLEANUP.json',
                    {'revision': report['revision'], 'at': now(), 'error': str(exc), 'retryPerformed': False})
                failure_path = cleanup_failure['path']
            target.client.close()
        report['completedAt'] = now()
        receipt = seal(CHECKPOINTS / 'XRAY-EXTERNAL-P89-V4.json', report)
        record({'revision': report['revision'], 'status': report['status'], 'activeFailure': failure_path,
                'nextExactAction': 'P89_REVIEW_EXTERNAL_RESULTS' if report['status'].startswith('PASS') else 'P89_DIAGNOSE_RECORDED_EXTERNAL_FAILURE'}, receipt)
        print(json.dumps({'status': report['status'], 'receipt': receipt,
                          'installedStatePreserved': report.get('installedStatePreserved'),
                          'cleanup': report.get('cleanup'), 'error': report.get('error')}), flush=True)
    return 0 if report['status'].startswith('PASS') else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['preflight', 'matrix'], required=True)
    args = parser.parse_args()
    sys.exit(preflight() if args.phase == 'preflight' else matrix())
