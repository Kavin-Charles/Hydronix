#!/usr/bin/env bash
# =====================================================================
# HydroHackathon - one-shot setup (Linux / macOS / Git Bash)
# Creates .venv, installs all deps, regenerates sample hulls.
# =====================================================================
set -e
cd "$(dirname "$0")/.."

echo
echo "[1/4] Python version check"
python3 --version || { echo "Python not on PATH. Install 3.11 or 3.12."; exit 1; }

echo
echo "[2/4] Create virtual environment at .venv"
if [ ! -d .venv ]; then
    python3 -m venv .venv
else
    echo "    .venv already exists - skipping"
fi

echo
echo "[3/4] Install dependencies"
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo
echo "[4/4] Generate sample offset files"
python samples/generate_samples.py
python samples/build_kcs.py

cat <<EOF

 ======================================================
  Setup complete. Activate with:
      source .venv/bin/activate
  Then run:
      ./scripts/run_tests.sh      (validation suite)
      ./scripts/run_demo.sh       (CLI demo)
      ./scripts/run_streamlit.sh  (web UI)
 ======================================================
EOF
