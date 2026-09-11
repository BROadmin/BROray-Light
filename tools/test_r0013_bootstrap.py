#!/usr/bin/env python3
"""Linux isolated bootstrap/installer tests. opkg, mount type and service start are boundaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from build_r0013_release import RELEASE_ID, XRAY, prepared_app, primitives
import r0013_inputs as inputs

ROOT = inputs.REPO / "packaging/r0013-overlay"
BINARY = b"#!/bin/sh\necho 'Xray 26.9.9 fixture'\n"
PARAMS = {"RELEASE_ID": RELEASE_ID, "CANDIDATE_ID": RELEASE_ID, "XRAY_VERSION": XRAY["version"],
          "XRAY_BINARY_SHA256": hashlib.sha256(BINARY).hexdigest()}

def render(relative, params):
    text = (ROOT / relative).read_text()
    text = text.replace("@BOOTSTRAP_RAM_HELPERS@", (ROOT / "bootstrap-ram.sh").read_text())
    text = text.replace("@RUNTIME_RAM_HELPERS@", (ROOT / "shared/runtime-ram.sh").read_text())
    for key, value in params.items():
        text = text.replace("@" + key + "@", value)
    assert "@RELEASE_ID@" not in text and "@XRAY_VERSION@" not in text
    return text.encode()

class Fixture:
    def __init__(self, shell):
        self.temp = tempfile.TemporaryDirectory(prefix="r0013-bootstrap-")
        self.root = Path(self.temp.name)
        self.shell = shell
        self.write("tools/stat", b'#!/bin/sh\nif [ "$1" = -f ]; then echo "$FIXTURE_FS_TYPE"; else exec /usr/bin/stat "$@"; fi\n', 0o755)
        (self.root / "tmp").mkdir(mode=0o1777)
        (self.root / "tmp").chmod(0o1777)
        self.env = dict(os.environ, BRORAY_LIGHT_ROOT_PREFIX=str(self.root),
                        BRORAY_LIGHT_SKIP_SERVICE_START="1", FIXTURE_FS_TYPE="tmpfs",
                        PATH=str(self.root / "tools") + ":/usr/bin:/bin")
        self.bootstrap = self.root / "tmp/broray-light-bootstrap"
        self.app = self.root / "opt/broray-light"

    def write(self, name, payload, mode=0o600):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        path.chmod(mode)
        return path

    def run(self, relative, params=PARAMS):
        return subprocess.run([self.shell, "-s"], input=render(relative, params), env=self.env,
                              capture_output=True, timeout=15)

    def pre(self):
        return self.run("system/packaging/opkg/preinst")

    def post(self):
        return self.run("system/packaging/opkg/postinst")

    def data(self):
        self.write("tmp/broray-light-bootstrap/xray-" + XRAY["version"], BINARY, 0o755)
        slot = "opt/broray-light/releases/" + RELEASE_ID + "/"
        app=prepared_app();base=primitives()
        base.source_app_files=lambda repo,modes:[('app/'+name,data,mode) for name,(data,mode) in sorted(app.items())]
        members,_=base.slot_payload(self.root,{})
        for name,data,mode in members:self.write(slot+name,data,mode)
        for relative in ("opt/etc/init.d/S24broray-light", "opt/etc/init.d/S23broray-light-updater",
                         "opt/bin/broray-light-updaterctl", "opt/bin/broray-light-web-publishctl",
                         "opt/libexec/broray-light-updater/broray-light-updater.sh",
                         "opt/libexec/broray-light-updater/minisign",
                         "opt/libexec/broray-light-web-publish/broray-light-web-publish.sh",
                         "opt/libexec/broray-light-web-publish/start-gate.sh",
                         "opt/libexec/broray-light-web-publish/network.sh",
                         "opt/libexec/broray-light-web-publish/policy.sh"):
            self.write(relative, b"#!/bin/sh\nexit 0\n", 0o755)

    def installer(self, corrupt=False, opkg_fail=False):
        package = b"fixture-package"
        source = self.write("source.ipk", b"corrupt" if corrupt else package)
        self.env["BRORAY_LIGHT_PACKAGE_FILE"] = str(source)
        self.env["FIXTURE_OPKG_FAIL"] = "1" if opkg_fail else "0"
        self.write("tools/opkg", b"""#!/bin/sh
