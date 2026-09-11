#!/usr/bin/env python3
"""Bounded local-only correction of this turn's checksum newline writes."""
import json
import subprocess
from diagnose_r0013_xray_external import CHECKPOINTS as CP, REPO, digest, now, seal


def main():
    failure = CP / 'process-failures/FAILURE-P89-SEAL-V1-SIDECAR-NEWLINES.json'
    failure.with_name(failure.name + '.sha256').write_text(digest(failure.read_bytes()) + '  ' + failure.name + '\n', encoding='ascii', newline='\n')
    tracked = subprocess.check_output(['git', 'ls-files', '-z', 'checkpoints/R0013'], cwd=REPO).decode().split('\0')
    current = {'CHECKPOINT.json.sha256', 'REPORT.md.sha256', 'VALIDATION.json.sha256', 'SHA256SUMS.sha256'}
    historical = [p for p in tracked if p.endswith('.sha256') and p.rsplit('/', 1)[-1] not in current]
    restorations = []
    # Plan all rewrites first; unexpected content changes fail closed.
    for name in historical:
        path = REPO / name
        old = subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=REPO)
        present = path.read_bytes()
        assert present.replace(b'\r\n', b'\n') == old.replace(b'\r\n', b'\n'), 'Not a newline-only accidental change: ' + name
        if present != old:
            restorations.append((path, old))
    for path, old in restorations:
        path.write_bytes(old)
    receipt = seal(CP / 'EVIDENCE-INTEGRITY-P89-V2.json', {
        'schemaVersion': 1, 'revision': 'p89-seal-v2', 'at': now(), 'status': 'PASS_HISTORICAL_SIDECARS_RESTORED',
        'failure': failure.relative_to(REPO).as_posix(), 'historicalSidecarsVerified': len(historical),
        'newlineOnlySidecarsRestored': len(restorations), 'restoredExactlyToCleanPreTurnGitBytes': True,
        'routerTestsRepeated': False, 'routerChanged': False, 'compatibilityResultsChanged': False,
        'files': [{'path': p.relative_to(REPO).as_posix(), 'sha256': digest(data)} for p, data in restorations]})
    with (REPO / 'project/WORKLOG.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'at': now(), 'stage': 'R0013_P89', 'revision': 'p89-seal-v1', 'status': 'FIRST_ERROR',
            'event': 'Checksum formatter changed historical sidecar newline bytes; no router/test/source changes.',
            'failure': failure.relative_to(REPO).as_posix(), 'sha256': digest(failure.read_bytes()), 'nextExactAction': 'P89_SEAL_V2_EXACT_BYTE_RESTORATION'}) + '\n')
        stream.write(json.dumps({'at': now(), 'stage': 'R0013_P89', 'revision': 'p89-seal-v2', 'status': 'PASS',
            'receipt': receipt, 'nextExactAction': 'RECORD_NEGATIVE_COMPATIBILITY_IN_CANDIDATE_BEFORE_RELEASE_AND_COMPLETE_REMAINING_WEBUI_LIFECYCLE_SIGNING_ACCEPTANCE'}) + '\n')
    state_path = REPO / 'project/R0013-STATE.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    state['xrayExternalDiagnostic']['finalEvidenceAudit'] = receipt
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    for filename in ('CHECKPOINT.json', 'REPORT.md', 'VALIDATION.json'):
        path = CP / filename
        path.with_name(filename + '.sha256').write_text(digest(path.read_bytes()) + '  ' + filename + '\n', encoding='ascii', newline='\n')
    files = sorted(p for p in CP.rglob('*') if p.is_file() and p.name not in ('SHA256SUMS', 'SHA256SUMS.sha256'))
    sums = CP / 'SHA256SUMS'
    sums.write_text(''.join(digest(p.read_bytes()) + '  ' + p.relative_to(CP).as_posix() + '\n' for p in files), encoding='utf-8', newline='\n')
    sums.with_name('SHA256SUMS.sha256').write_text(digest(sums.read_bytes()) + '  SHA256SUMS\n', encoding='ascii', newline='\n')
    for line in sums.read_text().splitlines():
        expected, name = line.split('  ', 1)
        assert digest((CP / name).read_bytes()) == expected, name
    for name in historical:
        assert (REPO / name).read_bytes() == subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=REPO), name
    print(json.dumps({'status': 'PASS', 'sha256Entries': len(files), 'historicalSidecarsVerified': len(historical),
                      'newlineOnlyRestored': len(restorations), 'sha256SumsSha256': digest(sums.read_bytes()), 'receipt': receipt}))


if __name__ == '__main__':
    main()
