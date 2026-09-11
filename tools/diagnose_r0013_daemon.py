#!/usr/bin/env python3
"""Read-only shell-resolution diagnostic, not a retry of P60 daemon lifecycle."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import r0013_busybox_fixture

assert len(sys.argv) == 2
records = []
utilities = r0013_busybox_fixture.enable()
try:
    code = '''
sleep_path="$(command -v sleep)"
printf 'command_v_sleep=%s\n' "$sleep_path"
readlink -f "$sleep_path"
printf 'readlink_exit=%s\n' "$?"
printf 'shell_exe='
readlink /proc/$$/exe
printf 'external_path_sleep='
which sleep
'''
    for shell in (['/bin/dash'], ['/usr/bin/busybox','ash']):
        r = subprocess.run([*shell,'-c',code], env=os.environ, capture_output=True, text=True, timeout=5)
        records.append(dict(shell=shell,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
finally:
    utilities.cleanup()
report = dict(stage='R0013',revision='p61-busybox-idle-start-diagnostic',
              status='DIAGNOSTIC_CAPTURED_NOT_ACCEPTANCE', tests=records,
              daemonExecuted=False, candidateReady=False,
              sourceSha256=hashlib.sha256(Path('packaging/r0013-overlay/app/bin/broray-lightd').read_bytes()).hexdigest())
Path(sys.argv[1]).write_bytes((json.dumps(report,indent=2)+'\n').encode())
print(json.dumps(report))