[ "$1" = --tmp-dir ] && [ "$3" = install ] || exit 71
case "$2" in "$BRORAY_LIGHT_ROOT_PREFIX/tmp/broray-light-install."??????/opkg) ;; *) exit 72 ;; esac
[ "$TMPDIR" = "$2" ] || exit 73
printf invoked >"$BRORAY_LIGHT_ROOT_PREFIX/opkg-called"
mkdir "$2/scratch"
printf scratch >"$2/scratch/download"
[ "$FIXTURE_OPKG_FAIL" = 0 ] || exit 74
mkdir -p "$BRORAY_LIGHT_ROOT_PREFIX/opt/broray-light/runtime"
printf xray >"$BRORAY_LIGHT_ROOT_PREFIX/opt/broray-light/runtime/xray"
chmod 755 "$BRORAY_LIGHT_ROOT_PREFIX/opt/broray-light/runtime/xray"
ln -s releases/fixture "$BRORAY_LIGHT_ROOT_PREFIX/opt/broray-light/current"
""", 0o755)
        params = dict(PACKAGE_URL="https://invalid.test/package.ipk", PACKAGE_SIZE=str(len(package)),
                      PACKAGE_SHA256=hashlib.sha256(package).hexdigest(), PACKAGE_NAME="package.ipk")
        return self.run("system/packaging/installer/broray-light-install.sh.in", params)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shell", required=True)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0, "Run isolated ownership tests as root on disposable CI, not a router"
    records = []
    def emit(value):
        payload=json.dumps(value,indent=2)+'\n'
        if args.result:
            args.result.parent.mkdir(parents=True,exist_ok=True)
            args.result.write_text(payload)
        print(payload,flush=True)
    def test(name, function):
        fixture = Fixture(args.shell)
        try:
            function(fixture)
            records.append(dict(test=name, status="PASS"))
        except Exception as error:
            emit(dict(stage="R0013", revision="p49-p47-clean-install-ram", status="FAIL_FIRST_ERROR",
                      test=name, error=str(error), completed=records))
            raise
        finally:
            fixture.temp.cleanup()
    def pre_ok(f):
        result = f.pre()
        assert result.returncode == 0, result.stderr.decode()
        assert f.bootstrap.stat().st_mode & 0o777 == 0o700
        assert (f.bootstrap / "owner").stat().st_mode & 0o777 == 0o600
    def clean(f):
        pre_ok(f); f.data()
        result = f.post()
        assert result.returncode == 0, result.stderr.decode()
        assert (f.app / "runtime/xray").read_bytes() == BINARY
        assert (f.app / "current").is_symlink()
        assert not f.bootstrap.exists()
        assert not (f.root/'opt/var/lock').exists()
        for name in ('run','logs','tmp','update'):
            assert (f.app/name).is_symlink() and os.readlink(f.app/name)==str(f.root/'tmp/broray-light'/name)
            assert (f.root/'tmp/broray-light'/name).stat().st_mode&0o777==0o700
        assert (f.root/'tmp/broray-light/run/web-new/sessions').stat().st_mode&0o777==0o700
    def preserve(f):
        pre_ok(f); f.data()
        old = b"#!/bin/sh\necho 'Xray 26.7.28 accepted'\n"
        f.write("opt/broray-light/runtime/xray", old, 0o755)
        result = f.post()
        assert result.returncode == 0, result.stderr.decode()
        assert (f.app / "runtime/xray").read_bytes() == old
        assert not f.bootstrap.exists()
    def wrong_hash(f):
        pre_ok(f); f.data()
        (f.bootstrap / ("xray-" + XRAY["version"])).write_bytes(b"wrong")
        assert f.post().returncode != 0
        assert not (f.app / "runtime/xray").exists() and not f.bootstrap.exists()
    def preoccupied(f):
        f.bootstrap.mkdir()
        sentinel = f.bootstrap / "foreign"
        sentinel.write_text("preserve")
        assert f.pre().returncode != 0
        assert sentinel.read_text() == "preserve"
    def symlink(f):
        target = f.root / "foreign"
        target.mkdir()
        f.bootstrap.symlink_to(target, target_is_directory=True)
        assert f.pre().returncode != 0 and f.bootstrap.is_symlink()
        assert list(target.iterdir()) == []
    def nonram(f):
        f.env["FIXTURE_FS_TYPE"] = "ext4"
        assert f.pre().returncode != 0 and not f.bootstrap.exists()
    def marker_tamper(f):
        pre_ok(f); f.data()
        (f.bootstrap / "owner").write_text("foreign")
        assert f.post().returncode != 0 and f.bootstrap.exists()
        assert not (f.app / "current").exists()
    def foreign_product(f):
        f.write("opt/broray/foreign", b"preserve")
        assert f.pre().returncode != 0 and not f.bootstrap.exists()
    def already_installed(f):
        f.write('opt/broray-light/releases/1.0.0-r1/owned',b'preserve')
        (f.app/'current').symlink_to('releases/1.0.0-r1')
        assert f.pre().returncode != 0 and not f.bootstrap.exists()
        assert os.readlink(f.app/'current')=='releases/1.0.0-r1'
    def manifest_tamper(f):
        pre_ok(f);f.data()
        (f.app/'releases'/RELEASE_ID/'app/web-new/home.html').write_bytes(b'tampered')
        assert f.post().returncode != 0 and not (f.app/'current').exists()
        assert not (f.app/'runtime/xray').exists()
    def installer(f):
        result = f.installer()
        assert result.returncode == 0, result.stderr.decode()
        assert list((f.root / "tmp").iterdir()) == []
    def install_bad_hash(f):
        assert f.installer(corrupt=True).returncode != 0
        assert not (f.root / "opkg-called").exists()
        assert list((f.root / "tmp").iterdir()) == []
    def install_opkg_fail(f):
        assert f.installer(opkg_fail=True).returncode != 0
        assert (f.root / "opkg-called").is_file()
        assert list((f.root / "tmp").iterdir()) == []
    def install_missing_stat_format(f):
        f.write('tools/stat', b'#!/bin/sh\nexit 1\n', 0o755)
        result = f.installer()
        assert result.returncode != 0
        assert b'install Entware coreutils-stat first' in result.stderr
        assert not (f.root / 'opkg-called').exists()
        assert list((f.root / 'tmp').iterdir()) == []
    def install_missing_stat_fs(f):
        f.write('tools/stat', b'#!/bin/sh\n[ "$1" != -f ] || exit 1\nexec /usr/bin/stat "$@"\n', 0o755)
        result = f.installer()
        assert result.returncode != 0
        assert b'stat lacks required filesystem support' in result.stderr
        assert not (f.root / 'opkg-called').exists()
        assert list((f.root / 'tmp').iterdir()) == []
    for name, fn in [("clean-bootstrap-owned-ram-cleaned", clean), ("existing-xray-preserved", preserve),
                     ("bootstrap-hash-refusal-cleaned", wrong_hash), ("occupied-namespace-preserved", preoccupied),
                     ("symlink-namespace-preserved", symlink), ("nonram-refused-before-write", nonram),
                     ("changed-owner-fails-closed-preserves-evidence", marker_tamper),
                     ("full-product-ownership-refused", foreign_product),
                     ("installed-package-overwrite-refused", already_installed),
                     ("tampered-app-slot-refused", manifest_tamper),
                     ("installer-private-opkg-ram-cleanup", installer),
                     ("installer-bad-hash-no-opkg-cleanup", install_bad_hash),
                     ("installer-opkg-failure-cleanup", install_opkg_fail),
                     ("installer-missing-stat-format-before-write", install_missing_stat_format),
                     ("installer-missing-stat-fs-before-write", install_missing_stat_fs)]:
        test(name, fn)
    emit(dict(stage="R0013", revision="p49-p47-clean-install-ram", status="PASS", candidateReady=False,
              mockedBoundaries=["mount type", "opkg", "Xray binary", "service start"], tests=records))

if __name__ == "__main__":
    main()
