#!/usr/bin/env bash
# Full pipeline: setup -> tests -> CLI demo -> capsize demo.
set -e
cd "$(dirname "$0")/.."
bash scripts/setup.sh
bash scripts/run_tests.sh
bash scripts/run_demo.sh
bash scripts/run_capsize.sh
cat <<EOF

 ===========================================================
  Full pipeline complete. Launch UI with:
      ./scripts/run_streamlit.sh
 ===========================================================
EOF
