# Release Workflow Explained

## How Version Bumping Works

### CI/CD Does NOT Automatically Update Versions

**Important:** CI/CD does **NOT** automatically update `version.py`. You must update it manually before creating the release PR.

### The Workflow

```
1. You update CHANGELOG.md manually ✅
2. You update preocr/version.py manually ✅
3. You create a branch and PR ✅
4. CI/CD validates everything ✅
5. When PR is merged, CI/CD creates tag and publishes ✅
```

## Step-by-Step Process

### Option 1: Branch + PR (Recommended for Major Releases)

**Best for:** Major releases (1.0.0), breaking changes, or when you want review

1. **Create a branch:**
   ```bash
   git checkout -b release/v1.0.0
   ```

2. **Update CHANGELOG.md** (already done ✅)
   - Add version entry with clear, well-structured changes

3. **Update version.py:**
   ```bash
   # Edit preocr/version.py
   __version__ = "1.0.0"
   ```

4. **Commit changes:**
   ```bash
   git add docs/CHANGELOG.md preocr/version.py
   git commit -m "chore: prepare release v1.0.0"
   git push origin release/v1.0.0
   ```

5. **Create Pull Request:**
   - Title: `chore: bump version to 1.0.0` (exact format required!)
   - Description: Summary of changes
   - CI/CD will validate:
     - CHANGELOG.md entry exists and is well-formatted
     - Version matches in version.py
     - Tests pass
     - Linting passes

6. **Review and Merge PR:**
   - Review CI/CD validation results
   - Merge when ready

7. **CI/CD Automatically:**
   - Creates git tag `v1.0.0` with detailed message
   - Generates release files (`releases/v1.0.0.md` and `releases/v1.0.0.json`)
   - Commits release files to repository
   - Creates GitHub Release
   - Publishes to PyPI 🚀

### Option 2: Direct Commit to Main (Not Recommended)

**Only for:** Emergency patches or if you have direct main access

```bash
# On main branch
git add docs/CHANGELOG.md preocr/version.py
git commit -m "chore: bump version to 1.0.0"
git push origin main
```

**Note:** This still requires the commit message to contain "bump version" for CI/CD to trigger.

## Why Manual Version Updates?

### Advantages:
- ✅ **Full Control**: You decide exactly when to release
- ✅ **Review Process**: PR allows team review before release
- ✅ **Quality Assurance**: CI/CD validates everything before release
- ✅ **Clear History**: Git history shows intentional version bumps
- ✅ **Major Releases**: Perfect for major releases where you want careful review

### CI/CD's Role:
- ✅ **Validates** CHANGELOG.md entry exists and is well-formatted
- ✅ **Validates** version.py matches expected version
- ✅ **Creates** git tag with detailed message
- ✅ **Generates** release files automatically
- ✅ **Publishes** to PyPI automatically
- ❌ **Does NOT** update version.py (you do this manually)

## Current Workflow Summary

```
┌─────────────────────────────────────────┐
│ 1. You: Update CHANGELOG.md            │
│    (Add version entry)                 │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 2. You: Update preocr/version.py       │
│    (Set new version)                    │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 3. You: Create branch & PR              │
│    (Title: "chore: bump version to X") │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 4. CI/CD: Validates everything         │
│    - CHANGELOG.md entry                 │
│    - Version consistency                │
│    - Tests & linting                    │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 5. You: Review & Merge PR              │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 6. CI/CD: Automatic Release             │
│    - Creates git tag                    │
│    - Generates release files            │
│    - Creates GitHub Release             │
│    - Publishes to PyPI                  │
└─────────────────────────────────────────┘
```

## Quick Reference

### PR Title Format (Required!)
```
chore: bump version to 1.0.0
```

This exact format triggers the release workflow.

### Files You Must Update Manually:
1. ✅ `docs/CHANGELOG.md` - Add version entry
2. ✅ `preocr/version.py` - Update version number

### What CI/CD Does Automatically:
- ✅ Validates CHANGELOG.md
- ✅ Creates git tag
- ✅ Generates release files
- ✅ Publishes to PyPI

## Best Practices

1. **Always use a branch** for releases (allows review)
2. **Update CHANGELOG.md first** (documentation before code)
3. **Update version.py** to match CHANGELOG.md version
4. **Use exact PR title format** (`chore: bump version to X.Y.Z`)
5. **Review CI/CD validation** before merging
6. **Verify release** after merge (check PyPI, GitHub Release)

## Troubleshooting

### CI/CD Not Triggering?
- Check PR title contains "bump version"
- Verify PR was merged (not just closed)
- Check workflow logs in GitHub Actions

### Version Mismatch Error?
- Ensure `preocr/version.py` matches CHANGELOG.md version
- Ensure version format is correct (X.Y.Z)

### CHANGELOG Validation Fails?
- Check entry exists: `grep "^## \[1.0.0\]" docs/CHANGELOG.md`
- Check date format: `YYYY-MM-DD`
- Check structured sections (Added/Changed/Fixed)

