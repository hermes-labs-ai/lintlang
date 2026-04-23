# Contributing to lintlang

Thank you for your interest in contributing to lintlang.

## Reporting Bugs

- Search [existing issues](https://github.com/hermes-labs-ai/lintlang/issues) first to avoid duplicates.
- Open a new issue with a clear title and description.
- Include steps to reproduce, expected behavior, and actual behavior.
- Attach sample input files if relevant.

## Submitting Pull Requests

1. Fork the repository.
2. Create a feature branch from `main` (`git checkout -b my-feature`).
3. Make your changes with clear, focused commits.
4. Add or update tests for any new functionality.
5. Run the full test suite before submitting:
   ```bash
   pytest
   ```
6. Open a pull request against `main` with a clear description of the change.

## Code Style

- We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting.
- Run `ruff check .` and `ruff format .` before committing.
- Type hints are required on all public functions.
- Use `from __future__ import annotations` in all modules.

## Testing

- All tests use [pytest](https://docs.pytest.org/).
- Run with coverage: `pytest --cov=lintlang --cov-report=term-missing`
- New features must include test coverage.

## Development Setup

```bash
pip install -e ".[dev]"
```

## Questions?

Open an issue or start a discussion on the repository.
