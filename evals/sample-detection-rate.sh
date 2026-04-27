#!/bin/bash
# evals/sample-detection-rate.sh — runnable detection-rate check.
#
# Verifies that lintlang catches the 4 deliberately-broken sample configs in
# samples/ and lets the 1 clean config pass. This is the smallest reproducible
# eval surface for the README's flagship claim.
#
# Exit 0 = expected detection rate (4 fail, 1 pass) on the bundled samples.
# Exit 1 = drift; either the rules changed, the samples changed, or detection
# regressed. Investigate before shipping a release.

set -uo pipefail
cd "$(dirname "$0")/.."

if ! command -v lintlang >/dev/null 2>&1; then
    echo "FAIL: lintlang not on PATH. Run 'pip install -e .' first."
    exit 1
fi

EXPECTED_FAIL=("samples/bad_agent_config.json"
               "samples/bad_system_prompt.txt"
               "samples/bad_tool_descriptions.yaml"
               "samples/mixed_issues.yaml")
EXPECTED_PASS=("samples/clean_config.yaml")

fails=0
unexpected=0

for f in "${EXPECTED_FAIL[@]}"; do
    if lintlang scan "$f" --fail-on fail >/dev/null 2>&1; then
        echo "UNEXPECTED PASS on known-bad: $f"
        unexpected=$((unexpected+1))
    else
        echo "  ✓ correctly flagged: $f"
        fails=$((fails+1))
    fi
done

for f in "${EXPECTED_PASS[@]}"; do
    if lintlang scan "$f" --fail-on fail >/dev/null 2>&1; then
        echo "  ✓ correctly passed:  $f"
    else
        echo "UNEXPECTED FAIL on known-clean: $f"
        unexpected=$((unexpected+1))
    fi
done

echo ""
echo "Detection rate on bad samples: $fails/${#EXPECTED_FAIL[@]}"
echo "Unexpected outcomes: $unexpected"

if [[ $unexpected -eq 0 && $fails -eq ${#EXPECTED_FAIL[@]} ]]; then
    echo "PASS — detection on bundled samples matches expected outcomes."
    exit 0
else
    echo "FAIL — detection drifted from expected. Investigate before release."
    exit 1
fi
