import os
import sys

sys.path.insert(0, os.path.abspath("../.."))

project = "Mari Kit"
author = "Mari Kit contributors"
copyright = "Mari Kit contributors"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_inline_tabs",
    "sphinx_toolbox.collapse",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "_includes/**"]

# ---------------------------------------------------------------------------
# Theme: furo, restyled into the Mari Blueprint docs shell (mari.guru/docs).
# Palette and type live in _static/css/custom.css as --mk-* tokens; the furo
# variables below map furo's own components onto the same palette so nothing
# falls back to furo's default blue or dark grey.
# ---------------------------------------------------------------------------

_light = {
    "bg": "#ffffff",
    "card": "#f7f8fa",
    "flysch": "#f0f2f5",
    "ink": "#10263b",
    "line": "#d4d5d8",
    "accent": "#1e6fa8",
    "biscay": "#1c3f60",
    "espelette": "#b23a1e",
    "moss": "#2c6e49",
    "clay": "#a05e1c",
    "muted": "#5d6b79",
    "faint": "#71808f",
    "down": "#e8f1f9",
}
_dark = {
    "bg": "#0e2032",
    "card": "#0a1926",
    "flysch": "#12293d",
    "ink": "#eaf0f5",
    "line": "#2d4356",
    "accent": "#1e6fa8",
    "link": "#6fb1e6",
    "biscay": "#6fb1e6",
    "espelette": "#e8805e",
    "moss": "#5fb98a",
    "clay": "#d6944f",
    "muted": "#b9c6d2",
    "faint": "#8497a6",
    "down": "#14324c",
}

# Code blocks keep the docs shell's warm dark block in both modes.
_code_bg = "#26231c"
_code_fg = "#f3ecd9"


def _furo_vars(p: dict, *, dark: bool) -> dict:
    link = p.get("link", p["accent"])
    ink_rgb = "234,240,245" if dark else "16,38,59"
    return {
        "font-stack": "Inter, ui-sans-serif, system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif",
        "font-stack--headings": "Inter, ui-sans-serif, system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif",
        "font-stack--monospace": "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        # foreground / background
        "color-foreground-primary": p["ink"],
        "color-foreground-secondary": p["muted"],
        "color-foreground-muted": p["faint"],
        "color-foreground-border": p["line"],
        "color-background-primary": p["bg"],
        "color-background-secondary": p["card"],
        "color-background-hover": p["flysch"],
        "color-background-hover--transparent": p["flysch"] + "00",
        "color-background-border": p["line"],
        "color-background-item": p["line"],
        # brand / links
        "color-brand-primary": link,
        "color-brand-content": link,
        "color-brand-visited": link,
        "color-link": link,
        "color-link--hover": p["biscay"],
        "color-link--visited": link,
        "color-link--visited--hover": p["biscay"],
        "color-link-underline": f"rgba({ink_rgb}, 0.25)",
        "color-link-underline--hover": p["biscay"],
        "color-link-underline--visited": f"rgba({ink_rgb}, 0.25)",
        "color-link-underline--visited--hover": p["biscay"],
        # header (furo mobile header) and announcement wrapper reused as our header
        "color-header-background": p["card"],
        "color-header-border": p["line"],
        "color-header-text": p["ink"],
        "color-announcement-background": p["card"],
        "color-announcement-text": p["ink"],
        # sidebar
        "color-sidebar-background": p["card"],
        "color-sidebar-background-border": p["line"],
        "color-sidebar-brand-text": p["ink"],
        "color-sidebar-caption-text": p["ink"],
        "color-sidebar-link-text": p["ink"],
        "color-sidebar-link-text--top-level": p["ink"],
        "color-sidebar-item-background": p["card"],
        "color-sidebar-item-background--current": "transparent",
        "color-sidebar-item-background--hover": "transparent",
        "color-sidebar-item-expander-background": "transparent",
        "color-sidebar-item-expander-background--hover": "transparent",
        "color-sidebar-search-text": p["ink"],
        "color-sidebar-search-background": p["bg"],
        "color-sidebar-search-background--focus": p["bg"],
        "color-sidebar-search-border": p["line"],
        "color-sidebar-search-icon": p["faint"],
        # right-hand table of contents
        "color-toc-background": p["bg"],
        "color-toc-title-text": p["ink"],
        "color-toc-item-text": p["muted"],
        "color-toc-item-text--hover": p["ink"],
        "color-toc-item-text--active": link,
        # content
        "color-content-foreground": p["ink"],
        "color-content-background": "transparent",
        "color-inline-code-background": f"rgba({ink_rgb}, 0.08)",
        "color-code-background": _code_bg,
        "color-code-foreground": _code_fg,
        "color-highlight-on-target": p["down"],
        "color-highlighted-background": p["down"],
        "color-highlighted-text": p["ink"],
        "color-table-border": p["line"],
        "color-table-header-background": f"rgba({ink_rgb}, 0.04)",
        "color-card-border": p["line"],
        "color-card-background": p["card"],
        "color-card-marginals-background": p["card"],
        "color-guilabel-background": p["down"],
        "color-guilabel-border": p["line"],
        "color-guilabel-text": p["ink"],
        "color-problematic": p["espelette"],
        # admonitions: note/seealso accent, tip/hint moss, warning/caution clay,
        # danger/error/attention espelette, important biscay
        "color-admonition-background": p["card"],
        "color-admonition-title": p["ink"],
        "color-admonition-title-background": f"rgba({ink_rgb}, 0.06)",
        "color-admonition-title--note": p["accent"],
        "color-admonition-title-background--note": f"{p['accent']}1f",
        "color-admonition-title--seealso": p["accent"],
        "color-admonition-title-background--seealso": f"{p['accent']}1f",
        "color-admonition-title--tip": p["moss"],
        "color-admonition-title-background--tip": f"{p['moss']}1f",
        "color-admonition-title--hint": p["moss"],
        "color-admonition-title-background--hint": f"{p['moss']}1f",
        "color-admonition-title--warning": p["clay"],
        "color-admonition-title-background--warning": f"{p['clay']}1f",
        "color-admonition-title--caution": p["clay"],
        "color-admonition-title-background--caution": f"{p['clay']}1f",
        "color-admonition-title--danger": p["espelette"],
        "color-admonition-title-background--danger": f"{p['espelette']}1f",
        "color-admonition-title--error": p["espelette"],
        "color-admonition-title-background--error": f"{p['espelette']}1f",
        "color-admonition-title--attention": p["espelette"],
        "color-admonition-title-background--attention": f"{p['espelette']}1f",
        "color-admonition-title--important": p["biscay"],
        "color-admonition-title-background--important": f"{p['biscay']}1f",
        # api docs (autodoc), kept on-palette
        "color-api-name": p["ink"],
        "color-api-pre-name": p["muted"],
        "color-api-keyword": p["ink"],
        "color-api-overall": p["muted"],
        "color-api-paren": p["muted"],
        "color-api-background": "transparent",
        "color-api-background-hover": p["flysch"],
    }


