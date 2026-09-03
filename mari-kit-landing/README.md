# Mari Kit documentation landing page

The documentation published at <https://kit.mari.guru> is authored as MyST
Markdown and built with Sphinx and the Read the Docs theme. Each feature has its
own Markdown document, grouped beneath expandable knowledge-system categories
in the left navigation.

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

The Markdown files under `docs/` are the source of truth. Do not edit generated
HTML or the deployed S3 objects independently.
