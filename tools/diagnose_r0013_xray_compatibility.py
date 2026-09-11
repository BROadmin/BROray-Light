#!/usr/bin/env python3
"""RAM-only, localhost-only diagnostics; never installs or invokes Light controls."""
from __future__ import annotations
import argparse, base64, datetime as dt, getpass, hashlib, io, json, re, sys, time, urllib.request, zipfile
from pathlib import Path
from r0013_target_transport import EXPECTED_KEY, HOST, paramiko
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, x25519
from cryptography.x509.oid import NameOID

REPO = Path(__file__).resolve().parents[1]
TAGS = ['v26.9.9','v26.9.8','v26.7.28','v26.7.11','v26.6.27','v26.3.27','v26.2.6']
ASSET = 'Xray-linux-arm64-v8a.zip'
GENERATOR_SHA = 'dc1c932d9eccef83b25ca5c4eae74c9a1085fdff1bda531f0be16b08bee1041f'
APP_SHA = '57832490c248a75d0286f142c8553e4b5e7a377336b10f648ee2e2dffb206716'
PREFIX = 'export PATH=/opt/bin:/opt/sbin:/usr/bin:/bin; '

def digest(data): return hashlib.sha256(data).hexdigest()
def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def save(path, obj):
    data = (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode()
    with path.open('xb') as f: f.write(data)
    return {'path':path.relative_to(REPO).as_posix(),'sha256':digest(data),'bytes':len(data)}
def fetch(url, limit):
    assert url.startswith(('https://api.github.com/repos/XTLS/Xray-core/','https://github.com/XTLS/Xray-core/releases/download/'))
    req = urllib.request.Request(url,headers={'User-Agent':'BROray-Light-compatibility-diagnostic'})
    with urllib.request.urlopen(req,timeout=45) as r:
        assert r.url.startswith('https:')
        data = r.read(limit+1)
    assert len(data)<=limit
    return data

class Target:
    def __init__(self):
        self.client=paramiko.SSHClient()
        self.client.load_host_keys(str(Path.home()/'.ssh/known_hosts'))
        self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
        password=getpass.getpass('Root password (not saved): ')
        self.client.connect(HOST,username='root',password=password,look_for_keys=False,allow_agent=False,timeout=8,auth_timeout=15,banner_timeout=15)
        del password
        key=self.client.get_transport().get_remote_server_key()
        assert key.get_name()=='ssh-ed25519' and key.get_base64()==EXPECTED_KEY
        self.work=None
        self.files=set()
    def command(self,command,payload=None,timeout=45,check=True):
        c=self.client.get_transport().open_session(timeout=10)
        c.settimeout(timeout); c.exec_command(PREFIX+command)
        if payload is not None: c.sendall(payload)
        c.shutdown_write()
        stdout,stderr=bytearray(),bytearray(); deadline=time.monotonic()+timeout
        while True:
            if c.recv_ready(): stdout.extend(c.recv(65536))
            if c.recv_stderr_ready(): stderr.extend(c.recv_stderr(65536))
            if c.exit_status_ready() and not c.recv_ready() and not c.recv_stderr_ready(): break
            if time.monotonic()>deadline:
                c.close(); raise TimeoutError('Remote result uncertain; no automatic retry')
            time.sleep(.01)
        r=dict(exitCode=c.recv_exit_status(),stdout=stdout.decode('utf-8','replace'),stderr=stderr.decode('utf-8','replace'))
        if check and r['exitCode']: raise RuntimeError(json.dumps(r,ensure_ascii=False))
        return r
    def snapshot(self):
        return self.command('''set -eu
uname -m; uname -r; readlink /opt/broray-light/current
sha256sum /opt/broray-light/runtime/xray /opt/broray-light/current/APP-SHA256SUMS
find /opt/broray-light/config -type f -exec sha256sum {} \\; | sort | sha256sum
for p in /proc/[0-9]*; do
 if [ "$(readlink "$p/exe" 2>/dev/null)" = /opt/broray-light/runtime/xray ]; then
  printf '%s ' "${p##*/}"; awk '{print $22}' "$p/stat"
 fi
done
''')['stdout']
    def prepare(self):
        r=self.command('''set -eu; umask 077
test "$(stat -f -c %T /tmp)" = tmpfs; test "$(uname -m)" = aarch64
test "$(df -k /tmp | awk 'END{print $4}')" -gt 160000
test "$(awk '/MemAvailable:/{print $2}' /proc/meminfo)" -gt 180000
command -v openssl >/dev/null; command -v netstat >/dev/null
for port in 39487 39488 39489 39490; do
 if netstat -lnt | awk '{print $4}' | grep -Eq ":$port$"; then exit 41; fi
done
mktemp -d /tmp/brl-r13-xray-p88.XXXXXX
''')
        self.work=r['stdout'].strip()
        assert re.fullmatch(r'/tmp/brl-r13-xray-p88\.[A-Za-z0-9]{6}',self.work)
        self.command(f'test "$(stat -c %u:%a {self.work})" = 0:700; test ! -L {self.work}')
    def put(self,name,data,mode=0o600):
        assert re.fullmatch(r'[a-zA-Z0-9_.-]+',name) and len(data)<48*1024*1024
        path=self.work+'/'+name; self.files.add(name)
        self.command(f'set -eu; umask 077; test ! -e {path}; test ! -L {path}; set -C; cat >{path}; chmod {mode:o} {path}',data,timeout=120)
        assert self.command(f'sha256sum {path}')['stdout'].split()[0]==digest(data)
    def remove(self,names):
        for name in names:
            assert name in self.files
            path=self.work+'/'+name
            self.command(f'set -eu; test ! -L {path}; test -f {path}; rm -- {path}')
            self.files.remove(name)
    def cleanup(self):
        if not self.work: return {'status':'NOT_CREATED'}
        self.command(f'''set -eu
test ! -L {self.work}; test "$(stat -c %u:%a {self.work})" = 0:700
for p in /proc/[0-9]*; do
 exe="$(readlink "$p/exe" 2>/dev/null || :)"
 case "$exe" in
  {self.work}/xray) kill -TERM "${{p##*/}}" ;;
  /opt/bin/openssl) if tr '\\000' '\\n' <"$p/cmdline" | grep -Fxq '{self.work}/cert.pem'; then kill -TERM "${{p##*/}}"; fi ;;
 esac
done
sleep 1
''')
        names=sorted(self.files)
        for name in names:
            path=self.work+'/'+name
            self.command(f'set -eu; test ! -L {path}; if test -e {path}; then test -f {path}; rm -- {path}; fi')
        self.command(f'rmdir {self.work}; test ! -e {self.work}')
        return {'status':'PASS','temporaryDirectoryRemoved':True,'exactFileCount':len(names)}

def credentials():
    key=ec.generate_private_key(ec.SECP256R1())
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'r0013.test')])
    instant=dt.datetime.now(dt.timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(instant-dt.timedelta(days=1))
          .not_valid_after(instant+dt.timedelta(days=2))
          .add_extension(x509.SubjectAlternativeName([x509.DNSName('r0013.test')]),critical=False)
          .add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True).sign(key,hashes.SHA256()))
    reality=x25519.X25519PrivateKey.generate()
    enc=lambda b:base64.urlsafe_b64encode(b).decode().rstrip('=')
    return (key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()),
            cert.public_bytes(serialization.Encoding.PEM),
            enc(reality.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())),
            enc(reality.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)))

