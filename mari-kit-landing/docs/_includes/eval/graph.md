:::{admonition} Benchmark first
:class: benchmark
**Corpora:** [DocRED](https://github.com/thunlp/DocRED) · [WDC Products](https://webdatacommons.org/largescaleproductcorpus/wdc-products/) · [KILT](https://github.com/facebookresearch/KILT) · [QASC](https://github.com/allenai/qasc)

**Protocol:** Measure blocking pairs completeness and reduction ratio, entity pair/cluster F1, relation micro-F1, provenance precision/recall, and multi-hop answer accuracy. Then run graph-off and graph-on retrieval with identical seeds to attribute recall gains. Every projected passage must retain its source node and path.
:::
