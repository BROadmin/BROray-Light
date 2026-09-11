#!/usr/bin/env python3
"""Exact prepared CGI/session scripts, real curl, private mock Keenetic HTTP.

Run only via unshare --mount --net --propagation private on a disposable Linux
runner. Canonical /opt and /tmp paths are private tmpfs mounts, not host data.
This does not replace physical native-SCGI or browser acceptance.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time

from build_r0013_release import prepared_app

REVISION = 'p55-native-auth-cgi-session-validation'
APP = Path('/opt/broray-light')
RAM = Path('/tmp/broray-light')
USER, PASSWORD = 'fixture-admin', 'invented-fixture-password'
REALM, CHALLENGE = 'Fixture Keenetic', 'Fixture_Challenge-001'


class NativeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    mode = 'valid'
    gets = 0
    posts = 0
    accepted = 0


class NativeHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        s = self.server
        s.gets += 1
        assert self.path == '/auth'
        self.send_response(200 if s.mode == 'fake-200' else 503 if s.mode == 'unavailable' else 401)
        if s.mode != 'missing-challenge':
            self.send_header('X-NDM-Challenge', CHALLENGE)
        self.send_header('X-NDM-Realm', REALM)
        if s.mode == 'duplicate-realm' or (s.mode == 'duplicate-second-realm' and s.gets == 2):
            self.send_header('X-NDM-Realm', 'Ambiguous')
        if s.mode == 'duplicate-challenge':
            self.send_header('X-NDM-Challenge', 'Ambiguous')
        self.send_header('Set-Cookie', 'native_fixture=challenge; HttpOnly; Path=/auth')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self):
        s = self.server
        s.posts += 1
        raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        body = json.loads(raw)
        md5 = hashlib.md5(f'{USER}:{REALM}:{PASSWORD}'.encode()).hexdigest()
        expected = hashlib.sha256((CHALLENGE + md5).encode()).hexdigest()
        valid = (self.path == '/auth' and body == {'login': USER, 'password': expected}
                 and 'native_fixture=challenge' in self.headers.get('Cookie', '')
                 and s.mode != 'deny-post')
        s.accepted += int(valid)
        self.send_response(200 if valid else 401)
        self.send_header('Content-Length', '0')
        self.end_headers()


class AuthFixture:
    def __init__(self, shell, applets):
        self.shell = shell
        self.files = prepared_app()
        self.server = None
        self.mounts = []
        # Do not inherit user credentials, proxies or product test overrides.
        self.env = {'PATH': '/opt/bin:/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C.UTF-8'}
        for ns in ('mnt', 'net'):
            assert os.readlink('/proc/self/ns/' + ns) != os.readlink('/proc/1/ns/' + ns), 'Private namespace required: ' + ns
        assert os.geteuid() == 0
        subprocess.run(['mount', '--make-rprivate', '/'], check=True, capture_output=True)
        for path in ('/opt', '/tmp'):
            subprocess.run(['mount', '-t', 'tmpfs', '-o', 'size=64m,mode=' + ('1777' if path == '/tmp' else '755'),
                            'r0013-auth-fixture', path], check=True, capture_output=True)
            self.mounts.append((path, os.stat(path).st_dev))
        Path('/opt/bin').mkdir()
        Path('/opt/bin/ash').symlink_to(shell[0])
        # r1 supplies a hexdump call; retain the actual BusyBox implementation.
        names = ['hexdump']
        if applets:
            from r0013_busybox_fixture import APPLETS
            names += list(APPLETS) + ['dd', 'md5sum']
        available = set(subprocess.check_output(['/usr/bin/busybox', '--list'], text=True).splitlines())
        assert set(names) <= available
        for name in names:
            Path('/opt/bin', name).symlink_to('/usr/bin/busybox')
        slot = APP / 'releases/2.0.0-r1/app'
        for name, (data, mode) in self.files.items():
            p = slot / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            p.chmod(mode)
        (APP / 'current').symlink_to('releases/2.0.0-r1', target_is_directory=True)
        for name in ('bin', 'lib', 'share', 'web-new'):
            (APP / name).symlink_to('current/app/' + name, target_is_directory=True)
        for name in ('config', 'servers', 'subscriptions', 'runtime'):
            (APP / name).mkdir(mode=0o700)
        code = '. /opt/broray-light/lib/runtime-environment.sh && brl_ram_child "$BRL_RAM/run/web-new" && brl_ram_child "$BRL_RAM/run/web-new/sessions"'
        r = subprocess.run([*shell, '-c', code], env=self.env, capture_output=True, timeout=30)
        assert r.returncode == 0, r.stderr.decode()
        subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True, capture_output=True)
        self.server = NativeServer(('127.0.0.1', 79), NativeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def mode(self, value):
        self.server.mode = value
        self.server.gets = self.server.posts = self.server.accepted = 0

    def cgi(self, relative, method='POST', body=None, cookie='', raw=None, length=None):
        payload = raw if raw is not None else json.dumps(body or {}).encode()
        env = dict(self.env, REQUEST_METHOD=method, CONTENT_TYPE='application/json',
                   CONTENT_LENGTH=str(len(payload) if length is None else length),
                   HTTP_COOKIE=cookie, HTTP_HOST='brolight.fixture.invalid',
                   QUERY_STRING='', SERVER_PROTOCOL='HTTP/1.1')
        r = subprocess.run([*self.shell, str(APP / 'web-new/api' / relative)], env=env,
                           input=payload, capture_output=True, timeout=40)
        assert r.returncode == 0, dict(endpoint=relative, rc=r.returncode, stderr=r.stderr.decode())
        head, sep, body_bytes = r.stdout.partition(b'\r\n\r\n')
        assert sep, dict(endpoint=relative, malformedCGI=r.stdout.decode(errors='replace'), stderr=r.stderr.decode())
        headers = {}
        for line in head.decode().split('\r\n'):
            key, value = line.split(':', 1)
            assert key.lower() not in headers, 'Duplicate CGI header: ' + key
            headers[key.lower()] = value.strip()
        status = int(headers.get('status', '200 OK').split()[0])
        value = json.loads(body_bytes)
        assert 'no-store' in headers.get('cache-control', '')
        assert headers.get('x-content-type-options') == 'nosniff'
        assert PASSWORD.encode() not in r.stdout + r.stderr, 'Fixture password exposed'
        return status, headers, value

    def login(self, password=PASSWORD):
        return self.cgi('login.cgi', body={'login': USER, 'password': password})

    def durable(self):
        return {str(p.relative_to(APP)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in APP.rglob('*') if p.is_file() and not p.is_symlink()}

    def scratch_clean(self):
        assert not list((RAM / 'tmp').iterdir()), 'Request/probe scratch leaked'
        assert not list((RAM / 'run/web-new').glob('auth.*')), 'Native auth scratch leaked'

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
        for path, device in reversed(self.mounts):
            assert os.stat(path).st_dev == device, 'Fixture mount changed before cleanup'
            subprocess.run(['umount', path], check=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shell', default='/bin/dash')
    parser.add_argument('--busybox', action='store_true')
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    result = args.result.resolve()
    assert not str(result).startswith(('/opt/', '/tmp/')), 'Evidence must survive private mount cleanup'
    shell = [args.shell, 'ash'] if args.busybox else [args.shell]
    records, failed, fixture = [], False, None
    gate = 'fixture'

    def persist():
        value = dict(stage='R0013', revision=REVISION, shell=shell, candidateReady=False,
                     status='FAIL_FIRST_ERROR' if failed else 'IN_PROGRESS', tests=records,
                     scope='Exact prepared CGI/native-auth/session scripts; real curl; mock loopback Keenetic HTTP; no physical SCGI/browser acceptance')
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text(json.dumps(value, indent=2) + '\n')

    def passed(detail=None):
        records.append(dict(name=gate, status='PASS', detail=detail))
        print(json.dumps(records[-1]), flush=True)
        persist()

    persist()
    try:
        fixture = AuthFixture(shell, args.busybox)
        before = fixture.durable()
        gate = 'valid-native-challenge-response-and-private-session'
        status, headers, value = fixture.login()
        assert status == 200 and value['ok'] and value['user'] == USER, (status, value)
        cookie = headers['set-cookie'].split(';')[0]
        token = cookie.split('=', 1)[1]
        assert re.fullmatch('[0-9a-f]{64}', token)
        assert all(flag in headers['set-cookie'] for flag in ['Path=/', 'HttpOnly', 'SameSite=Strict', 'Max-Age=1800'])
        session = RAM / 'run/web-new/sessions' / token
        assert session.stat().st_uid == 0 and session.stat().st_mode & 0o777 == 0o600
        assert session.parent.stat().st_mode & 0o777 == 0o700
        assert PASSWORD not in session.read_text()
        assert fixture.server.gets == 2 and fixture.server.accepted == 1
        fixture.scratch_clean()
        passed(dict(nativeHandshakeVerified=True, privateRamSession=True))

        gate = 'session-refresh-and-expiry'
        old = json.loads(session.read_bytes())
        old['expiresAt'] = int(time.time()) + 30
        session.write_text(json.dumps(old))
        status, _, value = fixture.cgi('session.cgi', 'GET', cookie=cookie)
        assert status == 200 and value['authenticated'] and value['expiresAt'] > old['expiresAt']
        old['expiresAt'] = 1
        session.write_text(json.dumps(old))
        assert fixture.cgi('session.cgi', 'GET', cookie=cookie)[0] == 401 and not session.exists()
        passed()

        for mode in ('wrong-password', 'deny-post', 'fake-200', 'unavailable', 'missing-challenge', 'duplicate-realm', 'duplicate-challenge', 'duplicate-second-realm'):
            gate = 'native-refusal-' + mode
            fixture.mode('valid' if mode == 'wrong-password' else mode)
            status, headers, value = fixture.login('wrong-fixture-password' if mode == 'wrong-password' else PASSWORD)
            expected = 401 if mode in ('wrong-password', 'deny-post') else 503
            assert status == expected and not value['ok'] and 'set-cookie' not in headers, (status, value)
            assert fixture.server.accepted == 0 and not list(session.parent.iterdir())
            if expected == 503:
                assert fixture.server.posts == 0, 'Ambiguous backend received credentials'
            fixture.scratch_clean()
            passed(dict(httpStatus=expected, noSession=True))

        fixture.mode('valid')
        for raw, length in [(b'{', 1), (b'[]', 2), (b'{}', 9), (b'{}', 0), (b'{}', 9000)]:
            gate = 'login-malformed-body-' + str(len(records))
            assert fixture.cgi('login.cgi', raw=raw, length=length)[0] == 400
            assert fixture.server.posts == 0
            fixture.scratch_clean()
            passed()
        gate = 'login-method-guard'
        assert fixture.cgi('login.cgi', 'GET')[0] == 405
        passed()

        for name in sorted(fixture.files):
            if not name.startswith('web-new/api/') or not name.endswith('.cgi'):
                continue
            endpoint = name.removeprefix('web-new/api/')
            if endpoint in ('login.cgi', 'logout.cgi'):
                continue
            gate = 'unauthenticated-api-' + endpoint
            statuses = [fixture.cgi(endpoint, method)[0] for method in ('GET', 'POST')]
            assert 401 in statuses and all(s in (401, 405) for s in statuses), statuses
            assert fixture.durable() == before, 'Unauthenticated request changed application/data'
            fixture.scratch_clean()
            passed(dict(methods=['GET', 'POST'], httpStatuses=statuses))

        gate = 'logout-invalidates-session'
        fixture.mode('valid')
        status, headers, _ = fixture.login()
        assert status == 200
        cookie = headers['set-cookie'].split(';')[0]
        status, headers, value = fixture.cgi('logout.cgi', cookie=cookie)
        assert status == 200 and value['ok'] and 'Max-Age=0' in headers['set-cookie']
        assert fixture.cgi('session.cgi', 'GET', cookie=cookie)[0] == 401
        assert not list(session.parent.iterdir())
        fixture.scratch_clean()
        passed()
    except Exception as error:
        failed = True
        records.append(dict(name=gate, status='FAIL', error=str(error)))
        print(json.dumps(records[-1]), flush=True)
        persist()
    finally:
        if fixture:
            try:
                fixture.close()
            except Exception as error:
                failed = True
                records.append(dict(name='fixture-cleanup', status='FAIL', error=str(error)))
        persist()
    value = json.loads(result.read_bytes())
    value['status'] = 'FAIL_FIRST_ERROR' if failed else 'PASS_NATIVE_HTTP_CGI_AND_SESSION_BOUNDARIES'
    result.write_text(json.dumps(value, indent=2) + '\n')
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
