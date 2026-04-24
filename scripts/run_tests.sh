#!/usr/bin/env bash
# Validation suite: analytical benchmarks + KCS regression.
set -e
cd "$(dirname "$0")/.."
[ -f .venv/bin/activate ] && source .venv/bin/activate

echo
echo "=== pytest ==="
python -m pytest tests/ -v

echo
echo "=== benchmark script (verbose numbers) ==="
python tests/test_benchmarks.py
