# PyPI Trusted Publisher Setup for CI/CD Release Pipeline

## Current Issue

The workflow `ci-cd-release.yml` is trying to publish, but the trusted publisher on PyPI is configured for a different workflow.

## Error Details

The error shows these claims from GitHub:
- **Workflow:** `yuvaraj3855/preocr/.github/workflows/ci-cd-release.yml@refs/heads/main`
- **Repository:** `yuvaraj3855/preocr`
- **Branch:** `refs/heads/main`

## Solution: Update Trusted Publisher on PyPI

### Step 1: Go to PyPI Project Settings

1. Go to https://pypi.org/manage/projects/
2. Click on your project: **preocr**
3. Go to **"Publishing"** tab
4. Scroll to **"Trusted publishers"** section

### Step 2: Update or Add Trusted Publisher

**Option A: Update Existing Publisher**
1. Find the existing trusted publisher
2. Click **"Edit"** or **"Remove"** and add a new one
3. Update the workflow filename to: `.github/workflows/ci-cd-release.yml`

**Option B: Add New Publisher**
1. Click **"Add"** under Trusted publishers
2. Fill in:
   - **PyPI project name:** `preocr`
   - **Owner:** `yuvaraj3855`
   - **Repository name:** `preocr`
   - **Workflow filename:** `.github/workflows/ci-cd-release.yml` ⚠️ **IMPORTANT: Must match exactly**
   - **Environment name:** (leave empty)
3. Click **"Add trusted publisher"**

### Step 3: Verify Configuration

The trusted publisher should match:
- ✅ Repository: `yuvaraj3855/preocr`
- ✅ Workflow file: `.github/workflows/ci-cd-release.yml`
- ✅ Branch: `main` (or leave empty for all branches)

## Alternative: Use API Token (Quick Fix)

If you want to publish immediately without setting up trusted publishing:

1. Go to https://pypi.org/manage/account/token/
2. Create API token with scope: **"Project: preocr"**
3. In GitHub: **Settings → Secrets and variables → Actions**
4. Add secret: `PYPI_API_TOKEN` with your token value
5. Update workflow to use token (see below)

## Update Workflow to Use API Token (If Needed)

If you choose the API token method, update the publish step in `ci-cd-release.yml`:

```yaml
- name: Publish to PyPI
  if: needs.version-bump.outputs.should_bump == 'true' && steps.check_tag.outputs.exists == 'false'
  env:
    TWINE_USERNAME: __token__
    TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
  run: |
    twine upload dist/*
```

But **trusted publishing is recommended** as it's more secure and doesn't require managing secrets.



