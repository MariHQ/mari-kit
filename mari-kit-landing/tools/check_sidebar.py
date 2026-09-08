"""Exercise built documentation navigation in Chromium, on desktop and mobile.

Usage: python mari-kit-landing/tools/check_sidebar.py --site-dir path/to/html
Install playwright and its Chromium browser first. --browser-path can select an
existing Chrome executable. The test serves only the supplied build on localhost.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def check(base_url: str, browser_path: str | None) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=browser_path)
        for mobile in (False, True):
            context = browser.new_context(
                viewport={"width": 390, "height": 844}
                if mobile
                else {"width": 1440, "height": 900},
                color_scheme="dark" if mobile else "light",
            )
            # Exercise the shell without external network dependencies.
            context.route(
                "https://fonts.googleapis.com/**", lambda route: route.abort()
            )
            context.route("https://fonts.gstatic.com/**", lambda route: route.abort())
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))

            def loaded(page=page):
                page.wait_for_load_state("load")
                page.evaluate("() => document.fonts.ready")
                page.evaluate(
                    "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
                )

            def open_menu(page=page, mobile=mobile):
                if mobile and not page.locator("#__navigation").is_checked():
                    page.locator("label.mk-menu").click()
                    assert page.locator("#__navigation").is_checked()

            def position(page=page):
                return page.locator(".sidebar-scroll").evaluate("el => el.scrollTop")

            page.goto(base_url)
            loaded()
            open_menu()
            link = page.locator(
                ".sidebar-tree a[href='agents/conversation-knowledge.html']"
            )
            link.scroll_into_view_if_needed()
            before = position()
            assert before > 500
            link.click()
            loaded()
            open_menu()
            assert abs(position() - before) <= 2, (mobile, before, position())
            assert page.evaluate("window.scrollY") == 0
            page.reload()
            loaded()
            open_menu()
            assert abs(position() - before) <= 2
            page.go_back()
            loaded()
            open_menu()
            assert abs(position() - before) <= 2
            page.go_forward()
            loaded()
            open_menu()
            assert abs(position() - before) <= 2

            heading = page.locator(".sidebar-tree .toctree-l1 > a.reference").last
            style = heading.evaluate(
                "el => { const s = getComputedStyle(el); return { opacity: s.opacity, size: parseFloat(s.fontSize), border: s.borderLeftWidth, color: s.color, background: s.backgroundColor }; }"
            )
            assert style["opacity"] == "1" and style["size"] >= 12
            assert style["border"] == "3px"

            def luminance(rgb):
                values = [float(x.strip()) / 255 for x in rgb[4:-1].split(",")]
                return sum(
                    weight
                    * (v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
                    for weight, v in zip((0.2126, 0.7152, 0.0722), values, strict=True)
                )

            low, high = sorted(
                (luminance(style["color"]), luminance(style["background"]))
            )
            assert (high + 0.05) / (low + 0.05) >= 4.5
            assert not errors, errors
            context.close()

        # No previous tab position: reveal the active entry on a deep link.
        for storage in ("empty", "corrupt", "denied"):
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            context.route(
                "https://fonts.googleapis.com/**", lambda route: route.abort()
            )
            if storage == "corrupt":
                context.add_init_script(
                    "sessionStorage.setItem('mari-kit:sidebar:v1:/', '{broken');"
                )
            elif storage == "denied":
                context.add_init_script(
                    "Object.defineProperty(window, 'sessionStorage', {get() {throw new Error('denied');}});"
                )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
            page.goto(base_url + "platform/stores.html")
            page.wait_for_load_state("load")
            visible = page.locator(
                ".sidebar-tree .current-page > a.reference"
            ).evaluate(
                "el => { const item = el.getBoundingClientRect(); const menu = document.querySelector('.sidebar-scroll').getBoundingClientRect(); return item.top >= menu.top && item.bottom <= menu.bottom; }"
            )
            assert visible and not errors, (storage, errors)
            assert page.evaluate("window.scrollY") == 0
            context.close()
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", required=True, type=Path)
    parser.add_argument("--browser-path")
    args = parser.parse_args()
    if not (args.site_dir / "index.html").is_file():
        parser.error("site-dir must contain a built index.html")
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(QuietHandler, directory=str(args.site_dir.resolve())),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        check(f"http://127.0.0.1:{server.server_port}/", args.browser_path)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    print(
        "Sidebar checks passed: click, reload, history, mobile, contrast, deep links, and storage fallback."
    )


if __name__ == "__main__":
    main()
