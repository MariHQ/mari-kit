# Mari Kit documentation landing page

The documentation published at <https://kit.mari.guru> is authored as MyST
Markdown and built with Sphinx and the Furo theme, styled with Mari tokens.
Each feature has its own Markdown document, grouped beneath visible categories
in the left navigation.

The page distinguishes importable, current APIs from proposed interfaces.
Research-derived features place their papers beside the relevant mechanics and
code instead of collecting them in a separate catalog.

## Build

```sh
python -m pip install -r mari-kit-landing/requirements.txt
make -C mari-kit-landing html
```

From the repository's virtual environment, the equivalent strict build is:

```sh
.venv/bin/sphinx-build -W --keep-going -b html mari-kit-landing/docs mari-kit-landing/_build/html
```

Warnings fail the build, including unresolved local links and invalid includes.
Repository tests also check page navigation, Python imports, and the shared-atom
architecture example.

## Navigation and inventory checks

The sidebar saves its scroll position per browser tab using session storage.
It restores a visible link and its offset across clicks, reloads, and history
navigation. A fresh deep link reveals the active item without scrolling the
article. Storage denial falls back to normal navigation. Section labels use
full-contrast text, a tinted background, and an accent border in both themes.

Run the browser regression checks against a strict build:

```sh
python -m pip install playwright
python -m playwright install chromium
python mari-kit-landing/tools/check_sidebar.py --site-dir mari-kit-landing/_build/html
```

The checks cover desktop/light, mobile/dark, click/reload/history restoration,
fresh deep links, section contrast, and unavailable or malformed storage.
Use `--browser-path` to test with an existing Chrome executable.

The complete API inventory is generated from source definitions rather than
maintained as a handwritten count:

```sh
python mari-kit-landing/tools/generate_algorithm_inventory.py
python mari-kit-landing/tools/generate_algorithm_inventory.py --check
```

Regenerate after committing source changes so the inventory's pinned source
links identify the matching revision. CI checks inventory freshness with full
Git history, builds the site, and runs the sidebar browser checks.

Open `mari-kit-landing/_build/html/index.html`, or serve the build directory:

```sh
python -m http.server 8000 --directory mari-kit-landing/_build/html
```

The Markdown files under `docs/` are the source of truth. Do not edit generated
HTML or the deployed S3 objects independently.

## Edit and publish

Add feature pages to their section's `index.md` toctree and its visible overview.
The sidebar shows two levels of page titles across all sections. Put important
starting paths on the homepage as well. Conversation knowledge and dependency
updates include their guides from the repository-level `docs/` directory, so
edit those guides rather than duplicating their text.

A Git push updates the repository. It does not itself publish the website:
the current GitHub Actions workflow validates the project and has no docs
deployment job. Publishing requires the authorized site operator to upload the
complete strict-build output and invalidate the site's CDN cache.

After publication, fetch the homepage, each new deep link, and a section index.
Check the HTML title, canonical URL, page heading, and sidebar entry. A successful
HTTP status is insufficient: the host may return the homepage for an unavailable
deep link. Verify an expected heading and content unique to the new page.

Keep archived research proposals separate from current API instructions. Mark
host callbacks in examples, describe reference implementation limits, and link
shared identity and dependency concepts instead of inventing local equivalents.
