"""Disposable PATH mapping for exercising actual BusyBox utilities in Linux CI."""
import os
from pathlib import Path
import subprocess
import tempfile

APPLETS = ('awk', 'cat', 'chmod', 'cmp', 'cp', 'date', 'find', 'grep', 'head', 'id',
           'ln', 'mkdir', 'mktemp', 'mv', 'readlink', 'rm', 'rmdir', 'sed', 'sha256sum',
           'sleep', 'sort', 'stat', 'tar', 'tr', 'uniq', 'wc')


def enable():
    binary = Path('/usr/bin/busybox')
    available = set(subprocess.check_output([str(binary), '--list'], text=True).splitlines())
    assert set(APPLETS) <= available, sorted(set(APPLETS)-available)
    directory = tempfile.TemporaryDirectory(prefix='r0013-busybox-path-', dir='/var/tmp')
    for name in APPLETS:
        (Path(directory.name) / name).symlink_to(binary)
    os.environ['PATH'] = directory.name + os.pathsep + os.environ['PATH']
    return directory
