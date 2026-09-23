#!/bin/bash
set -euo pipefail

source dev-container-features-test-lib

check "installed command reports the requested release" bash -c "lintlang --version | grep -Fx 'lintlang 0.7.0'"

cat > /tmp/lintlang-clean.yaml <<'YAML'
system_prompt: |
  You are a support agent. Only process the selected ticket and report the result.
  Set a stop_condition of 3 tool calls per ticket. If no progress is made after 2 attempts, stop and report the issue.
tools:
  - name: process_ticket
    description: Retrieve one ticket by its identifier and return its current status.
    parameters:
      type: object
      properties:
        ticket_id:
          type: string
          description: The identifier of the ticket to retrieve.
      required:
        - ticket_id
YAML

cat > /tmp/lintlang-bad.yaml <<'YAML'
system_prompt: |
  You are an agent. Use the tools.
tools:
  - name: process_ticket
    description: ""
    parameters:
      type: object
YAML

cat > /tmp/lintlang-malformed.yaml <<'YAML'
tools:
  - name: [not valid yaml
YAML

check "clean input passes" bash -c "lintlang scan /tmp/lintlang-clean.yaml --fail-on fail >/tmp/lintlang-clean.out"
check "bad input fails the verdict gate" bash -c "! lintlang scan /tmp/lintlang-bad.yaml --fail-on fail >/tmp/lintlang-bad.out 2>/tmp/lintlang-bad.err"
check "malformed input is an error" bash -c "! lintlang scan /tmp/lintlang-malformed.yaml >/tmp/lintlang-malformed.out 2>/tmp/lintlang-malformed.err && grep -F 'Input error' /tmp/lintlang-malformed.err"

reportResults
