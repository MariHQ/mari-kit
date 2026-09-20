"""Run every company-brain fixture and emit its observable results as JSON."""

import json
from importlib import import_module

SCENARIOS = (
    "search",
    "support",
    "onboarding",
    "incident",
    "decisions",
    "conversation",
    "sync",
    "isolation",
)


def run() -> dict[str, object]:
    return {
        name: import_module(f"examples.company_brains.{name}").run()
        for name in SCENARIOS
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
