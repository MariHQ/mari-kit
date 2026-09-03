#!/usr/bin/env python3
"""Run the documented API conformance evaluation and retain every case result."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks/results"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mari-conformance-") as directory:
        junit = Path(directory) / "junit.xml"
        started = time.perf_counter()
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", f"--junitxml={junit}"],
            check=False,
        )
        wall_seconds = time.perf_counter() - started
        root = ET.parse(junit).getroot()
        suite = root.find("testsuite") if root.tag == "testsuites" else root
        if suite is None:
            raise RuntimeError("pytest did not emit a test suite")
        cases = []
        for case in suite.iter("testcase"):
            outcome = "passed"
            for candidate in ("failure", "error", "skipped"):
                if case.find(candidate) is not None:
                    outcome = candidate
                    break
            cases.append(
                {
                    "id": f"{case.get('classname')}::{case.get('name')}",
                    "outcome": outcome,
                    "duration_seconds": float(case.get("time", "0")),
                }
            )
    report = {
        "schema_version": 1,
        "evaluation": "documented-api-conformance",
        "created_at": datetime.now(UTC).isoformat(),
        "mari_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "tests": len(cases),
        "passed": sum(case["outcome"] == "passed" for case in cases),
        "failed": sum(case["outcome"] in {"failure", "error"} for case in cases),
        "skipped": sum(case["outcome"] == "skipped" for case in cases),
        "wall_seconds": wall_seconds,
    }
    (args.output_dir / "documented-api-conformance.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    with (args.output_dir / "documented-api-conformance.cases.jsonl").open(
        "w"
    ) as stream:
        for case in cases:
            stream.write(json.dumps(case, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
