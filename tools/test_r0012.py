#!/usr/bin/env python3
"""R0012 relocation, WebUI preservation, and inherited isolated acceptance."""

from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

import test_r0011 as inherited


STAGE = "R0012"
RELEASE_ID = "1.0.0-r3"
WEB_ASSET_CACHE_TOKEN = "1.0.0-r3-r0012"
PREVIOUS_RELEASE_ID = "1.0.0-r2"
NEWER_RELEASE_ID = "1.0.0-r4"


class PageAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.navigation: list[str] = []
        self.buttons = 0
        self.details = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(str(values["id"]))
        href = str(values.get("href") or "")
        target = href.split("?", 1)[0]
        if tag == "a" and target in {"home.html", "servers.html", "subscriptions.html"}:
            self.navigation.append(target)
        if tag == "button":
            self.buttons += 1
        if tag == "details":
            self.details += 1


def require(text: str, fragments: tuple[str, ...], label: str) -> None:
    missing = [fragment for fragment in fragments if fragment not in text]
    if missing:
        raise RuntimeError(f"{label} missing: {missing}")


def reject(text: str, fragments: tuple[str, ...], label: str) -> None:
    present = [fragment for fragment in fragments if fragment in text]
    if present:
        raise RuntimeError(f"{label} unexpectedly present: {present}")


