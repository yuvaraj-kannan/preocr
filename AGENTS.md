# AGENTS.md

## Cursor Cloud specific instructions

This is a **pure Python library** (`preocr`) — no databases, Docker, web servers, or external services.

### Quick reference

| Action | Command |
|--------|---------|
| Install (dev) | `pip install -e ".[dev]"` |
| Tests | `pytest` (runs with `--cov=preocr` by default via `pyproject.toml`) |
| Lint | `ruff check preocr/` |
| Format check | `black --check preocr/` |
| Type check | `mypy preocr/` (note: pre-existing `import-untyped` errors for `fitz`, `openpyxl`, `tqdm`; the pre-commit config passes `--ignore-missing-imports`) |

### Non-obvious notes

- **System dependency**: `libmagic1` must be installed (`apt-get install -y libmagic1`). It is pre-installed on the Cloud VM.
- **PATH**: pip installs scripts to `~/.local/bin` — ensure it is on `PATH` (`export PATH="$HOME/.local/bin:$PATH"`).
- **No dataset files in repo**: The `datasets/` directory referenced in examples/scripts is not committed. Tests use mocks/temp files and do not require dataset files.
- **mypy standalone vs pre-commit**: Running `mypy preocr/` without `--ignore-missing-imports` will show ~11 `import-untyped` errors. This is expected. The `.pre-commit-config.yaml` hooks pass `--ignore-missing-imports`.
