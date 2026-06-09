import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_ENDPOINT_KEYS = {
    "purchase_orders",
    "goods_receipts",
    "branch_transfers",
    "suppliers",
    "stock_valuation",
    "inventory_aging",
    "slow_dead_stock",
}


def _load_fixture(path):
    with path.open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def _validate_fixture(fixture):
    endpoints = fixture.get("endpoints")
    if not isinstance(endpoints, list):
        raise AssertionError("Fixture must contain an endpoints list")

    seen = set()
    results = []
    failures = []

    for endpoint in endpoints:
        key = endpoint.get("endpoint_key")
        sample_ms = endpoint.get("sample_ms")
        threshold_ms = endpoint.get("threshold_ms")

        if key not in REQUIRED_ENDPOINT_KEYS:
            failures.append(f"unknown endpoint key: {key!r}")
            continue
        if key in seen:
            failures.append(f"duplicate endpoint key: {key}")
            continue
        seen.add(key)

        if not isinstance(sample_ms, (int, float)) or sample_ms < 0:
            failures.append(f"{key}: sample_ms must be a non-negative number")
            continue
        if not isinstance(threshold_ms, (int, float)) or threshold_ms <= 0:
            failures.append(f"{key}: threshold_ms must be a positive number")
            continue

        promoted = sample_ms <= threshold_ms
        if not promoted:
            failures.append(f"{key}: sample_ms {sample_ms} exceeds threshold_ms {threshold_ms}")

        results.append(
            {
                "endpoint_key": key,
                "sample_ms": sample_ms,
                "threshold_ms": threshold_ms,
                "promoted": promoted,
            }
        )

    missing = sorted(REQUIRED_ENDPOINT_KEYS - seen)
    if missing:
        failures.append(f"missing endpoint keys: {missing}")

    return results, failures


def main():
    parser = argparse.ArgumentParser(description="Validate export benchmark promotion fixture.")
    parser.add_argument(
        "--fixture",
        default="docs/benchmarks/export-benchmark-fixture.json",
        help="Path to the pinned export benchmark fixture.",
    )
    parser.add_argument(
        "--output",
        default="benchmark-results/export-benchmark-results.json",
        help="Path where the benchmark artifact should be written.",
    )
    args = parser.parse_args()

    fixture_path = Path(args.fixture)
    output_path = Path(args.output)
    fixture = _load_fixture(fixture_path)
    results, failures = _validate_fixture(fixture)

    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture": str(fixture_path),
        "promotion_logic": fixture.get("promotion_logic"),
        "results": results,
        "passed": not failures,
        "failures": failures,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    if failures:
        print("Export benchmark promotion failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        sys.exit(1)

    print(f"Export benchmark promotion passed for {len(results)} endpoints.")
    print(f"Artifact written to {output_path}.")


if __name__ == "__main__":
    main()
