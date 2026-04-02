#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${SCRIPT_DIR}"
REPO_URL="https://github.com/AndreasSchaudt2/Power2Color.git"
REPO_BRANCH="v3-refactor"
TARGET_DIR="${HOME}/Power2Color"
VENV_DIR=""
SERVICE_NAME="power2color.service"
SERVICE_TEMPLATE=""
SERVICE_TARGET="/etc/systemd/system/${SERVICE_NAME}"
RUN_SCRIPT=""
AUTO_START=1

update_paths() {
    VENV_DIR="${REPO_DIR}/.venv"
    SERVICE_TEMPLATE="${REPO_DIR}/systemd/power2color.service.template"
    RUN_SCRIPT="${REPO_DIR}/run_power2color.sh"
}

update_paths

usage() {
    cat <<'EOF'
Usage: ./install_on_pi.sh [--no-start] [--branch <name>] [--target-dir <path>] [--repo-url <url>]

Installs system packages, creates the Python virtual environment, installs Python
dependencies, and installs/enables the Power2Color systemd service.

Options:
  --no-start    Install and enable the service, but do not start it now.
    --branch      Git branch to clone/use. Default: v3-refactor
    --target-dir  Clone destination when bootstrapping. Default: ~/Power2Color
    --repo-url    Repository URL used for bootstrapping.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-start)
            AUTO_START=0
            shift
            ;;
        --branch)
            REPO_BRANCH="$2"
            shift 2
            ;;
        --target-dir)
            TARGET_DIR="$2"
            shift 2
            ;;
        --repo-url)
            REPO_URL="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

require_sudo() {
    if ! command -v sudo >/dev/null 2>&1; then
        echo "sudo is required for package installation and service setup." >&2
        exit 1
    fi

    sudo -v
}

install_git() {
    sudo apt-get update
    sudo apt-get install -y git
}

ensure_repo() {
    if [[ -d "${REPO_DIR}/.git" ]]; then
        echo "Using existing repository at ${REPO_DIR}"
        return
    fi

    if [[ -e "${TARGET_DIR}" && ! -d "${TARGET_DIR}/.git" ]]; then
        echo "Target directory exists but is not a git repository: ${TARGET_DIR}" >&2
        echo "Remove it or provide a different --target-dir." >&2
        exit 1
    fi

    if [[ -d "${TARGET_DIR}/.git" ]]; then
        echo "Using existing cloned repository at ${TARGET_DIR}"
        REPO_DIR="${TARGET_DIR}"
    else
        echo "Cloning ${REPO_URL} (branch: ${REPO_BRANCH}) to ${TARGET_DIR}"
        git clone --branch "${REPO_BRANCH}" --single-branch "${REPO_URL}" "${TARGET_DIR}"
        REPO_DIR="${TARGET_DIR}"
    fi

    update_paths
}

install_system_packages() {
    sudo apt-get install -y \
        bluetooth \
        bluez \
        build-essential \
        libatlas-base-dev \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv
}

install_python_dependencies() {
    python3 -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --upgrade pip wheel setuptools
    "${VENV_DIR}/bin/pip" install -r "${REPO_DIR}/requirements.txt"
}

install_service() {
    local exec_start
    exec_start="${RUN_SCRIPT}"

    sed \
        -e "s|__WORKING_DIRECTORY__|${REPO_DIR}|g" \
        -e "s|__EXEC_START__|${exec_start}|g" \
        "${SERVICE_TEMPLATE}" | sudo tee "${SERVICE_TARGET}" >/dev/null

    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}"
}

configured_bluetooth_address() {
    awk '
        /^[[:space:]]*address:/ {
            line = $0
            sub(/#.*/, "", line)
            sub(/^[[:space:]]*address:[[:space:]]*/, "", line)
            gsub(/[[:space:]]/, "", line)
            print line
            exit
        }
    ' "${REPO_DIR}/config.yaml"
}

start_service_if_ready() {
    local address
    address="$(configured_bluetooth_address)"

    if [[ ${AUTO_START} -eq 0 ]]; then
        echo "Service installed but not started because --no-start was used."
        return
    fi

    if [[ -z "${address}" ]]; then
        echo "Service installed and enabled, but not started because bluetooth.address is not configured in config.yaml."
        echo "Set the trainer bluetooth address first, or run manually once if you still want interactive device selection."
        return
    fi

    sudo systemctl restart "${SERVICE_NAME}"
    sudo systemctl --no-pager --full status "${SERVICE_NAME}" || true
}

print_next_steps() {
    cat <<EOF

Install complete.

Useful commands:
  sudo systemctl status ${SERVICE_NAME}
  sudo journalctl -u ${SERVICE_NAME} -f
  sudo systemctl restart ${SERVICE_NAME}

Repo directory:
  ${REPO_DIR}

Virtual environment:
  ${VENV_DIR}
EOF
}

main() {
    require_sudo
    install_git
    ensure_repo
    chmod +x "${RUN_SCRIPT}"
    install_system_packages
    install_python_dependencies
    install_service
    start_service_if_ready
    print_next_steps
}

main "$@"
