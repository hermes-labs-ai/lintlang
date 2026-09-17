# LintLang Dev Container Feature

Installs an exact LintLang release in an isolated virtual environment and exposes
the `lintlang` command at `/usr/local/bin/lintlang`.

```json
{
  "features": {
    "ghcr.io/hermes-labs-ai/lintlang/lintlang:1": {}
  }
}
```

The default package pin is LintLang `0.6.0`. Override it only with an exact
released PyPI version:

```json
{
  "features": {
    "ghcr.io/hermes-labs-ai/lintlang/lintlang:1": {
      "version": "0.6.0"
    }
  }
}
```

This Feature currently supports Debian/Ubuntu base images on `amd64` and
`arm64`. It installs Python 3.10+ and `python3-venv` through `apt-get`; Alpine,
RPM-based images, unsupported architectures, and non-root Feature installation
are rejected explicitly.

After installation:

```bash
lintlang scan AGENTS.md --fail-on fail
```

LintLang is zero-LLM and deterministic. A `FAIL` scan is an expected analyzer
result, while a missing or malformed input remains an error.
