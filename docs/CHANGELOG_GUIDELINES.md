# CHANGELOG.md Guidelines

This document outlines best practices for maintaining CHANGELOG.md entries to ensure clear, well-structured explanations for all releases.

## Format Standards

### Version Entry Structure

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- **Feature Name**: Clear description of what was added and why it's useful
- **Another Feature**: Description

### Changed
- **Component**: What changed and the impact

### Fixed
- **Issue**: What was fixed and how it affects users

### Deprecated
- **Feature**: What's deprecated and migration path

### Removed
- **Feature**: What was removed and why

### Security
- **Vulnerability**: Security-related changes
```

## Writing Guidelines

### 1. User-Focused Descriptions

✅ **Good:**
```markdown
- **Batch Processing**: Added `BatchProcessor` class for processing multiple files efficiently with progress tracking
```

❌ **Bad:**
```markdown
- Added BatchProcessor class
- Merge pull request #3
```

### 2. Clear and Concise

- Use **bold** for feature/component names
- Explain **what** was added/changed/fixed
- Explain **why** it matters (when relevant)
- Avoid technical jargon unless necessary
- Group related changes together

### 3. Structured Sections

Always use these sections in order:
1. **Added** - New features
2. **Changed** - Changes to existing functionality
3. **Deprecated** - Soon-to-be removed features
4. **Removed** - Removed features
5. **Fixed** - Bug fixes
6. **Security** - Security vulnerabilities

### 4. Version Dates

- Use actual release date (YYYY-MM-DD format)
- Match the date when the git tag was created
- Can be found with: `git log -1 --format=%ai vX.Y.Z`

## Examples

### Minor Release (New Features)

```markdown
## [0.8.0] - 2026-01-20

### Added
- **OCR Integration**: Added `extract_ocr_data()` function for extracting text from scanned documents
- **Image Enhancement**: Pre-processing options for better OCR accuracy
- **Batch OCR Processing**: Support for processing multiple scanned documents

### Changed
- **API Enhancement**: `extract_native_data()` now supports page-level extraction for mixed documents
- **Performance**: Improved extraction speed for large PDFs by 40%

### Fixed
- Fixed memory leak when processing large batches of documents
- Resolved issue with special characters in extracted text
```

### Patch Release (Bug Fixes)

```markdown
## [0.7.1] - 2026-01-15

### Fixed
- Fixed crash when processing corrupted PDF files
- Resolved encoding issues with non-ASCII characters in extracted text
- Fixed incorrect bounding box calculations for rotated pages

### Changed
- Improved error messages for better debugging
```

## CI/CD Validation

The CI/CD pipeline validates:

1. **Version Entry Exists**: CHANGELOG.md must have an entry for the version being released
2. **Proper Format**: Entry must follow the standard format
3. **Date Format**: Date must be in YYYY-MM-DD format
4. **Structured Sections**: Changes should be categorized (Added/Changed/Fixed/etc.)

## Workflow

### Before Creating Version Bump PR

1. **Update CHANGELOG.md**:
   ```bash
   # Add entry after [Unreleased] section
   ## [X.Y.Z] - YYYY-MM-DD
   
   ### Added
   - **Feature**: Description
   ```

2. **Update version.py**:
   ```python
   __version__ = "X.Y.Z"
   ```

3. **Create PR** with title: `chore: bump version to X.Y.Z`

4. **CI/CD will**:
   - Validate CHANGELOG.md entry exists
   - Generate release files from CHANGELOG.md
   - Create git tag with proper message
   - Publish to PyPI

### Git Tag Messages

Tags are automatically created with format:
```
Release vX.Y.Z
```

The tag message includes:
- Version number
- Release date (from CHANGELOG.md)
- Link to release notes

## Quality Checklist

Before merging a version bump PR, ensure:

- [ ] CHANGELOG.md entry is clear and user-focused
- [ ] All significant changes are documented
- [ ] Changes are properly categorized (Added/Changed/Fixed)
- [ ] Date matches the release date
- [ ] No merge commits or technical details in user-facing descriptions
- [ ] Breaking changes are clearly marked
- [ ] Migration guides included for breaking changes (if applicable)

## Helper Scripts

### Generate CHANGELOG Entry Template

```bash
# Generate template for specific version
python scripts/generate_changelog_entries.py --version v0.8.0
```

### Validate CHANGELOG Entry

```bash
# CI/CD automatically validates, but you can check manually:
grep "^## \[0.8.0\]" docs/CHANGELOG.md
```

## Best Practices Summary

1. **Write for users**, not developers
2. **Be specific** about what changed
3. **Explain impact** when relevant
4. **Group related changes** together
5. **Use consistent formatting**
6. **Keep it concise** but informative
7. **Update before** creating version bump PR
8. **Review carefully** before merging

## References

- [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
- [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
- [Conventional Commits](https://www.conventionalcommits.org/)