def fixture(t,network,security,vision,public,private):
    profile={'id':'synthetic','address':'127.0.0.1','port':39489,'uuid':'8e44b972-2d29-46cd-9587-aa807b76f54d',
             'encryption':'none','network':network,'security':security,
             'transport':{'path':'/r0013','host':'r0013.test','serviceName':'r0013'},
             'xhttp':{'path':'/r0013','mode':'auto'},
             'tls':{'serverName':'r0013.test','fingerprint':'chrome','allowInsecure':False},
             'reality':{'serverName':'r0013.test','fingerprint':'chrome','publicKey':public,'shortId':'aabbccdd'}}
    if vision: profile['flow']='xtls-rprx-vision'
    t.put('profile.json',json.dumps(profile).encode()); t.files.add('client.json')
    t.command(f'cd {t.work}; jq -n --slurpfile s profile.json --argjson socksPort 39490 --arg logLevel warning -f generator.jq > client.json')
    client=json.loads(t.command(f'cat {t.work}/client.json')['stdout'])
    stream=client['outbounds'][0]['streamSettings'].copy()
    if security=='tls': stream['tlsSettings']={'certificates':[{'certificateFile':t.work+'/cert.pem','keyFile':t.work+'/key.pem'}]}
    elif security=='reality': stream['realitySettings']={'dest':'127.0.0.1:39487','show':True,'serverNames':['r0013.test'],'privateKey':private,'shortIds':['aabbccdd']}
    user={'id':profile['uuid']}
    if vision: user['flow']=profile['flow']
    server={'log':{'loglevel':'info'},'inbounds':[{'listen':'127.0.0.1','port':39489,'protocol':'vless',
            'settings':{'clients':[user],'decryption':'none'},'streamSettings':stream}],
            'outbounds':[{'protocol':'freedom','settings':{'finalRules':[{'action':'allow','network':'tcp','ip':['127.0.0.1'],'port':39488}]}}]}
    t.put('server.json',json.dumps(server).encode())
    target_config={'log':{'loglevel':'warning'},'inbounds':[{'listen':'127.0.0.1','port':39487,'protocol':'vless',
                   'settings':{'clients':[{'id':profile['uuid']}],'decryption':'none'},
                   'streamSettings':{'network':'tcp','security':'tls','tlsSettings':{'minVersion':'1.3','alpn':['h2','http/1.1'],
                   'certificates':[{'certificateFile':t.work+'/cert.pem','keyFile':t.work+'/key.pem'}]}}}],
                   'outbounds':[{'protocol':'blackhole'}]}
    t.put('target.json',json.dumps(target_config).encode())
    return client,server

