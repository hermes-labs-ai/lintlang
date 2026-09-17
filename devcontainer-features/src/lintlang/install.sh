#!/bin/bash
set -euo pipefail

readonly requested_version="${VERSION:-0.6.0}"
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

if ! command -v apt-get >/dev/null 2>&1; then
    echo "LintLang Feature supports Debian/Ubuntu images with apt-get; this base image is unsupported." >&2
    exit 1
fi

case "${requested_version}" in
    ''|*[!0-9A-Za-z.+-]*)
        echo "LintLang version must be an exact PyPI version string; found '${requested_version}'." >&2
        exit 1
        ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install --no-install-recommends -y ca-certificates python3 python3-venv
rm -rf /var/lib/apt/lists/*

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "LintLang ${requested_version} requires Python 3.10 or newer; found $(python3 --version)." >&2
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
