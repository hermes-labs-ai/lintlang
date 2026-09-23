# LintLang for GitHub Copilot CLI

Install the Hermes Labs plugin directly from its GitHub repository:

```bash
copilot plugin install hermes-labs-ai/lintlang:integrations/copilot-cli
```

In a new Copilot CLI session, use `/skills list` to confirm that
`lintlang-audit` loaded. Ask Copilot to audit a named file, for example:

```text
Use lintlang-audit to scan .github/copilot-instructions.md and report its verdict and findings.
```

The skill scans the named agent instruction, tool definition, or prompt file
with LintLang and summarizes its static findings. It does not scan all files
automatically or change the target. Install the scanner separately with
`python -m pip install lintlang==0.7.0`, or have `uvx` available to run that
release on demand. The plugin itself does not include the Python package.
Python 3.10+ is required for the scanner. A scan makes no LLM or network calls;
installing the scanner may download packages. A `PASS` verdict only means that
the selected static checks found no covered issue above `LOW`.

To remove the plugin, run `copilot plugin uninstall lintlang`.

This plugin uses the [Agent Plugins 1.0 format](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-creating).
The direct `OWNER/REPO:PATH` install form is documented in the
[Copilot CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference#plugin-specification-for-install-command).
