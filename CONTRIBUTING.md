# Contributing to python-can-j1939

Thank you for your interest in contributing! Please read this guide before opening a pull request.

## Requirements

- **Python 3.10 or later** — the codebase uses `match`/`case` (PEP 622) and `X | Y` union types (PEP 604).

## Setting up a development environment

```bash
git clone https://github.com/RaulSMS/python-can-j1939.git
cd python-can-j1939

# Install the package in editable mode with test and lint dependencies
pip install -e ".[test,lint]"
```

## Running the tests

```bash
pytest . --pyargs
```

All tests must pass before submitting a pull request. CI runs the full suite on Python 3.10–3.13 across Ubuntu, macOS, and Windows.

## Code style

This project uses [ruff](https://docs.astral.sh/ruff/) to enforce a consistent style (rules `E` and `F`).

Check your changes before committing:

```bash
ruff check .
```

Fix violations before opening a PR — the CI lint job will reject any remaining issues.

Key rules enforced:

- Use `is None` / `is not None` instead of `== None` / `!= None`.
- Use truthiness checks (`if x:`) instead of `== True` / `== False`.
- Remove unused imports and variables.
- No multiple statements on one line (no `if x: do_something()`).

## Branching and commits

- Branch off `master` for new features and bug fixes.
- Use descriptive branch names: `fix/some-bug`, `feature/new-thing`, `docs/update-readme`.
- Keep commits focused — one logical change per commit.
- Write commit messages in the imperative mood: `fix transport protocol timeout`, not `fixed timeout`.

## Type checking

This project uses [Pyright](https://github.com/microsoft/pyright) for static type analysis.

```bash
pyright
```

Configuration is in `pyrightconfig.json` (covers `j1939/` only, `basic` mode). Fix any new errors introduced by your change before opening a PR.

## Pull request checklist

- [ ] Tests pass: `pytest . --pyargs`
- [ ] No lint violations: `ruff check .`
- [ ] No type errors: `pyright`
- [ ] New protocol behaviour is covered by tests in `test/` using the `Feeder` fixture (see `test/helpers/feeder.py`).
- [ ] Changes that affect both J1939-21 and J1939-22 are applied to **both** `j1939/j1939_21.py` and `j1939/j1939_22.py`.
- [ ] Public API additions are exported from `j1939/__init__.py`.

## Release Process

Releases are fully automated via GitHub Actions CI/CD pipelines but are strictly gated to maintainers to preserve package security.

### Requesting a New Release
If you are a contributor and believe a new version should be published (e.g., after a significant feature addition or bug fix has landed on master):
1. Open a new Issue on GitHub requesting a release.
2. Assign the issue to the project maintainer (RaulSMS).
3. The maintainer will review the state of the master branch and initiate the release deployment sequence.

### Maintainer Deployment Sequence (For Reference)
Only RaulSMS has permission to publish releases to PyPI. The steps are:
1. Update the version string inside j1939/version.py on the master branch.
2. Push a semantic version tag matching the v* pattern:
   git tag v2.1.0
   git push origin v2.1.0
3. The CI/CD system will automatically catch the tag push, execute all tests, generate a GitHub Release with an automated changelog, and securely upload the package distributions to PyPI.

## Architecture overview

See [CLAUDE.md](CLAUDE.md) for a detailed description of the layered architecture (ECU → DLL → ControllerApplication), the threading model, and pointers to each module.
