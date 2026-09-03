import os
import sys

sys.path.insert(0, os.path.abspath("../.."))

project = "Mari Kit"
author = "Mari"
copyright = "2026, Mari"

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

html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "canonical_url": "https://kit.mari.guru",
    "collapse_navigation": True,
    "navigation_depth": 3,
}
html_title = "Mari Kit documentation"
html_static_path = ["_static"]
html_css_files = ["css/custom.css"]
html_show_sourcelink = False
html_context = {
    "display_github": True,
    "github_user": "MariHQ",
    "github_repo": "mari-kit",
    "github_version": "main/",
    "conf_py_path": "/mari-kit-landing/docs/",
}

myst_enable_extensions = ["colon_fence", "attrs_inline"]
myst_heading_anchors = 3
