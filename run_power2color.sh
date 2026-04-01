#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python"

if [[ ! -x "${VENV_PYTHON}" ]]; then
	echo "Virtual environment not found at ${VENV_PYTHON}" >&2
	echo "Run ./install_on_pi.sh first." >&2
	exit 1
fi

cd "${SCRIPT_DIR}"
exec "${VENV_PYTHON}" power2color.py "$@"

