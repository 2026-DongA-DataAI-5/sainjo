"""Render the Flask prototype into a static GitHub Pages project site."""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs"
BASE_PATH = os.environ.get("PAGES_BASE_PATH", "/sainjo").rstrip("/")
ROUTES = (
    "/",
    "/start",
    "/dashboard",
    "/vehicle",
    "/history/new",
    "/maintenance/new",
    "/items/engine-oil",
    "/items/air-filter",
    "/items/coolant",
    "/questions",
    "/timeline",
)
LOCAL_URL = re.compile(r"(?P<prefix>\b(?:href|src|action)\s*=\s*)(?P<quote>[\"'])/(?P<path>[^\"']*)")


def rewrite_local_urls(html: str) -> str:
    html = html.replace('data-base-path=""', f'data-base-path="{BASE_PATH}"')

    def replace(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}{match.group('quote')}{BASE_PATH}/{match.group('path')}"

    return LOCAL_URL.sub(replace, html)


def page_path(route: str) -> Path:
    if route == "/":
        return OUTPUT / "index.html"
    return OUTPUT / route.strip("/") / "index.html"


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from chageun import create_app

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    client = create_app().test_client()
    for route in ROUTES:
        response = client.get(route)
        if response.status_code != 200:
            raise RuntimeError(f"{route} returned HTTP {response.status_code}")
        destination = page_path(route)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rewrite_local_urls(response.get_data(as_text=True)), encoding="utf-8")

    not_found = client.get("/__pages_not_found__")
    if not_found.status_code != 404:
        raise RuntimeError("The not-found page did not return HTTP 404")
    (OUTPUT / "404.html").write_text(rewrite_local_urls(not_found.get_data(as_text=True)), encoding="utf-8")
    shutil.copytree(ROOT / "chageun" / "static", OUTPUT / "static")
    (OUTPUT / ".nojekyll").write_text("", encoding="utf-8")

    generated_pages = list(OUTPUT.rglob("index.html"))
    if len(generated_pages) != len(ROUTES):
        raise RuntimeError(f"Expected {len(ROUTES)} pages, generated {len(generated_pages)}")
    print(f"Built {len(generated_pages)} static pages under {OUTPUT}")
    print(f"GitHub Pages base path: {BASE_PATH}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
