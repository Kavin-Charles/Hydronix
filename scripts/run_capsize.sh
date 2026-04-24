#!/usr/bin/env bash
# Headless capsize-simulator demo on KCS (rogue wave strike).
set -e
cd "$(dirname "$0")/.."
[ -f .venv/bin/activate ] && source .venv/bin/activate
python scripts/capsize_demo.py
