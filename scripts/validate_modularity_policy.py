import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "MODULARITY.md"
CI = ROOT / ".github" / "workflows" / "ci.yml"

REQUIRED_RUNNER_KEYS = {
    "backend_lint",
    "backend_migrations",
    "backend_tests",
    "backend_architecture_tests",
    "frontend_lint",
    "frontend_build",
    "modularity_policy",
    "export_benchmark",
}

REQUIRED_ENDPOINT_KEYS = {
    "purchase_orders",
    "goods_receipts",
    "branch_transfers",
    "suppliers",
    "stock_valuation",
    "inventory_aging",
    "slow_dead_stock",
}


def _load_policy_json():
    text = POLICY.read_text(encoding="utf-8")
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        raise ValueError("MODULARITY.md must contain a JSON policy block")
    return json.loads(match.group(1))


def main():
    policy = _load_policy_json()
    runner_lock = policy.get("runner_lock", {})
    endpoints = set(policy.get("export_endpoint_keys", []))

    runner_keys = set(runner_lock)
    if runner_keys != REQUIRED_RUNNER_KEYS:
        missing = sorted(REQUIRED_RUNNER_KEYS - runner_keys)
        extra = sorted(runner_keys - REQUIRED_RUNNER_KEYS)
        raise AssertionError(f"Runner lock keys drifted. missing={missing} extra={extra}")

    if endpoints != REQUIRED_ENDPOINT_KEYS:
        missing = sorted(REQUIRED_ENDPOINT_KEYS - endpoints)
        extra = sorted(endpoints - REQUIRED_ENDPOINT_KEYS)
        raise AssertionError(f"Export endpoint keys drifted. missing={missing} extra={extra}")

    ci_text = CI.read_text(encoding="utf-8")
    missing_commands = [
        command
        for command in runner_lock.values()
        if command != runner_lock["modularity_policy"] and command not in ci_text
    ]
    if missing_commands:
        raise AssertionError(f"Runner-locked commands missing from CI: {missing_commands}")

    if runner_lock["modularity_policy"] not in ci_text:
        raise AssertionError("Modularity policy validator command is not wired into CI")

    print("MODULARITY.md runner lock and endpoint keys match CI policy.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Policy validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