html_theme = "furo"
html_title = "Mari Kit"
html_baseurl = "https://kit.mari.guru/"
html_favicon = "_static/favicon.svg"
html_static_path = ["_static"]
html_css_files = ["css/custom.css", "css/diagrams.css"]
html_show_sourcelink = False
html_show_copyright = False
html_show_sphinx = False
html_theme_options = {
    "sidebar_hide_name": True,
    "light_css_variables": _furo_vars(_light, dark=False),
    "dark_css_variables": _furo_vars(_dark, dark=True),
    "top_of_page_buttons": [],
    "source_repository": "https://github.com/MariHQ/mari-kit/",
    "source_branch": "main",
    "source_directory": "mari-kit-landing/docs/",
    # A non-empty announcement makes furo render its announcement block, which
    # _templates/page.html overrides to draw the Mari docs top header. The
    # value itself is never printed.
    "announcement": "mari-kit-header",
}

# Code blocks are dark in both modes (the docs shell's #26231c block), so use
# one dark Pygments style for both.
pygments_style = "monokai"
pygments_dark_style = "monokai"

# Fonts: the docs shell loads Inter and JetBrains Mono from Google Fonts.
_fonts_href = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
    "&family=JetBrains+Mono:wght@400;500;600&display=swap"
)

# Brand mark shared with mari.guru/docs. Read from _static so the template
# inlines the same file the header, sidebar, and favicon are built from.
with open(os.path.join(os.path.dirname(__file__), "_static", "mari-mark.svg"), encoding="utf-8") as _f:
    _mari_mark_svg = _f.read().strip()

html_context = {
    "mari_mark_svg": _mari_mark_svg,
    "mari_fonts_href": _fonts_href,
    "mari_github_url": "https://github.com/MariHQ/mari-kit",
    "mari_license_url": "https://github.com/MariHQ/mari-kit/blob/main/LICENSE.md",
    "mari_site_url": "https://mari.guru",
}

myst_enable_extensions = ["colon_fence", "attrs_inline"]
myst_heading_anchors = 3
