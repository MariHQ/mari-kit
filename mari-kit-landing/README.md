# Mari Kit documentation landing page

The documentation published at <https://kit.mari.guru> is authored as one
MyST Markdown page and built with Sphinx and the Read the Docs theme. The left
navigation exposes major knowledge-system categories, then the sections within
the active category.

The page distinguishes importable, current APIs from proposed interfaces.
Research-derived features place their papers beside the relevant mechanics and
code instead of collecting them in a separate catalog.

## Build

```sh
python -m pip install -r mari-kit-landing/requirements.txt
make -C mari-kit-landing html
```

Open `mari-kit-landing/_build/html/index.html`, or serve the build directory:

```sh
python -m http.server 8000 --directory mari-kit-landing/_build/html
```

The Markdown source of truth is `docs/index.md`. Do not edit generated HTML or
the deployed S3 objects independently.
