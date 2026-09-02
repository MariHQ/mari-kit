# Mari Kit documentation landing page

This directory contains the static single-page documentation published at
<https://kit.mari.guru>.

The page distinguishes importable, current APIs from proposed interfaces.
Research-derived features place their papers beside the relevant mechanics and
code instead of collecting them in a separate catalog.

## Preview

```sh
python3 -m http.server 8000 --directory mari-kit-landing
```

Open <http://localhost:8000>.

## Deploy

Deployment requires an authenticated AWS CLI profile with access to the site
bucket and CloudFront distribution. Upload all three assets, preserve their
content types, set explicit cache policy, and invalidate the distribution only
after every upload succeeds.

The deployed source of truth is this directory. Do not edit the S3 objects
independently.
