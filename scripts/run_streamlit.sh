#!/usr/bin/env bash
# Launch Streamlit web UI.
set -e
cd "$(dirname "$0")/.."
[ -f .venv/bin/activate ] && source .venv/bin/activate
echo
echo "Opening Streamlit UI at http://localhost:8501 ..."
streamlit run app.py "$@"
