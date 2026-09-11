#!/usr/bin/env python3
"""Linux-only CI E2E regression; never controls the user's desktop/browser."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import threading

from playwright.sync_api import sync_playwright, expect
from r0013_ui_preview import Preview, Handler, USER, PASSWORD

REVISION='p66-browser-dialog-capable-surface'


def main():
    assert sys.platform == 'linux', 'This harness is only for disposable Linux CI'
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    fixture=Preview(('127.0.0.1',0),Handler,out/'fixture.json',revision=REVISION)
    thread=threading.Thread(target=fixture.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(fixture.server_port)
    records=[];failed=False;gate='browser-start';errors=[];screenshots=[]
    def persist():
        value=dict(stage='R0013',revision=REVISION,status='FAIL_FIRST_ERROR' if failed else 'IN_PROGRESS',
                   tests=records,candidateReady=False,boundary='Actual prepared frontend and Chromium; invented loopback HTTP API fixtures only',
                   screenshots=screenshots,scriptErrors=errors,sourceFiles={p:hashlib.sha256(b).hexdigest() for p,b in fixture.files.items()})
        (out/'result.json').write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())
    def passed(detail=None):
        records.append(dict(name=gate,status='PASS',detail=detail));persist();print(json.dumps(records[-1]),flush=True)
    def posts(endpoint):
        return sum(r['endpoint']==endpoint and r['method']=='POST' for r in fixture.requests)
    persist()
    try:
        with sync_playwright() as api:
            browser=api.chromium.launch(headless=True)
            context=browser.new_context(viewport={'width':1440,'height':1000})
            # No externally reachable app/user resource belongs to this test.
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(base+'/') else route.abort())
            page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            page.set_default_timeout(5000)
            def goto(name):
                page.goto(base+'/'+name+'?v=2.0.0',wait_until='networkidle')
            def click_dialog(locator,accept):
                observed=[]
                def handle(dialog):
                    observed.append(dict(type=dialog.type,message=dialog.message,accepted=accept))
                    dialog.accept() if accept else dialog.dismiss()
                page.once('dialog',handle);locator.click();assert len(observed)==1,observed
                return observed
            def sub(name):
                return page.locator('section.subscription-card').filter(has=page.get_by_text(name,exact=True))
            def server(identifier):
                return page.locator('[data-server-id="'+identifier+'"]')
            def shot(name):
                path=out/(name+'.png');page.screenshot(path=str(path),full_page=True)
                screenshots.append(dict(path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))

            gate='login-password-show-hide-and-native-form-submit'
            goto('index.html')
            page.locator('#login').fill(USER);page.locator('#password').fill('wrong-fixture')
            page.get_by_role('button',name='Показать пароль',exact=True).click()
            expect(page.locator('#password')).to_have_attribute('type','text')
            page.get_by_role('button',name='Скрыть пароль',exact=True).click()
            expect(page.locator('#password')).to_have_attribute('type','password')
            page.get_by_role('button',name='Войти',exact=True).click()
            expect(page.locator('#login-error')).to_be_visible()
            page.locator('#password').fill(PASSWORD)
            page.get_by_role('button',name='Войти',exact=True).click()
            expect(page).to_have_url(re.compile('/home.html'))
            expect(page.locator('#lightVersion')).to_have_text('2.0.0');passed()

            gate='subscription-create-required-fields-and-success'
            page.get_by_role('link',name='Подписки',exact=True).click()
            add=page.get_by_role('button',name='Добавить подписку',exact=True)
            before=posts('subscriptions/create.cgi');add.click()
            expect(page.get_by_text('Укажите название подписки',exact=True)).to_be_visible()
            page.get_by_role('textbox',name='Название',exact=True).fill('Browser fixture')
            add.click();expect(page.get_by_text('Укажите ссылку подписки',exact=True)).to_be_visible()
            assert posts('subscriptions/create.cgi')==before
            page.get_by_role('textbox',name='Ссылка подписки',exact=True).fill('https://fixture.invalid/subscription')
            add.click();expect(page.get_by_text('Browser fixture',exact=True)).to_be_visible()
            expect(page.get_by_role('textbox',name='Название',exact=True)).to_have_value('')
            assert posts('subscriptions/create.cgi')==before+1;passed()

            gate='subscription-auto-refresh-checkbox-interval-save'
            card=sub('Browser fixture')
            card.get_by_role('checkbox',name='Включить автообновление',exact=True).check()
            card.get_by_role('spinbutton',name='Интервал, минут',exact=True).fill('120')
            card.get_by_role('button',name='Сохранить автообновление',exact=True).click()
            expect(card.get_by_role('checkbox')).to_be_checked()
            expect(card.get_by_role('spinbutton')).to_have_value('120')
            assert fixture.subs[-1]['autoUpdateEnabled'] is True and fixture.subs[-1]['updateIntervalMinutes']==120;passed()

            gate='subscription-refresh-and-delete-cancel-accept'
            card.get_by_role('button',name='Обновить',exact=True).click()
            expect(card.get_by_text(re.compile('Обновлена:'))).to_be_visible()
            before=posts('subscriptions/delete.cgi')
            cancel=click_dialog(card.get_by_role('button',name='Удалить',exact=True),False)
            expect(card.get_by_role('button',name='Удалить',exact=True)).to_be_enabled()
            assert posts('subscriptions/delete.cgi')==before
            accept=click_dialog(card.get_by_role('button',name='Удалить',exact=True),True)
            expect(card).to_have_count(0)
            assert posts('subscriptions/delete.cgi')==before+1;passed(dict(dialogs=cancel+accept))

            gate='server-import-empty-invalid-and-success'
            page.get_by_role('link',name='Серверы',exact=True).click()
            importer=page.get_by_role('button',name='Добавить сервер',exact=True)
            importer.click();expect(page.get_by_text('Вставьте VLESS-ссылку',exact=True)).to_be_visible()
            page.locator('#uri').fill('invalid-fixture');importer.click()
            expect(page.get_by_text('Некорректная VLESS-ссылка',exact=True)).to_be_visible();expect(importer).to_be_enabled()
            page.locator('#uri').fill('vless://11111111-1111-4111-8111-111111111111@192.0.2.13:443?encryption=none#Fixture')
            importer.click();expect(server('fixture-manual')).to_be_visible();expect(page.locator('#uri')).to_have_value('');passed()

            gate='server-up-down-boundaries-exclude-and-failover-save'
            expect(server('fixture-nl').get_by_role('button',name='Переместить выше',exact=True)).to_be_disabled()
            expect(server('fixture-manual').get_by_role('button',name='Переместить ниже',exact=True)).to_be_disabled()
            server('fixture-manual').get_by_role('button',name='Переместить выше',exact=True).click()
            expect(page.locator('#servers > section').nth(1)).to_have_attribute('data-server-id','fixture-manual')
            server('fixture-manual').get_by_role('button',name='Переместить ниже',exact=True).click()
            page.locator('#failoverEnabled').check();page.locator('#failureThreshold').fill('4');page.locator('#cooldownSeconds').fill('900')
            server('fixture-manual').get_by_role('checkbox').check()
            page.get_by_role('button',name='Сохранить настройки',exact=True).click()
            expect(page.locator('#failoverStatus')).to_contain_text('Включено')
            assert fixture.failover==dict(enabled=True,failureThreshold=4,cooldownSeconds=900,orderedServerIds=['fixture-nl','fixture-fi','fixture-manual'],excludedServerIds=['fixture-manual']);passed()

            gate='server-check-activate-active-refusal-delete-cancel-accept'
            card=server('fixture-manual');card.get_by_role('button',name='Проверить',exact=True).click()
            expect(card.get_by_text(re.compile('HTTP 204'))).to_be_visible()
            card.get_by_role('button',name='Активировать',exact=True).click()
            expect(card.get_by_role('button',name='Активен',exact=True)).to_be_disabled()
            click_dialog(card.get_by_role('button',name='Удалить',exact=True),True)
            expect(page.get_by_text('Активный сервер удалить нельзя',exact=True)).to_be_visible()
            expect(card.get_by_role('button',name='Удалить',exact=True)).to_be_enabled()
            server('fixture-nl').get_by_role('button',name='Активировать',exact=True).click()
            expect(card.get_by_role('button',name='Активировать',exact=True)).to_be_enabled()
            before=posts('servers/delete.cgi');click_dialog(card.get_by_role('button',name='Удалить',exact=True),False)
            assert posts('servers/delete.cgi')==before
            click_dialog(card.get_by_role('button',name='Удалить',exact=True),True);expect(card).to_have_count(0);passed()

            gate='home-keenetic-create-repair-and-refresh'
            page.get_by_role('link',name='Главная',exact=True).click()
            expect(page.locator('#keeneticInterfaceName')).to_have_text('ProxyLight0')
            page.get_by_role('button',name='Настроить',exact=True).click()
            expect(page.locator('#keeneticState')).to_have_text('Активен')
            expect(page.locator('#keeneticCreateButton')).to_be_disabled()
            fixture.keenetic['health'].update(severity='warning',operational=False)
            page.get_by_role('button',name='Обновить статус',exact=True).click()
            expect(page.locator('#keeneticRepairButton')).to_be_enabled()
            page.get_by_role('button',name='Исправить',exact=True).click()
            expect(page.locator('#keeneticState')).to_have_text('Активен');passed()

            gate='home-light-update-check-start-and-equal-state'
            page.get_by_role('button',name='Проверить обновление',exact=True).nth(1).click()
            expect(page.locator('#lightInstallButton')).to_be_enabled();page.locator('#lightInstallButton').click()
            expect(page.locator('#lightInstallButton')).to_have_text('Обновлений нет')
            expect(page.locator('#lightInstallButton')).to_be_disabled();passed()

            gate='xray-catalog-same-version-reinstall-cancel-and-accept'
            page.locator('#xrayCheckButton').click()
            expect(page.locator('#xrayInstallButton')).to_have_text('Переустановить 26.9.9')
            expect(page.locator('#xrayReleaseSelect > option')).to_have_count(1)
            before=posts('xray/install.cgi');cancel=click_dialog(page.locator('#xrayInstallButton'),False)
            assert posts('xray/install.cgi')==before;expect(page.locator('#xrayInstallButton')).to_be_enabled()
            accepted=click_dialog(page.locator('#xrayInstallButton'),True)
            expect(page.locator('#xrayInstallButton')).to_be_disabled();expect(page.locator('#xraySelector')).to_be_hidden()
            assert posts('xray/install.cgi')==before+1;passed(dict(dialogs=cancel+accepted))

            gate='xray-prerelease-toggle-select-and-two-consents'
            page.locator('#xrayCheckButton').click();page.locator('#xrayShowPrerelease').check()
            expect(page.locator('#xrayReleaseSelect > option')).to_have_count(2)
            page.locator('#xrayReleaseSelect').select_option('v26.9.10-beta.1')
            dialogs=[]
            def accept_prerelease(dialog):
                dialogs.append(dialog.message);dialog.accept()
            page.on('dialog',accept_prerelease);page.locator('#xrayInstallButton').click()
            expect(page.locator('#xraySelector')).to_be_hidden();page.remove_listener('dialog',accept_prerelease)
            assert len(dialogs)==2,dialogs;passed(dict(dialogs=dialogs))

            gate='home-server-order-link'
            page.get_by_role('link',name='Настроить порядок серверов →',exact=True).click()
            expect(page).to_have_url(re.compile('/servers.html'));passed()

            for width in (390,768,1440):
                page.set_viewport_size({'width':width,'height':900})
                for name in ('home','servers','subscriptions'):
                    gate='responsive-'+name+'-'+str(width);goto(name+'.html')
                    assert page.locator('nav a[aria-current="page"]').count()==1
                    assert page.locator('nav a[aria-current="page"]').get_attribute('href').startswith(name+'.html')
                    measure=page.evaluate('({viewport:innerWidth,document:document.documentElement.scrollWidth})')
                    assert measure['document']<=measure['viewport'],measure
                    shot(name+'-'+str(width));passed(measure)
            gate='javascript-runtime-errors'
            assert not errors,errors;passed()
            context.close();browser.close()
    except Exception as error:
        failed=True;records.append(dict(name=gate,status='FAIL',error=str(error)));persist();print(json.dumps(records[-1]),flush=True)
    finally:
        fixture.shutdown();fixture.server_close();thread.join(timeout=3);fixture.persist();persist()
    report=json.loads((out/'result.json').read_bytes())
    report['status']='FAIL_FIRST_ERROR' if failed else 'PASS_CHROMIUM_CONTROLS_AND_RESPONSIVE_FIXTURE'
    (out/'result.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
    raise SystemExit(1 if failed else 0)


if __name__=='__main__':
    main()
