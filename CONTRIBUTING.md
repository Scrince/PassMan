# Contributing to PassMan

Thanks for helping improve PassMan. Changes should preserve the offline-first
design and protect vault confidentiality and integrity.

## Development setup

Use Python 3.12 or newer and [uv](https://docs.astral.sh/uv/):

```bash
uv sync --locked --extra build --extra dev
uv run python src/main.py
```

The committed `uv.lock` locks the complete dependency graph across supported
platforms. Update it with `uv lock` when changing project dependencies, then
review both `pyproject.toml` and `uv.lock` in the same change.

## Before opening a pull request

```bash
uv run ruff check src tests scripts build.py
uv run python -m unittest discover -s tests -p "test_*.py" -v
```

For packaging or platform-specific changes, build on the target operating
system with `uv run python build.py --skip-package`. Builds do not cross
operating systems. Never include vault files, credentials, private signing
material, virtual environments, or generated build outputs.

Pull requests should describe the user-visible change, security impact where
relevant, and the checks performed. Add focused tests for behavior changes.
Read `docs/Encryption.txt` before changing vault formats or cryptography and
`docs/OpSec.txt` before changing security workflows or claims.

## Release process

Maintainers should follow [docs/ReleaseProcess.md](docs/ReleaseProcess.md).
