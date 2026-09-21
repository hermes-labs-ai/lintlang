#!/bin/bash
set -euo pipefail

# The scenario runner invokes a script named after the scenario key.
exec "$(dirname "$0")/test.sh"
