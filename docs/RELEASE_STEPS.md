# Step-by-Step Release Process

This guide walks you through releasing a new version to PyPI, following PreOCR's quality standards.

## Prerequisites

- ✅ All changes committed and pushed
- ✅ Tests passing locally
- ✅ CHANGELOG.md guidelines reviewed (`docs/CHANGELOG_GUIDELINES.md`)

## Step-by-Step Process

### Step 1: Determine Version Number

Decide on the version number based on [Semantic Versioning](https://semver.org/):

- **Major** (X.0.0): Breaking changes
- **Minor** (0.X.0): New features, backward compatible
- **Patch** (0.0.X): Bug fixes, backward compatible

**Example:** If current version is `0.7.0`:
- Major release: `1.0.0` (breaking changes)
- Minor release: `0.8.0` (new features)
- Patch release: `0.7.1` (bug fixes)

### Step 2: Update CHANGELOG.md

**Location:** `docs/CHANGELOG.md`

1. **Add new version entry** after `[Unreleased]` section:

```markdown
## [Unreleased]

## [1.0.0] - 2026-01-20

### Added
- **Major Feature**: Clear description of what was added
- **Another Feature**: Description

### Changed
- **Component**: What changed and impact

### Fixed
- **Issue**: What was fixed

### Breaking Changes
- **API Change**: Description of breaking change and migration path
```

2. **Follow quality standards:**
   - ✅ Use proper date format (YYYY-MM-DD)
   - ✅ Use structured sections (Added/Changed/Fixed)
   - ✅ Use **bold** for feature/component names
   - ✅ Write user-focused descriptions
   - ✅ Document all significant changes

3. **Update links section** at bottom of file:

```markdown
[Unreleased]: https://github.com/yuvaraj3855/preocr/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yuvaraj3855/preocr/releases/tag/v1.0.0
[0.7.0]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.7.0
...
```

**Quick check:**
```bash
# Verify entry exists
grep "^## \[1.0.0\]" docs/CHANGELOG.md

# Verify date format
grep "^## \[1.0.0\]" docs/CHANGELOG.md | grep -E "[0-9]{4}-[0-9]{2}-[0-9]{2}"
```

### Step 3: Update Version in Code

**Location:** `preocr/version.py`

```python
"""Version information for preocr package."""

__version__ = "1.0.0"
```

**Verify:**
```bash
python -c "from preocr.version import __version__; print(__version__)"
# Should output: 1.0.0
```

### Step 4: Commit Changes

```bash
# Stage changes
git add docs/CHANGELOG.md preocr/version.py

# Commit with descriptive message
git commit -m "chore: prepare release v1.0.0"

# Push to your branch
git push origin your-branch-name
```

### Step 5: Create Version Bump PR

1. **Create Pull Request** with title:
   ```
   chore: bump version to 1.0.0
   ```

2. **PR Description** (optional but recommended):
   ```markdown
   ## Release v1.0.0
   
   ### Changes Summary
   - Major feature: ...
   - Breaking changes: ...
   
   ### Checklist
   - [x] CHANGELOG.md updated
   - [x] Version updated in version.py
   - [x] Tests passing
   - [x] Documentation reviewed
   ```

3. **CI/CD will automatically:**
   - ✅ Validate CHANGELOG.md entry exists and is well-formatted
   - ✅ Run tests
   - ✅ Run linting
   - ✅ Validate release files

### Step 6: Review and Merge PR

1. **Review CI/CD results:**
   - All checks should pass ✅
   - CHANGELOG.md validation should pass ✅
   - Tests should pass ✅

2. **Merge the PR** to `main` branch

3. **CI/CD will automatically:**
   - Create git tag `v1.0.0` with detailed message
   - Generate release files (`releases/v1.0.0.md` and `releases/v1.0.0.json`)
   - Commit release files to repository
   - Create GitHub Release
   - **Publish to PyPI** 🚀

### Step 7: Verify Release

#### Check Git Tag

```bash
# View tag
git tag -l "v1.0.0"
git show v1.0.0

# Verify tag message includes:
# - Release date
# - Link to CHANGELOG.md
# - Link to GitHub release
```

#### Check GitHub Release

1. Go to: https://github.com/yuvaraj3855/preocr/releases
2. Verify release `v1.0.0` exists
3. Check release notes are populated from CHANGELOG.md

#### Check PyPI

1. Go to: https://pypi.org/project/preocr/
2. Verify version `1.0.0` is listed
3. Test installation:

```bash
pip install --upgrade preocr
python -c "from preocr import __version__; print(__version__)"
# Should output: 1.0.0
```

#### Check Release Files

```bash
# Verify release files exist
ls -la releases/v1.0.0.*

# View release JSON
python scripts/get_release_info.py v1.0.0 --format json

# View release Markdown
python scripts/get_release_info.py v1.0.0 --format markdown
```

## Troubleshooting

### CI/CD Fails: CHANGELOG.md Missing Entry

**Error:** `ERROR: CHANGELOG.md entry missing for version X.Y.Z`

**Solution:**
1. Add entry to CHANGELOG.md
2. Update PR with new commit
3. CI/CD will re-validate

### CI/CD Fails: CHANGELOG.md Format Issues

**Error:** `WARNING: CHANGELOG.md entry lacks structured sections`

**Solution:**
1. Review `docs/CHANGELOG_GUIDELINES.md`
2. Ensure entry has proper sections (Added/Changed/Fixed)
3. Update CHANGELOG.md entry
4. Update PR

### Tag Already Exists

**Error:** `Tag v1.0.0 already exists`

**Solution:**
```bash
# Delete local tag
git tag -d v1.0.0

# Delete remote tag
git push origin --delete v1.0.0

# Re-run workflow or create tag manually
```

### PyPI Upload Fails

**Error:** PyPI publishing fails

**Solution:**
1. Check PyPI API token is configured in GitHub Secrets
2. Verify package name is correct
3. Check for version conflicts (version already exists on PyPI)
4. Review workflow logs for specific error

## Quick Reference

### Files to Update

1. ✅ `docs/CHANGELOG.md` - Add version entry
2. ✅ `preocr/version.py` - Update version number

### Commands

```bash
# Verify version
python -c "from preocr.version import __version__; print(__version__)"

# Check CHANGELOG entry
grep "^## \[1.0.0\]" docs/CHANGELOG.md

# Generate release files manually (if needed)
python scripts/generate_release.py v1.0.0

# Query release info
python scripts/get_release_info.py v1.0.0

# Test installation from PyPI
pip install --upgrade preocr
```

### PR Title Format

**Required:** `chore: bump version to X.Y.Z`

This triggers the automated release workflow.

## Post-Release Checklist

After successful release:

- [ ] Verify PyPI package is accessible
- [ ] Test installation from PyPI
- [ ] Verify GitHub Release has correct notes
- [ ] Check release files are committed
- [ ] Update any external documentation
- [ ] Announce release (if applicable)

## Next Steps After Release

1. **Create new development branch** for next version
2. **Update [Unreleased] section** in CHANGELOG.md for future changes
3. **Continue development** on new features/fixes

## Support

- **CHANGELOG Guidelines:** `docs/CHANGELOG_GUIDELINES.md`
- **Release Guide:** `docs/RELEASE.md`
- **Release Folder:** `releases/README.md`

