[]{#install}

# Install

## Supported environment

| Requirement | Value |
|---|---|
| Python | 3.11–3.13 |
| Required dependency | NumPy |
| Model, database, and HTTP SDKs | Injected by the application or installed as optional extras |




```{code-block} console
:caption: terminal

python -m pip install 'mari-components @ git+https://github.com/MariHQ/mari-kit.git'

# Install a runtime adapter when the application uses one
python -m pip install 'mari-components[openai-agents] @ git+https://github.com/MariHQ/mari-kit.git'
python -m pip install 'mari-components[langchain] @ git+https://github.com/MariHQ/mari-kit.git'
```

## Run the examples

The examples live in the repository. Clone it and install the local package
before running the outcome guides:

```{code-block} console
git clone https://github.com/MariHQ/mari-kit.git
cd mari-kit
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
source .venv/bin/activate
python -m pip install -e .
python -m examples.quickstarts.company_search
python -m examples.quickstarts.dependency_updates
python -m examples.conversation_knowledge_demo
```

These examples use deterministic fixtures and run credential-free. Pin a Git
commit in production installations by appending `@<commit>` to the repository
URL. The package is a pre-release preview with
[documented maturity labels](maturity.md).

## Package boundaries

The base wheel contains Mari's domain types and connector contracts. It also
installs the sync, retrieval, knowledge, trajectory, and verification modules.
Model SDKs and database clients arrive through optional extras or the host
application. The host passes model calls, HTTP transport, persistence, clocks,
and authorization decisions into Mari functions. These details describe the
package boundary.
