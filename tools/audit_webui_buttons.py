#!/usr/bin/env python3
"""Audit every BROray-Light WebUI button binding in a built app archive."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from html.parser import HTMLParser
from pathlib import Path


PAGES = {
    "index.html": ("assets/js/login.js",),
    "home.html": ("assets/js/home.js",),
    "servers.html": ("assets/js/servers.js", "assets/js/servers-auto-switch.js"),
    "subscriptions.html": ("assets/js/subscriptions.js",),
}

LISTENER_BINDINGS = {
    ("index.html", "password-toggle"): 'passwordToggle.addEventListener("click"',
    ("index.html", "login-submit"): 'form.addEventListener("submit"',
    ("subscriptions.html", "addSubscription"): "document.getElementById('addSubscription').addEventListener('click', addSub)",
}

ENDPOINTS = {
    "index.html": ("api/login.cgi", "api/session.cgi"),
    "home.html": (
        "api/home/summary.cgi",
        "api/broray/info.cgi",
        "api/servers/auto-switch-status.cgi",
        "api/keenetic/create.cgi",
        "api/keenetic/repair.cgi",
        "api/xray/update-check.cgi",
        "api/xray/update.cgi",
        "api/broray/update-check.cgi",
        "api/broray/update-start.cgi",
    ),
    "servers.html": (
        "api/servers/summary.cgi",
        "api/servers/auto-switch-status.cgi",
        "api/servers/auto-switch-save.cgi",
        "api/servers/import.cgi",
        "api/servers/check.cgi",
        "api/servers/activate.cgi",
        "api/servers/delete.cgi",
    ),
    "subscriptions.html": (
        "api/subscriptions/list.cgi",
        "api/subscriptions/create.cgi",
        "api/subscriptions/details.cgi",
        "api/subscriptions/refresh.cgi",
        "api/subscriptions/delete.cgi",
    ),
}


class ButtonParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.buttons: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "button":
            self.buttons.append({key: value or "" for key, value in attrs})


def read_member(archive: tarfile.TarFile, name: str) -> str:
    member = archive.getmember(name)
    stream = archive.extractfile(member)
    if stream is None:
        raise RuntimeError(f"missing archive member payload: {name}")
    return stream.read().decode("utf-8")


def require(text: str, fragment: str, context: str) -> None:
    if fragment not in text:
        raise RuntimeError(f"missing {context}: {fragment}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-archive", type=Path, required=True)
    args = parser.parse_args()

    static_buttons: list[dict[str, str]] = []
    endpoint_results: list[dict[str, object]] = []
    with tarfile.open(args.app_archive.resolve(), "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        for page, scripts in PAGES.items():
            html = read_member(archive, f"app/web-new/{page}")
            javascript = "\n".join(read_member(archive, f"app/web-new/{script}") for script in scripts)
            parsed = ButtonParser()
            parsed.feed(html)
            for index, button in enumerate(parsed.buttons, start=1):
                button_id = button.get("id", "")
                onclick = button.get("onclick", "")
                binding = ""
                if onclick:
                    match = re.match(r"\s*([A-Za-z_$][\w$]*)\s*\(", onclick)
                    if not match:
                        raise RuntimeError(f"unrecognized onclick in {page} button {index}: {onclick}")
                    function_name = match.group(1)
                    if not re.search(rf"(?:async\s+)?function\s+{re.escape(function_name)}\s*\(", javascript):
                        raise RuntimeError(f"onclick target {function_name} is absent for {page} button {index}")
                    binding = f"onclick:{function_name}"
                else:
                    fragment = LISTENER_BINDINGS.get((page, button_id))
                    if not fragment:
                        raise RuntimeError(f"unbound static button in {page}: id={button_id or '<none>'}")
                    require(javascript, fragment, f"listener for {page}#{button_id}")
                    binding = "listener"
                static_buttons.append({"page": page, "id": button_id or f"button-{index}", "binding": binding})

        all_javascript = {
            page: "\n".join(read_member(archive, f"app/web-new/{script}") for script in scripts)
            for page, scripts in PAGES.items()
        }
        server_js = all_javascript["servers.html"]
        for action in ("up", "down", "check", "activate", "delete"):
            require(server_js, f'data-a="{action}"', f"dynamic server button {action}")
        require(server_js, "actions.addEventListener('click'", "dynamic server action listener")
        require(server_js, "{ check: 'check.cgi', activate: 'activate.cgi', delete: 'delete.cgi' }[action]", "server endpoint map")

        subscription_js = all_javascript["subscriptions.html"]
        for action in ("refresh", "delete"):
            require(subscription_js, f'data-a="{action}"', f"dynamic subscription button {action}")
        require(subscription_js, "actions.addEventListener('click'", "dynamic subscription action listener")
        require(subscription_js, "panel.querySelector('[data-auto-save]').addEventListener('click'", "subscription auto-update save listener")
        require(subscription_js, "data-auto-save", "subscription auto-update save button")

        login_js = all_javascript["index.html"]
        require(login_js, 'method: "POST"', "login POST method")
        home_js = all_javascript["home.html"]
        for action in ("create", "repair"):
            require(home_js, "'api/keenetic/' + action + '.cgi'", f"Keenetic {action} endpoint dispatcher")
        require(home_js, "JSON.stringify({ mode })", "Xray install/reinstall mode body")
        require(home_js, "method: 'POST'", "state-changing Home POST methods")

        for page, endpoints in ENDPOINTS.items():
            page_js = all_javascript[page]
            for endpoint in endpoints:
                archive_name = f"app/web-new/{endpoint}"
                member = members.get(archive_name)
                if member is None or not member.isfile() or member.mode & 0o111 == 0:
                    raise RuntimeError(f"missing executable endpoint for {page}: {endpoint}")
                if endpoint.startswith("api/keenetic/"):
                    referenced = "'api/keenetic/' + action + '.cgi'" in page_js
                elif endpoint.startswith("api/servers/") and endpoint.rsplit("/", 1)[-1] in {"check.cgi", "activate.cgi", "delete.cgi"}:
                    referenced = "'api/servers/' + endpoint" in page_js
                elif endpoint.startswith("api/subscriptions/") and endpoint.rsplit("/", 1)[-1] in {"refresh.cgi", "delete.cgi"}:
                    referenced = "'api/subscriptions/' + endpoint" in page_js
                else:
                    referenced = endpoint in page_js or ("/" + endpoint) in page_js
                if not referenced:
                    raise RuntimeError(f"endpoint is not referenced by {page}: {endpoint}")
                endpoint_results.append({"page": page, "endpoint": endpoint, "executable": True})

    result = {
        "schemaVersion": 1,
        "status": "PASS",
        "appArchive": str(args.app_archive),
        "staticButtons": {"count": len(static_buttons), "bindings": static_buttons},
        "dynamicButtons": {
            "count": 8,
            "serverActions": ["up", "down", "check", "activate", "delete"],
            "subscriptionActions": ["refresh", "delete", "auto-update-save"],
        },
        "endpoints": {"count": len(endpoint_results), "bindings": endpoint_results},
        "totalButtonActions": len(static_buttons) + 8,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
