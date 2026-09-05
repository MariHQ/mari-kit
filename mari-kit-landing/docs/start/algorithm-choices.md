# Algorithm choices

## Run independent algorithms

Use fixture callbacks to compare algorithm choices. Install the optional solver
extra to include native graph and centroid-linkage operations.

```{code-block} console
python -m examples.algorithm_choices_demo
pip install 'mari-components[algorithm-solvers]'
python -m examples.algorithm_choices_demo --solvers
```

```{include} ../../../docs/algorithm-choices.md
:start-line: 2
```
