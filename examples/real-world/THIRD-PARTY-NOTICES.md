# Third-party inputs

The example inputs below were copied from public repositories at the pinned commit (the Okta manifest is a documented 16-tool excerpt, described in its README). LintLang did not write them and does not endorse them. A finding is a reason to read a file, not a verdict on its authors.

| Input in this repository | Upstream file | Commit | License | sha256 |
| --- | --- | --- | --- | --- |
| `okta-tool-manifest/input.json` | [docker/mcp-registry `servers/okta-mcp-server/tools.json`](https://github.com/docker/mcp-registry/blob/49b643ce3fc73e6ee80bb962719b6e2990e3d397/servers/okta-mcp-server/tools.json) | `49b643ce3fc73e6ee80bb962719b6e2990e3d397` | MIT, Copyright (c) 2025 Docker | `635119ee73ab64163f9a2f6d51ada013f1002d5cdfee47a1381be759b1bfcc92` (excerpt; full upstream file `2b740b09adb53c9cbea690940208167df10edd710d3fc2a68ece53e9cde0c130`) |
| `ci-gate-exit-codes/input-unrecognized-shape.json` | [docker/mcp-registry `servers/astro-docs/tools.json`](https://github.com/docker/mcp-registry/blob/49b643ce3fc73e6ee80bb962719b6e2990e3d397/servers/astro-docs/tools.json) | `49b643ce3fc73e6ee80bb962719b6e2990e3d397` | MIT, Copyright (c) 2025 Docker | `9756a1e9176917945823cbd2c8d5eb763b4c83e6257235a369474cf079919f33` |
| `baseline-tool-manifest/input.json` | [julymetodiev/post-cortex `tools.json`](https://github.com/julymetodiev/post-cortex/blob/da4b511dfc1322ff16256515afa5167b67f98499/tools.json) | `da4b511dfc1322ff16256515afa5167b67f98499` | MIT, Copyright (c) 2025 Julius ML | `48a6434dbfe98eb10428e2b45a57030f924c29aa1d107ff3be6ec59b4bab36a1` |
| `openrouter-skill-benchmarks/input/SKILL.md` (not vendored) | [OpenRouterTeam/skills `skills/openrouter-benchmarks/SKILL.md`](https://github.com/OpenRouterTeam/skills/blob/33597a44e38b0cdc38ea1256ef8bcf50c2704e3d/skills/openrouter-benchmarks/SKILL.md) | `33597a44e38b0cdc38ea1256ef8bcf50c2704e3d` | None declared in the repository | `6bfc172fe75e95c9b2f9df0510d61f5913663e123f70ae4d94e351a9401940fd` |

The full, unmodified upstream MIT license texts (copyright notice and permission notice) travel with the copies: [`LICENSES/docker-mcp-registry.LICENSE`](LICENSES/docker-mcp-registry.LICENSE) covers the two docker/mcp-registry files, and [`LICENSES/post-cortex.LICENSE`](LICENSES/post-cortex.LICENSE) covers the post-cortex file. Both were fetched from the upstream repositories at the pinned commits.

The OpenRouterTeam/skills repository declares no license, so its `SKILL.md` is not copied here. The example pins it by commit and checksum and its README shows how to fetch it. The skill-empty-description inputs were written for this repository.
