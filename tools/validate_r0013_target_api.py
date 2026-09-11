"""Real authorized target API acceptance. Secrets are held in memory only."""
import argparse
import datetime
import getpass
import hashlib
import http.cookiejar
import json
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://brolight.tvervip.keenetic.link'


class NativeAPI:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, endpoint, payload=None, method=None):
        assert endpoint.startswith('/api/') and '\n' not in endpoint
        body = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(BASE + endpoint, data=body, method=method,
            headers={'User-Agent': 'BROray-Light-R0013-Acceptance', 'Content-Type': 'application/json',
                     'Origin': BASE, 'Referer': BASE + '/home.html?v=2.0.0', 'Cache-Control': 'no-store'})
        try:
            response = self.opener.open(req, timeout=90)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read(2 * 1024 * 1024 + 1)
            assert len(body) <= 2 * 1024 * 1024
            return response.status, dict(response.headers), json.loads(body)

    def login(self):
        password = getpass.getpass('Keenetic admin password (not saved): ')
        status, headers, data = self.request('/api/login.cgi', {'login': 'admin', 'password': password})
        del password
        assert status == 200 and data.get('ok') is True, ('native-login-failed', status, data.get('error'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / 'checkpoints/R0013') and not output.exists()
    report = {'schemaVersion': 1, 'stage': 'R0013', 'revision': args.revision, 'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'status': 'IN_PROGRESS', 'scope': 'Actual public HTTPS native login and non-mutating backend requests; no browser click claim', 'tests': [], 'candidateReady': False}
    gate = 'unauthenticated-session-refusal'

    def save():
        output.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode())

    def passed(name, facts=None):
        report['tests'].append({'name': name, 'status': 'PASS', 'facts': facts or {}})
        save()
        print(name + ': PASS', flush=True)

    save()
    try:
        api = NativeAPI()
        status, headers, data = api.request('/api/session.cgi')
        assert status == 401, status
        passed(gate, {'httpStatus': status})
        gate = 'native-login'
        api.login()
        passed(gate)
        for endpoint in ('session.cgi', 'broray/info.cgi', 'home/summary.cgi', 'servers/summary.cgi', 'subscriptions/list.cgi', 'servers/auto-switch-status.cgi'):
            gate = endpoint
            status, headers, data = api.request('/api/' + endpoint)
            assert status == 200 and data.get('success') is not False and data.get('ok') is not False, (status, data.get('error'))
            value = data.get('data', data)
            facts = {'httpStatus': status, 'noStore': 'no-store' in headers.get('Cache-Control', '')}
            assert facts['noStore']
            if endpoint == 'broray/info.cgi':
                facts.update(version=value.get('version'), releaseId=value.get('releaseId'))
                assert facts['version'] == '2.0.0'
            if endpoint == 'servers/summary.cgi':
                facts.update(serverCount=len(value.get('servers', [])), activeServerPresent=bool(value.get('activeServerId')))
            if endpoint == 'subscriptions/list.cgi':
                facts['subscriptionCount'] = len(value if isinstance(value, list) else value.get('subscriptions', value.get('items', [])))
            passed(gate, facts)
        report['status'] = 'PASS_NATIVE_LOGIN_AND_READ_ONLY_BACKEND'
    except Exception as error:
        report.update(status='FAIL_FIRST_ERROR', failedGate=gate, errorType=type(error).__name__, error=str(error)[:400], nextCorrectedRevision='DIAGNOSE_BEFORE_RETRY')
        save()
        print(json.dumps({'status': report['status'], 'failedGate': gate, 'errorType': type(error).__name__}), flush=True)
        raise SystemExit(1)
    finally:
        save()
    print(json.dumps({'status': report['status'], 'tests': len(report['tests']), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