LOGS=['client-test.log','server-test.log','client.log','server.log','curl.log','target.log','response.html']
def test_case(t,name):
    w=t.work; t.files.update(LOGS)
    script=f'''set -eu; cd {w}
export SSL_CERT_FILE={w}/cert.pem
./xray run -test -c server.json >server-test.log 2>&1
./xray run -test -c client.json >client-test.log 2>&1
sp=; cp=; tp=
cleanup() {{
 for p in "$cp" "$sp" "$tp"; do
  test -n "$p" || continue
  if test "$(readlink /proc/$p/exe 2>/dev/null)" = {w}/xray; then kill -TERM "$p" 2>/dev/null || :; fi
 done
 test -z "$cp" || wait "$cp" 2>/dev/null || :
 test -z "$sp" || wait "$sp" 2>/dev/null || :
 test -z "$tp" || wait "$tp" 2>/dev/null || :
}}
trap cleanup EXIT HUP INT TERM
./xray run -c target.json >target.log 2>&1 & tp=$!
sleep 1
kill -0 "$tp"
netstat -lnt | grep -q '127.0.0.1:39487 '
./xray run -c server.json >server.log 2>&1 & sp=$!
./xray run -c client.json >client.log 2>&1 & cp=$!
ready=false
for n in $(seq 1 8); do
 kill -0 "$sp"; kill -0 "$cp"
 if netstat -lnt | grep -q '127.0.0.1:39489 ' && netstat -lnt | grep -q '127.0.0.1:39490 '; then ready=true; break; fi
 sleep 1
done
test "$ready" = true
curl -q --noproxy '' --socks5-hostname 127.0.0.1:39490 -k --fail --silent --show-error --max-time 12 https://127.0.0.1:39488/ -o response.html 2>curl.log
grep -qi '<HTML>' response.html
sha256sum response.html
'''
    r=t.command(script,timeout=25,check=False); r['name']=name; r['logs']={}
    for log in LOGS[:-1]:
        r['logs'][log]=t.command(f'if test -f {w}/{log}; then head -c 16384 {w}/{log}; fi')['stdout']
    if r['exitCode']:
        r['logs']['openssl.log']=t.command(f'head -c 16384 {w}/openssl.log')['stdout']
    return r

