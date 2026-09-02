#!/usr/bin/env python3
"""R0011 documentation and inherited isolated-root acceptance harness."""

from __future__ import annotations

import importlib.util
import sys
from html.parser import HTMLParser
from pathlib import Path


RELEASE_ID = "1.0.0-r2"
WEB_ASSET_CACHE_TOKEN = "1.0.0-r2-r0011"
PREVIOUS_RELEASE_ID = "1.0.0-r1"
NEWER_RELEASE_ID = "1.0.0-r3"


class HomeAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.copy_targets: list[str] = []
        self.details = 0
        self.navigation: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(str(values["id"]))
        if values.get("data-copy-target"):
            self.copy_targets.append(str(values["data-copy-target"]))
        if tag == "details":
            self.details += 1
        href = str(values.get("href") or "")
        target = href.split("?", 1)[0]
        if tag == "a" and target in {"home.html", "servers.html", "subscriptions.html"}:
            self.navigation.append(target)


def require(text: str, fragments: tuple[str, ...], label: str) -> None:
    missing = [fragment for fragment in fragments if fragment not in text]
    if missing:
        raise RuntimeError(f"{label} missing: {missing}")


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
            "v1.0.0-r2",
            "broray-light-install-1.0.0-r2.sh",
            "https://brolight.ВАШЕ-ИМЯ.keenetic.link/",
            "от 5 до 10080 минут",
            "Активный сервер удалить нельзя",
        ),
        "Russian GitHub guide",
    )

    companion = (repo / "docs" / "USER-GUIDE-RU.md").read_text(encoding="utf-8")
    require(companion, ("## Быстрый путь", "## Ежедневная работа", "## Контроль состояния"), "companion guide")

    web = repo / "packaging" / "app-overlay" / "web-new"
    home_html = (web / "home.html").read_text(encoding="utf-8")
    home_js = (web / "assets" / "js" / "home.js").read_text(encoding="utf-8")
    css = (web / "assets" / "css" / "allpage.css").read_text(encoding="utf-8")
    require(
        home_html,
        (
            'class="card guide-card"',
            'id="guideTitle"',
            "Как пользоваться BROray-Light",
            "Stable 1.0.0-r2",
            "Требования и установка",
            "Подписки и автообновление",
            "Автопереключение: статусы и настройки",
            "Xray и обновление BROray-Light",
            "Диагностика и безопасное удаление",
            "Полная инструкция на GitHub",
        ),
        "Home guide",
    )
    audit = HomeAudit()
    audit.feed(home_html)
    audit.close()
    if len(audit.ids) != len(set(audit.ids)):
        raise RuntimeError("Home contains duplicate element IDs")
    if audit.details != 7:
        raise RuntimeError(f"Home guide details count is {audit.details}, expected 7")
    if len(audit.copy_targets) != 3 or not set(audit.copy_targets).issubset(set(audit.ids)):
        raise RuntimeError("Home copy controls do not resolve exactly three targets")
    if sorted(set(audit.navigation)) != ["home.html", "servers.html", "subscriptions.html"]:
        raise RuntimeError(f"functional WebUI navigation changed: {audit.navigation}")

    require(
        home_js,
        (
            "async function copyGuideText(buttonElement)",
            "navigator.clipboard && window.isSecureContext",
            "document.execCommand('copy')",
            "document.querySelectorAll('.copy-guide-button')",
            "setupGuide();",
            "refreshHome();",
        ),
        "Home guide JavaScript",
    )
    require(
        css,
        (
            ".guide-card",
            ".guide-quick-grid",
            ".guide-sections summary:focus-visible",
            ".guide-content pre",
            ".guide-status-list",
            "@media (max-width: 700px)",
            ".guide-quick-grid { grid-template-columns: 1fr;",
        ),
        "Home guide styles",
    )

    old_hits: list[str] = []
    cache_hits = 0
    page_token = f"?v={RELEASE_ID}"
    cache_token = f"?v={WEB_ASSET_CACHE_TOKEN}"
    for path in sorted(web.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "1.0.0-r1" in text:
            old_hits.append(path.relative_to(repo).as_posix())
        cache_hits += text.count(cache_token)
    if old_hits:
        raise RuntimeError(f"old WebUI release token remains: {old_hits}")
    if cache_hits != 16:
        raise RuntimeError(f"cache token count is {cache_hits}, expected 16")
    for page_name in ("home.html", "servers.html", "subscriptions.html"):
        page = (web / page_name).read_text(encoding="utf-8")
        for target in ("home.html", "servers.html", "subscriptions.html"):
            if f'href="{target}{page_token}"' not in page:
                raise RuntimeError(f"versioned navigation missing in {page_name}: {target}")

    policy = (repo / "packaging" / "opkg" / "broray-light-web-publish-policy.sh").read_text(encoding="utf-8")
    if policy.count("BRORAY_LIGHT_WEB_POLICY_CANDIDATE_ID='1.0.0-r2'") != 1 or \
       policy.count("BRORAY_LIGHT_WEB_POLICY_CANDIDATE_ID\" = '1.0.0-r2'") != 1:
        raise RuntimeError("Web publication policy candidate ID is not exact r2")
    builder = (repo / "tools" / "build_r0011_release.py").read_text(encoding="utf-8")
    require(
        builder,
        (
            'RELEASE_ID = "1.0.0-r2"',
            'WEB_ASSET_CACHE_TOKEN = "1.0.0-r2-r0011"',
            'RELEASE_TAG = f"v{RELEASE_ID}"',
            "R0010_UPDATER_SHA256",
            '"stage": STAGE',
            '"homeGuideIncluded": True',
        ),
        "R0011 builder",
    )


def load_legacy(repo: Path):
    path = repo / "tools" / "test_r0009.py"
    spec = importlib.util.spec_from_file_location("r0011_legacy_acceptance", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load inherited acceptance harness")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RELEASE_ID = RELEASE_ID
    module.CANDIDATE_ID = RELEASE_ID
    module.WEB_ASSET_CACHE_TOKEN = WEB_ASSET_CACHE_TOKEN
    module.PREVIOUS_RELEASE_ID = PREVIOUS_RELEASE_ID
    module.NEWER_RELEASE_ID = NEWER_RELEASE_ID
    return module


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    source_audit(repo)
    if "--source-only" in sys.argv:
        sys.argv.remove("--source-only")
        print('{"stage":"R0011","status":"PASS","sourceAudit":"PASS"}')
        return 0
    legacy = load_legacy(repo)
    return int(legacy.main())


if __name__ == "__main__":
    raise SystemExit(main())
