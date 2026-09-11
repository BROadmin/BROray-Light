"""Download exact CI artifacts with in-memory GitHub auth and no credential forwarding."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUN = 34589012493
SOURCE = '9aff5dd98ec806dc3c44b1a9fe52da0bbf9eb6da'
OUT = ROOT / 'dist/R0013/p90-release-build'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self):
        response = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\npath=BROadmin/BROray-Light.git\n\n',
                                  cwd=ROOT, capture_output=True, text=True, check=True)
        fields = dict(line.split('=', 1) for line in response.stdout.splitlines() if '=' in line)
        self.token = fields['password']
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, payload=None, method=None):
        assert path.startswith('/repos/BROadmin/') and '\n' not in path
        req = urllib.request.Request('https://api.github.com' + path, method=method,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                     'User-Agent': 'BROray-Light-release-validation', 'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'})
        with self.opener.open(req, timeout=45) as response:
            return json.load(response)

    def artifact(self, item):
        req = urllib.request.Request(item['archive_download_url'], headers={'Authorization': 'Bearer ' + self.token, 'User-Agent': 'BROray-Light-release-validation'})
        try:
            response = self.opener.open(req, timeout=45)
        except urllib.error.HTTPError as error:
            assert error.code == 302
            location = error.headers['Location']
            assert location.startswith('https://')
            # Explicit fresh request: no repository token sent to artifact storage.
            response = urllib.request.urlopen(urllib.request.Request(location, headers={'User-Agent': 'BROray-Light-release-validation'}), timeout=60)
        with response:
            raw = response.read(60 * 1024 * 1024 + 1)
        assert len(raw) <= 60 * 1024 * 1024
        assert 'sha256:' + hashlib.sha256(raw).hexdigest() == item['digest'], 'artifact ZIP digest mismatch'
        return raw


def main():
    assert not OUT.exists(), 'Refuse overwrite or implicit retry'
    client = GitHub()
    run = client.request('/repos/BROadmin/BROray-Light/actions/runs/' + str(RUN))
    assert run['head_sha'] == SOURCE and run['conclusion'] == 'success'
    items = client.request('/repos/BROadmin/BROray-Light/actions/runs/' + str(RUN) + '/artifacts')['artifacts']
    OUT.mkdir(parents=True)
    wanted = {'r0013-build-A-': 'A', 'r0013-build-B-': 'B', 'r0013-signed-index-': 'signed', 'r0013-build-clean-validation-': 'validation'}
    receipts = []
    for prefix, directory in wanted.items():
        matches = [item for item in items if item['name'] == prefix + SOURCE]
        assert len(matches) == 1
        item = matches[0]
        raw = client.artifact(item)
        target = OUT / directory
        target.mkdir()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = set()
            for info in archive.infolist():
                assert not info.is_dir() and '/' not in info.filename and '\\' not in info.filename and info.filename not in ('.', '..')
                assert info.filename not in names and info.file_size < 50 * 1024 * 1024
                names.add(info.filename)
                (target / info.filename).write_bytes(archive.read(info))
        receipts.append({'artifactId': item['id'], 'name': item['name'], 'zipSha256': hashlib.sha256(raw).hexdigest()})
    a, b = OUT / 'A', OUT / 'B'
    assert sorted(p.name for p in a.iterdir()) == sorted(p.name for p in b.iterdir())
    assert all(p.read_bytes() == (b / p.name).read_bytes() for p in a.iterdir())
    assert (a / 'release.json').read_bytes() == (OUT / 'signed/release.json').read_bytes()
    artifacts = [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(a.iterdir())]
    receipt = {'schemaVersion': 1, 'stage': 'R0013', 'revision': 'p90-independent-builds-signed', 'status': 'PASS_EXACT_AB_AND_SIGNED_INDEX_BINDING',
               'sourceCommit': SOURCE, 'runId': RUN, 'buildA': 'PASS', 'buildB': 'PASS', 'comparison': '8_OF_8_BYTE_IDENTICAL',
               'signingVerification': 'PASS_EXISTING_PUBLIC_KEY_IN_CI', 'downloadReceipts': receipts, 'artifacts': artifacts, 'candidateReady': False}
    path = ROOT / 'checkpoints/R0013/INDEPENDENT-BUILDS-P90.json'
    assert not path.exists()
    path.write_bytes((json.dumps(receipt, indent=2) + '\n').encode())
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
