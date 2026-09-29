# A 108-tool MCP manifest

## What real job this models

A catalog of MCP servers publishes each server's tool list as a JSON file. Before an agent host offers those tools to a model, a reviewer wants to know which descriptions give the model too little to choose with. This example scans the Okta server's manifest as published in the Docker MCP registry.

```bash
lintlang scan input.json
```

Result: `FAIL — 1 HIGH, 2 MEDIUM`, exit `0` (a scan only sets a nonzero exit when you pass a gate such as `--fail-on`; see [ci-gate-exit-codes](../ci-gate-exit-codes/)). All 108 tools were inspected, each with a description and a schema.

- `H1.2` HIGH at line 2047: tool `activate_policy` has an 18-character description, `Activate a policy.`
- `H1.6` MEDIUM at lines 118 and 1802: `confirm_delete_application` and `confirm_delete_group` describe themselves as aliases of `delete_application` and `delete_group`, so the model is offered two tools with no basis to prefer one.

See [expected-output.txt](expected-output.txt) for the exact text.

## Provenance

- Repository: <https://github.com/docker/mcp-registry> (MIT)
- Commit: `49b643ce3fc73e6ee80bb962719b6e2990e3d397`
- File: `servers/okta-mcp-server/tools.json`, copied unchanged as `input.json`
- sha256: `2b740b09adb53c9cbea690940208167df10edd710d3fc2a68ece53e9cde0c130`

License text and notice: [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md). Of the 83 registry `tools.json` files at that commit, this was the only one that reported a HIGH finding when all 83 were scanned with lintlang 0.8.1. Most of the others use an `arguments` shape lintlang does not read (see [ci-gate-exit-codes](../ci-gate-exit-codes/)) or are empty lists.

## What this does not tell you

- The file is a registry snapshot of tool definitions. It is not the Okta server's source, so the scan says nothing about what the tools do when called or whether the server checks permissions.
- A short description is a reason to read the tool, not proof that the model will misuse it. The two alias findings say two tools compete for the same job, not that either is wrong.
- Only the description text and schema in this one file were checked. Descriptions that read well but are inaccurate would pass.
