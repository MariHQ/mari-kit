[]{#install}

# Install

## Supported environment

| Requirement | Value |
|---|---|
| Python | 3.11–3.13 |
| Required dependency | NumPy |
| Model, database, and HTTP SDKs | Injected by the application or installed as optional extras |




Python 3.11--3.13 is supported. The runtime dependency list contains NumPy.

```{code-block} console
:caption: terminal

pip install 'mari-components @ git+https://github.com/MariHQ/mari-kit.git'

# Install a runtime adapter when the application uses one
pip install 'mari-components[openai-agents] @ git+https://github.com/MariHQ/mari-kit.git'
pip install 'mari-components[langchain] @ git+https://github.com/MariHQ/mari-kit.git'
```

## How it works

The base wheel contains Mari's domain types and connector contracts. It also
installs the sync, retrieval, knowledge, trajectory, and verification modules.
Model SDKs and database clients arrive through optional extras or the host
application. The host passes model calls, HTTP transport, persistence, clocks,
and authorization decisions into Mari functions. These details describe the
package boundary.
