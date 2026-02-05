# PyPI Release Guide - PreOCR

> **For step-by-step release instructions, see [RELEASE_STEPS.md](RELEASE_STEPS.md)**

# PyPI Release Guide - PreOCR v0.4.0

## Pre-Release Checklist

✅ **Completed:**
- [x] Version updated to 0.4.0 in `preocr/version.py`
- [x] CHANGELOG.md updated with all improvements
- [x] Package built successfully (`dist/preocr-0.4.0-py3-none-any.whl` and `preocr-0.4.0.tar.gz`)
- [x] All new modules included (exceptions.py, logger.py, cache.py)
- [x] pyproject.toml configured correctly with dynamic version

## Uploading to PyPI

### Option 1: Using twine (Recommended)

1. **Install twine** (if not already installed):
   ```bash
   pip install twine
   ```

2. **Check the package** (optional but recommended):
   ```bash
   twine check dist/*
   ```

3. **Upload to TestPyPI first** (recommended for testing):
   ```bash
   twine upload --repository testpypi dist/*
   ```
   - You'll need TestPyPI credentials: https://test.pypi.org/account/register/

4. **Test installation from TestPyPI**:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ preocr
   ```

5. **Upload to PyPI** (production):
   ```bash
   twine upload dist/*
   ```
   - You'll need PyPI credentials: https://pypi.org/account/register/
   - Or use API token: https://pypi.org/manage/account/token/

### Option 2: Using GitHub Actions (Automated)

The repository already has a GitHub Actions workflow (`.github/workflows/publish.yml`) that will automatically publish when you:

1. **Create a git tag**:
   ```bash
   git tag v0.4.0
   git push origin v0.4.0
   ```

2. **Create a GitHub Release**:
   - Go to GitHub → Releases → Create a new release
   - Tag: `v0.4.0`
   - Title: `PreOCR v0.4.0`
   - Description: Copy from CHANGELOG.md
   - Publish release

The workflow will automatically:
- Build the package
- Run tests
- Upload to PyPI (if PYPI_API_TOKEN secret is configured)

### Option 3: Using build and upload directly

```bash
# Build
python -m build

# Upload
python -m twine upload dist/*
```

## Post-Release

After successful upload:

1. **Verify on PyPI**: https://pypi.org/project/preocr/
2. **Test installation**:
   ```bash
   pip install --upgrade preocr
   python -c "from preocr import needs_ocr, __version__; print(__version__)"
   ```
3. **Update GitHub release notes** (if using manual upload)
4. **Announce the release** (if applicable)

## Version Information

- **Current Version**: 0.4.0
- **Package Name**: preocr
- **Python Requirements**: >=3.9
- **Build Files**:
  - `dist/preocr-0.4.0-py3-none-any.whl` (37K)
  - `dist/preocr-0.4.0.tar.gz` (43K)

## What's New in v0.4.0

- Custom exception classes for better error handling
- Logging framework with environment variable support
- Optional caching for repeated analysis
- Progress callbacks for batch processing
- Type safety improvements (all type hints fixed)
- CI/CD pipeline with GitHub Actions
- Pre-commit hooks for code quality
- Enhanced documentation and project files

See CHANGELOG.md for complete details.

## Release Folder Management

PreOCR maintains versioned release notes in the `releases/` folder. Each release has two files:

- `vX.Y.Z.md` - Human-readable release notes
- `vX.Y.Z.json` - Machine-readable release metadata

### Automatic Generation

Release files are automatically generated when a version bump PR is merged:

1. Version is bumped in `preocr/version.py`
2. CHANGELOG.md is updated with new version entry
3. On PR merge, CI/CD automatically:
   - Generates release files (`releases/vX.Y.Z.md` and `releases/vX.Y.Z.json`)
   - Commits them to the repository
   - Uses them for GitHub Release notes

### Manual Generation

You can also generate release files manually:

```bash
# Generate for current version
python scripts/generate_release.py

# Generate for specific version
python scripts/generate_release.py v0.4.0

# Sync all releases from CHANGELOG.md
python scripts/sync_releases.py
```

### Query Release Information

Query release information for CI/CD or scripts:

```bash
# Get JSON (default)
python scripts/get_release_info.py v0.4.0

# Get Markdown
python scripts/get_release_info.py v0.4.0 --format markdown

# List all releases
python scripts/get_release_info.py --list
```

### CI/CD Integration

Release files are integrated into the CI/CD pipeline:

- **On Version Bump**: Release files are auto-generated and committed
- **GitHub Releases**: JSON files are used to populate release descriptions
- **Validation**: CI/CD validates that release files exist and are properly formatted

For more details, see `releases/README.md`.

## CHANGELOG.md Quality Standards

Starting from version 0.8.0, all CHANGELOG.md entries must be:

- **Clear and well-structured**: Use proper sections (Added/Changed/Fixed)
- **User-focused**: Write for end users, not developers
- **Well-formatted**: Use bold for features, proper dates, structured sections
- **Complete**: Document all significant changes

See `docs/CHANGELOG_GUIDELINES.md` for detailed guidelines and examples.

### Validation

CI/CD automatically validates:
- CHANGELOG.md entry exists for the version
- Entry has proper date format (YYYY-MM-DD)
- Entry has structured sections
- Quality indicators (bold features, clear descriptions)

The workflow will **fail** if CHANGELOG.md entry is missing or improperly formatted.