def source_audit(repo: Path) -> None:
    readme = (repo / "README.md").read_text(encoding="utf-8")
    require(
        readme,
        (
            "# BROray-Light",
            "## Требования",
            "## Установка",
            "## Вход в WebUI",
            "## Первоначальная настройка",
            "## Главная",
            "## Серверы",
            "### Дубли",
            "## Подписки",
            "### Автообновление",
            "## Автопереключение серверов",
            "## Обновление и переустановка",
            "## Диагностика",
            "## Резервная копия и сохранность данных",
            "## Удаление",
            "## Безопасность",
            "https://docs.brovibe.cloud/broray/#broray-light",
            "v1.0.0-r3",
            "broray-light-install-1.0.0-r3.sh",
            "https://brolight.ВАШЕ-ИМЯ.keenetic.link/",
            "от 5 до 10080 минут",
            "Активный сервер удалить нельзя",
        ),
        "Russian GitHub guide",
    )
    companion = (repo / "docs" / "USER-GUIDE-RU.md").read_text(encoding="utf-8")
    require(
        companion,
        ("Stable `1.0.0-r3`", "v1.0.0-r3", "## Быстрый путь", "## Ежедневная работа", "## Контроль состояния"),
        "companion guide",
    )

    web = repo / "packaging" / "app-overlay" / "web-new"
    home_html = (web / "home.html").read_text(encoding="utf-8")
    home_js = (web / "assets" / "js" / "home.js").read_text(encoding="utf-8")
    css = (web / "assets" / "css" / "allpage.css").read_text(encoding="utf-8")
    reject(
        home_html,
        ('class="card guide-card"', 'id="guideTitle"', "Как пользоваться BROray-Light", "copy-guide-button", "<details"),
        "embedded Home guide",
    )
    reject(home_js, ("copyGuideText", "setupGuide", ".copy-guide-button"), "guide JavaScript")
    reject(css, (".guide-", ".copy-guide-button"), "guide CSS")
    require(home_js, ("document.addEventListener('DOMContentLoaded', refreshHome);",), "Home startup")
    require(
        home_html,
        (
            'id="activeServer"',
            'id="failover"',
            'id="keeneticInterfaceName"',
            'id="keeneticState"',
            'id="keeneticCreateButton"',
            'id="keeneticRepairButton"',
            'id="xrayInstallButton"',
            'id="lightInstallButton"',
            "keeneticAction('create')",
            "keeneticAction('repair')",
            "refreshHome()",
            "xrayCheck()",
            "xrayInstall()",
            "lightCheck()",
            "lightInstall()",
        ),
        "Home functional controls",
    )
    require(
        home_js,
        (
            "api/home/summary.cgi",
            "api/broray/info.cgi",
            "api/servers/auto-switch-status.cgi",
            "api/keenetic/",
            "api/xray/update-check.cgi",
            "api/xray/update.cgi",
            "api/broray/update-check.cgi",
            "api/broray/update-start.cgi",
        ),
        "Home endpoint bindings",
    )
    audit = PageAudit()
    audit.feed(home_html)
    audit.close()
    if len(audit.ids) != len(set(audit.ids)):
        raise RuntimeError("Home contains duplicate element IDs")
    if sorted(set(audit.navigation)) != ["home.html", "servers.html", "subscriptions.html"]:
        raise RuntimeError(f"functional WebUI navigation changed: {audit.navigation}")
    if audit.buttons != 7 or audit.details != 0:
        raise RuntimeError(f"Home functional shape changed: buttons={audit.buttons} details={audit.details}")

    stale_hits: list[str] = []
    cache_hits = 0
    page_token = f"?v={RELEASE_ID}"
    cache_token = f"?v={WEB_ASSET_CACHE_TOKEN}"
    for path in sorted(web.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "1.0.0-r1" in text or "1.0.0-r2" in text or "r0011" in text:
            stale_hits.append(path.relative_to(repo).as_posix())
        cache_hits += text.count(cache_token)
    if stale_hits:
        raise RuntimeError(f"stale WebUI release tokens remain: {stale_hits}")
    if cache_hits != 16:
        raise RuntimeError(f"cache token count is {cache_hits}, expected 16")
    for page_name in ("home.html", "servers.html", "subscriptions.html"):
        page = (web / page_name).read_text(encoding="utf-8")
        for target in ("home.html", "servers.html", "subscriptions.html"):
            if f'href="{target}{page_token}"' not in page:
                raise RuntimeError(f"versioned navigation missing in {page_name}: {target}")

    policy = (repo / "packaging" / "opkg" / "broray-light-web-publish-policy.sh").read_text(encoding="utf-8")
    if policy.count("BRORAY_LIGHT_WEB_POLICY_CANDIDATE_ID='1.0.0-r3'") != 1 or \
       policy.count("BRORAY_LIGHT_WEB_POLICY_CANDIDATE_ID\" = '1.0.0-r3'") != 1:
        raise RuntimeError("Web publication policy candidate ID is not exact r3")
    builder = (repo / "tools" / "build_r0012_release.py").read_text(encoding="utf-8")
    require(
        builder,
        (
            'RELEASE_ID = "1.0.0-r3"',
            'WEB_ASSET_CACHE_TOKEN = "1.0.0-r3-r0012"',
            "R0011_UPDATER_SIZE = 131458",
            "cab97b6efd11a249cada2c7ceff540f732493ea11163fa5377b083ae450723ca",
            'documentation["homeGuideIncluded"] = False',
        ),
        "R0012 builder",
    )


def built_audit(repo: Path, build: Path) -> None:
    manifest = json.loads((build / "RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("stage") != STAGE or manifest.get("releaseId") != RELEASE_ID:
        raise RuntimeError("R0012 release manifest identity mismatch")
    documentation = manifest.get("documentation", {})
    if documentation.get("homeGuideIncluded") is not False:
        raise RuntimeError("R0012 manifest does not record embedded guide removal")
    import hashlib
    for field, path in (
        ("readmeSha256", repo / "README.md"),
        ("userGuideSha256", repo / "docs" / "USER-GUIDE-RU.md"),
    ):
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if documentation.get(field) != actual:
            raise RuntimeError(f"R0012 documentation hash mismatch: {field}")


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    source_audit(repo)
    if "--source-only" in sys.argv:
        sys.argv.remove("--source-only")
        print(json.dumps({"stage": STAGE, "status": "PASS", "sourceAudit": "PASS"}, sort_keys=True))
        return 0

    build = None
    if "--build" in sys.argv:
        index = sys.argv.index("--build")
        if index + 1 < len(sys.argv):
            build = Path(sys.argv[index + 1]).resolve()
    if build is None:
        raise RuntimeError("--build is required")
    built_audit(repo, build)

    inherited.RELEASE_ID = RELEASE_ID
    inherited.WEB_ASSET_CACHE_TOKEN = WEB_ASSET_CACHE_TOKEN
    inherited.PREVIOUS_RELEASE_ID = PREVIOUS_RELEASE_ID
    inherited.NEWER_RELEASE_ID = NEWER_RELEASE_ID
    legacy = inherited.load_legacy(repo)
    return int(legacy.main())


if __name__ == "__main__":
    raise SystemExit(main())
