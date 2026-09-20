# Scale builder integration

The DeepSeek Flash builder produced the scale benchmark and its behavioral
tests, but its session ended without a final Markdown report. The coordinator
completed integration, addressed the independent scale review, and ran the
1,000 / 10,000 / 25,000-document measurements plus a separate allocation run.

See [the integrated results](README.md) for final numbers and limitations.
The benchmark reports separate prebuilt-index and application paths, explicit
sample counts, percentile adequacy, process RSS semantics, full storage
footprint, allowlist sweeps, and batch update costs. Tests assert behavior and
measurement accounting rather than machine-specific latency thresholds.
