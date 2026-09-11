#!/usr/bin/env python3
"""Loopback-only prepared WebUI for visual/control acceptance, NOT a backend.

All API state is invented and memory-only. No external requests, shell actions,
subscription retrieval, installed Xray or router mutation are possible here.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from build_r0013_release import prepared_app

USER = 'fixture-admin'
PASSWORD = 'fixture-only'


class Preview(ThreadingHTTPServer):
    def __init__(self, address, handler, result, revision='p58-browser-control-and-layout-audit'):
        super().__init__(address, handler)
        self.revision = revision
        self.files = {p.removeprefix('web-new/'): data for p, (data, mode) in prepared_app().items() if p.startswith('web-new/') and not p.startswith('web-new/api/')}
        self.result = result
        self.requests = []
        self.servers = [dict(id='fixture-nl', name='NL — Тестовый сервер', address='192.0.2.11', port=443, network='xhttp', security='reality', active=True),
                        dict(id='fixture-fi', name='FI — Резервный сервер', address='192.0.2.12', port=443, network='xhttp', security='reality', active=False)]
        self.subs = [dict(id='fixture-sub', name='Тестовая подписка', serversCount=2, autoUpdateEnabled=False, updateIntervalMinutes=360, lastUpdatedAt='2026-09-11T03:00:00+03:00')]
        self.failover = dict(enabled=False, failureThreshold=3, cooldownSeconds=600, orderedServerIds=['fixture-nl','fixture-fi'], excludedServerIds=[])
        self.keenetic = dict(health=dict(severity='warning', operational=False, facts=dict(interfaceName='ProxyLight0', exists=True)))
        self.xray = '26.9.9'
        self.update_available = True
        self.persist()

    def persist(self):
        self.result.parent.mkdir(parents=True, exist_ok=True)
        self.result.write_text(json.dumps(dict(stage='R0013', revision=self.revision,
            status='VISUAL_FIXTURE_NOT_BACKEND_ACCEPTANCE', candidateReady=False,
            files={p: hashlib.sha256(b).hexdigest() for p,b in sorted(self.files.items())},
            requests=self.requests), ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def json_response(self, data, status=200, cookie=None):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        if cookie:
            self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(body)

    def error(self, message, status=400):
        self.json_response(dict(success=False,error=dict(message=message,code='FIXTURE_REFUSAL')),status)

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def dispatch(self):
        s = self.server
        u = urlsplit(self.path)
        endpoint = u.path.removeprefix('/api/')
        if not u.path.startswith('/api/'):
            key = u.path.lstrip('/') or 'index.html'
            if key not in s.files:
                self.send_error(404)
                return
            payload = s.files[key]
            self.send_response(200)
            self.send_header('Content-Type', mimetypes.guess_type(key)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(payload)
            return
        try:
            n = int(self.headers.get('Content-Length','0'))
            assert 0 <= n <= 65536
            body = json.loads(self.rfile.read(n)) if n else {}
            assert isinstance(body,dict)
        except (AssertionError,ValueError):
            self.error('Некорректный тестовый запрос')
            return
        # Never record supplied credentials, only nonsecret parameter names.
        s.requests.append(dict(endpoint=endpoint,method=self.command,fields=sorted(body),queryKeys=sorted(parse_qs(u.query))))
        s.persist()
        if endpoint == 'login.cgi':
            if self.command != 'POST':
                self.error('Требуется POST',405)
            elif body == dict(login=USER,password=PASSWORD):
                self.json_response(dict(ok=True,user=USER,redirect='/home.html'),cookie='fixture_session=accepted; Path=/; HttpOnly; SameSite=Strict')
            else:
                self.error('Неверные тестовые данные',401)
            return
        if 'fixture_session=accepted' not in self.headers.get('Cookie',''):
            self.error('Требуется тестовый вход',401)
            return
        if endpoint == 'session.cgi':
            self.json_response(dict(ok=True,authenticated=True,user=USER,expiresAt=2000000000))
            return
        if endpoint == 'logout.cgi':
            self.json_response(dict(ok=True),cookie='fixture_session=; Path=/; Max-Age=0')
            return
        value = None
        if endpoint == 'home/summary.cgi':
            value = dict(servers=dict(servers=s.servers,activeServerId=next((x['id'] for x in s.servers if x['active']),None)),connection=dict(connected=True),xray=dict(version=s.xray,running=True),keenetic=s.keenetic)
        elif endpoint == 'broray/info.cgi':
            value = dict(version='2.0.0',releaseChannel='stable')
        elif endpoint == 'servers/auto-switch-status.cgi':
            value = dict(config=s.failover,state={})
        elif endpoint == 'servers/auto-switch-save.cgi':
            s.failover = body
            value = body
        elif endpoint == 'servers/summary.cgi':
            value = dict(servers=s.servers)
        elif endpoint == 'servers/import.cgi':
            if not body.get('uri','').startswith('vless://'):
                self.error('Некорректная VLESS-ссылка')
                return
            s.servers.append(dict(id='fixture-manual',name='Ручной тестовый сервер',address='192.0.2.13',port=443,network='raw',security='none',active=False))
            value = dict(id='fixture-manual')
        elif endpoint in ('servers/check.cgi','servers/activate.cgi','servers/delete.cgi'):
            server = next((x for x in s.servers if x['id'] == body.get('id')),None)
            if not server:
                self.error('Сервер не найден',404)
                return
            if endpoint.endswith('/check.cgi'):
                server['lastCheck'] = dict(success=True,httpStatus=204,latencyMs=42,checkedAt='2026-09-11T03:00:00+03:00')
                value = server['lastCheck']
            elif endpoint.endswith('/activate.cgi'):
                for x in s.servers:
                    x['active'] = x is server
                value = server
            elif server['active']:
                self.error('Активный сервер удалить нельзя',409)
                return
            else:
                s.servers.remove(server)
                value = dict(deleted=True)
        elif endpoint == 'subscriptions/list.cgi':
            value = s.subs
        elif endpoint == 'subscriptions/create.cgi':
            s.subs.append(dict(id='fixture-sub-new',name=body.get('name','Тест'),serversCount=0,autoUpdateEnabled=False,updateIntervalMinutes=360))
            value = s.subs[-1]
        elif endpoint in ('subscriptions/details.cgi','subscriptions/refresh.cgi','subscriptions/delete.cgi'):
            sub = next((x for x in s.subs if x['id'] == parse_qs(u.query).get('id',[''])[0]),None)
            if not sub:
                self.error('Подписка не найдена',404)
                return
            if endpoint.endswith('details.cgi'):
                sub.update(body)
                value = sub
            elif endpoint.endswith('refresh.cgi'):
                sub['lastUpdatedAt'] = '2026-09-11T03:05:00+03:00'
                value = sub
            else:
                s.subs.remove(sub)
                value = dict(deleted=True)
        elif endpoint in ('keenetic/create.cgi','keenetic/repair.cgi'):
            s.keenetic['health'].update(severity='ok',operational=True)
            value = s.keenetic
        elif endpoint == 'xray/update-check.cgi':
            value = dict(currentVersion=s.xray,catalogComplete=True,releases=[
                dict(tagName='v26.9.9',version='26.9.9',installed=True,available=True,prerelease=False,archiveSha256='a'*64,compatibility=dict(status='compatible')),
                dict(tagName='v26.9.10-beta.1',version='26.9.10-beta.1',installed=False,available=True,prerelease=True,archiveSha256='b'*64,compatibility=dict(status='untested'))])
        elif endpoint == 'xray/install.cgi':
            value = dict(success=True)
        elif endpoint == 'broray/update-check.cgi':
            value = dict(installedReleaseId='2.0.0-r1',availableReleaseId='2.0.1-r1' if s.update_available else '2.0.0-r1',updateAvailable=s.update_available)
        elif endpoint == 'broray/update-start.cgi':
            s.update_available = False
            value = dict(success=True)
        else:
            self.error('Неизвестный fixture API: '+endpoint,404)
            return
        self.json_response(dict(success=True,data=value,error=None))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--result',type=Path,required=True)
    args = parser.parse_args()
    with Preview(('127.0.0.1',args.port),Handler,args.result) as server:
        print(json.dumps(dict(url='http://127.0.0.1:'+str(server.server_port),scope='WebUI fixture only')),flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
