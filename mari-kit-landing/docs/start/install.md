[]{#install}

# Install

## Evaluation

The distribution is installed into the test environment and all public modules are exercised by the repository suite. Five architecture checks also prevent undeclared application/runtime responsibilities from entering the package.

```console
$ pytest -q
196 passed
```


Python 3.11--3.13 is supported. NumPy is the only runtime dependency.

```{code-block} console
:caption: terminal

pip install mari-components

# Optional runtime adapters
pip install 'mari-components[openai-agents]'
pip install 'mari-components[langchain]'
```

## How it works

The base wheel installs the domain, connector, synchronization, retrieval, knowledge, trajectory, and verification modules without a model SDK or database client. Extras add adapter imports only; applications still inject model calls, HTTP transport, persistence, clocks, and authorization decisions. This is package behavior, not a research-derived algorithm.
