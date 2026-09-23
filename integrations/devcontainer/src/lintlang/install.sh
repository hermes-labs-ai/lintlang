#!/bin/bash
set -euo pipefail

readonly requested_version="${VERSION:-0.7.0}"
readonly install_root="/opt/lintlang-${requested_version}"

if [ "$(id -u)" -ne 0 ]; then
    echo "LintLang Feature must run as root during container build." >&2
    exit 1
fi

case "$(uname -m)" in
    x86_64|amd64|aarch64|arm64)
        ;;
    *)
        echo "LintLang Feature supports amd64 and arm64 only; found $(uname -m)." >&2
        exit 1
        ;;
esac

if [ ! -r /etc/os-release ]; then
    echo "LintLang Feature supports Debian/Ubuntu images; /etc/os-release is missing." >&2
    exit 1
fi

# Keep the support boundary aligned with the Feature documentation.  Merely
# having apt-get is not sufficient: several non-Debian images provide it as a
# compatibility tool while having incompatible package/runtime semantics.
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in
    debian|ubuntu)
        ;;
    *)
        echo "LintLang Feature supports Debian/Ubuntu images; found '${ID:-unknown}'." >&2
        exit 1
        ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install --no-install-recommends -y ca-certificates python3 python3-packaging python3-venv
rm -rf /var/lib/apt/lists/*

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "LintLang ${requested_version} requires Python 3.10 or newer; found $(python3 --version)." >&2
    exit 1
fi

if ! REQUESTED_VERSION="${requested_version}" python3 -c 'from packaging.version import Version; import os; Version(os.environ["REQUESTED_VERSION"])'; then
    echo "LintLang version must be a valid PEP 440 version string; found '${requested_version}'." >&2
    exit 1
fi
python3 -m venv "${install_root}"
"${install_root}/bin/python" -m pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    "lintlang==${requested_version}"

ln -sfn "${install_root}/bin/lintlang" /usr/local/bin/lintlang
ln -sfn "${install_root}/bin/python" /usr/local/bin/lintlang-python

echo "Installed lintlang ${requested_version} in ${install_root}."
