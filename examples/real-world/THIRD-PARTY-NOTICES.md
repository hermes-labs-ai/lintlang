# Third-party inputs

The example inputs below were copied unchanged from public repositories at the pinned commit. LintLang did not write them and does not endorse them. A finding is a reason to read a file, not a verdict on its authors.

| Input in this repository | Upstream file | Commit | License | sha256 |
| --- | --- | --- | --- | --- |
| `okta-tool-manifest/input.json` | [docker/mcp-registry `servers/okta-mcp-server/tools.json`](https://github.com/docker/mcp-registry/blob/49b643ce3fc73e6ee80bb962719b6e2990e3d397/servers/okta-mcp-server/tools.json) | `49b643ce3fc73e6ee80bb962719b6e2990e3d397` | MIT, Copyright (c) 2025 Docker | `2b740b09adb53c9cbea690940208167df10edd710d3fc2a68ece53e9cde0c130` |
| `ci-gate-exit-codes/input-unrecognized-shape.json` | [docker/mcp-registry `servers/astro-docs/tools.json`](https://github.com/docker/mcp-registry/blob/49b643ce3fc73e6ee80bb962719b6e2990e3d397/servers/astro-docs/tools.json) | `49b643ce3fc73e6ee80bb962719b6e2990e3d397` | MIT, Copyright (c) 2025 Docker | `9756a1e9176917945823cbd2c8d5eb763b4c83e6257235a369474cf079919f33` |
| `baseline-tool-manifest/input.json` | [julymetodiev/post-cortex `tools.json`](https://github.com/julymetodiev/post-cortex/blob/da4b511dfc1322ff16256515afa5167b67f98499/tools.json) | `da4b511dfc1322ff16256515afa5167b67f98499` | MIT, Copyright (c) 2025 Julius ML | `48a6434dbfe98eb10428e2b45a57030f924c29aa1d107ff3be6ec59b4bab36a1` |
| `openrouter-skill-benchmarks/input/SKILL.md` (not vendored) | [OpenRouterTeam/skills `skills/openrouter-benchmarks/SKILL.md`](https://github.com/OpenRouterTeam/skills/blob/33597a44e38b0cdc38ea1256ef8bcf50c2704e3d/skills/openrouter-benchmarks/SKILL.md) | `33597a44e38b0cdc38ea1256ef8bcf50c2704e3d` | None declared in the repository | `6bfc172fe75e95c9b2f9df0510d61f5913663e123f70ae4d94e351a9401940fd` |

The MIT permission notice for the three vendored files is the one in each upstream `LICENSE` file at the pinned commit:

> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.

The OpenRouterTeam/skills repository declares no license, so its `SKILL.md` is not copied here. The example pins it by commit and checksum and its README shows how to fetch it. The skill-empty-description inputs were written for this repository.