def main():
    p=argparse.ArgumentParser(); p.add_argument('--revision',default='v5',choices=['v5']); args=p.parse_args()
    out=REPO/('dist/R0013/p88-xray-compat-'+args.revision); out.mkdir(parents=True,exist_ok=False)
    report={'schemaVersion':1,'revision':'p88-xray-compatibility-'+args.revision,'startedAt':now(),
            'architecture':'arm64','kernel':'4.9-ndm-5','product':'BROray-Light','candidateId':'2.0.0-r1','versions':[],
            'candidateReady':False,'installedRuntimeChanged':False,
            'scope':'Official ARM64 execution, installed generator config, localhost VLESS 5 transports none/TLS, TCP Vision TLS/REALITY and XHTTP REALITY; not external subscription acceptance.'}
    t=None
    try:
        raw=fetch('https://api.github.com/repos/XTLS/Xray-core/releases?per_page=30',8*1024*1024)
        (out/'official-releases.json').write_bytes(raw); report['officialMetadataSha256']=digest(raw)
        releases=json.loads(raw)
        chosen=[r for r in releases if not r['draft'] and not r['prerelease']][:2]+[r for r in releases if not r['draft'] and r['prerelease']][:5]
        assert set(r['tag_name'] for r in chosen)==set(TAGS),'catalog changed; revise checkpoint'
        t=Target(); report['before']=t.snapshot()
        assert APP_SHA in report['before'] and 'releases/2.0.0-r1' in report['before']
        generator=t.command('cat /opt/broray-light/lib/server-config-generator.sh')['stdout'].encode()
        assert digest(generator)==GENERATOR_SHA
        jq=generator.decode().split('--arg logLevel "$log_level" \'\n',1)[1].split("' > \"$out\"",1)[0]
        report['generatorSha256']=GENERATOR_SHA; report['generatorJqSha256']=digest(jq.encode())
        t.prepare(); t.put('generator.jq',jq.encode())
        key,cert,private,public=credentials(); t.put('key.pem',key); t.put('cert.pem',cert); t.files.add('openssl.log')
        t.command(f'cd {t.work}; openssl s_server -accept 127.0.0.1:39488 -cert {t.work}/cert.pem -key {t.work}/key.pem -tls1_3 -groups X25519 -www -quiet >openssl.log 2>&1 </dev/null &')
        t.command('sleep 1; curl -q -k --noproxy "*" --fail --silent --show-error --max-time 5 https://127.0.0.1:39488/ | grep -qi "<HTML>"')
        cases=[(n,s,False) for s in ['none','tls'] for n in ['tcp','ws','grpc','httpupgrade','xhttp']]
        cases = [('tcp','reality',True),('xhttp','reality',False)] + cases + [('tcp','tls',True)]
        for tag in TAGS:
            print(f'{tag}: download and SHA-256 verification',flush=True)
            release=next(r for r in chosen if r['tag_name']==tag)
            assets=[a for a in release['assets'] if a['name']==ASSET and a['state']=='uploaded']; assert len(assets)==1
            asset=assets[0]; assert asset['browser_download_url']==f'https://github.com/XTLS/Xray-core/releases/download/{tag}/{ASSET}'
            expected=asset.get('digest','').removeprefix('sha256:'); assert re.fullmatch('[a-f0-9]{64}',expected)
            archive=fetch(asset['browser_download_url'],32*1024*1024)
            assert len(archive)==asset['size'] and digest(archive)==expected
            (out/(tag+'.zip')).write_bytes(archive)
            with zipfile.ZipFile(io.BytesIO(archive)) as z:
                files=[i for i in z.infolist() if i.filename=='xray']; assert len(files)==1 and 0<files[0].file_size<48*1024*1024
                binary=z.read(files[0])
            assert binary[:4]==b'\x7fELF' and binary[18:20]==b'\xb7\x00'
            t.put('xray',binary,0o700)
            version=t.command(f'{t.work}/xray version')['stdout']
            assert version.startswith('Xray '+tag[1:]+' ') and 'linux/arm64' in version
            row={'tag':tag,'prerelease':release['prerelease'],'archiveSha256':expected,'binarySha256':digest(binary),'versionOutput':version,'tests':[]}
            report['versions'].append(row)
            for network,security,vision in cases:
                name=network+'-'+security+('-vision' if vision else '')
                client,server=fixture(t,network,security,vision,public,private)
                result=test_case(t,name)
                result['clientConfigSha256']=digest(json.dumps(client,sort_keys=True).encode())
                result['serverConfigSha256']=digest(json.dumps(server,sort_keys=True).encode())
                row['tests'].append(result)
                print(f'{tag} {name}: '+('PASS' if result['exitCode']==0 else 'FAIL'),flush=True)
                assert result['exitCode']==0,f'FIRST_ERROR {tag} {name}; inspect saved logs'
                t.remove(['profile.json','client.json','server.json','target.json']+LOGS)
            row['status']='PASS_BOUNDED_LOCALHOST'; t.remove(['xray'])
            print(json.dumps(save(out/(tag+'.json'),row)),flush=True)
        report['status']='PASS_BOUNDED_LOCALHOST'
    except Exception as exc:
        failure={'schemaVersion':1,'revision':report['revision'],'at':now(),'status':'FIRST_ERROR','error':str(exc),
                 'cause':'Pending diagnosis from preserved first-run evidence; not automatically a product defect.',
                 'nextRevision':'p88-xray-compatibility-v6-only-after-diagnosis','retryPerformed':False}
        report['status']='FIRST_ERROR'; report['failure']=failure
        save(REPO/('checkpoints/R0013/process-failures/FAILURE-P88-XRAY-COMPATIBILITY-'+args.revision.upper()+'.json'),failure)
        print('FIRST_ERROR: '+str(exc),flush=True)
    finally:
        if t:
            try:
                report['cleanup']=t.cleanup(); report['after']=t.snapshot()
                report['installedStatePreserved']=report['before']==report['after']
                if not report['installedStatePreserved']: report['status']='INSTALLED_STATE_CHANGED_REQUIRES_DIAGNOSIS'
            except Exception as exc:
                report['cleanup']={'status':'FAIL_REQUIRES_DIAGNOSIS','error':str(exc)}; report['status']='CLEANUP_BLOCKED'
            t.client.close()
        report['completedAt']=now()
        print(json.dumps(save(out/'report.json',report)),flush=True)
    return 0 if report['status']=='PASS_BOUNDED_LOCALHOST' else 1
if __name__=='__main__': sys.exit(main())
