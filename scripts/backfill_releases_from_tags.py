#!/usr/bin/env python3
"""
Backfill release files from git tags when CHANGELOG.md entries are missing.

This script generates minimal release files for versions that have git tags
but are missing from CHANGELOG.md.

Usage:
    python scripts/backfill_releases_from_tags.py
    python scripts/backfill_releases_from_tags.py --version v0.5.0
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_git_tags() -> list:
    """Get all version tags from git."""
    try:
        result = subprocess.run(
            ['git', 'tag', '-l', 'v*'],
            capture_output=True,
            text=True,
            check=True
        )
        tags = [tag.strip() for tag in result.stdout.strip().split('\n') if tag.strip()]
        # Sort by version
        def version_key(tag):
            parts = tag.lstrip('v').split('.')
            return tuple(int(p) for p in parts)
        return sorted(tags, key=version_key)
    except Exception as e:
        print(f"Error getting git tags: {e}", file=sys.stderr)
        return []


def get_tag_date(tag: str) -> str:
    """Get the date when a tag was created."""
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%ai', tag],
            capture_output=True,
            text=True,
            check=True
        )
        date_str = result.stdout.strip()
        if date_str:
            # Parse and format as YYYY-MM-DD
            dt = datetime.fromisoformat(date_str.split()[0])
            return dt.strftime('%Y-%m-%d')
    except Exception:
        pass
    return datetime.now().strftime('%Y-%m-%d')


def get_tag_message(tag: str) -> str:
    """Get the tag message."""
    try:
        result = subprocess.run(
            ['git', 'tag', '-l', '--format=%(contents)', tag],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception:
        return f"Release {tag}"


def get_commits_since_previous_tag(tag: str) -> list:
    """Get commit messages since the previous tag."""
    try:
        # Get all tags
        tags = get_git_tags()
        tag_index = tags.index(tag)
        
        if tag_index == 0:
            # First tag, get all commits up to this tag
            result = subprocess.run(
                ['git', 'log', '--format=%s', tag],
                capture_output=True,
                text=True,
                check=True
            )
        else:
            # Get commits between previous tag and this tag
            prev_tag = tags[tag_index - 1]
            result = subprocess.run(
                ['git', 'log', '--format=%s', f'{prev_tag}..{tag}'],
                capture_output=True,
                text=True,
                check=True
            )
        
        commits = [c.strip() for c in result.stdout.strip().split('\n') if c.strip()]
        return commits[:20]  # Limit to 20 commits
    except Exception:
        return []


def generate_minimal_release_files(tag: str, repo_url: str = None) -> tuple:
    """Generate minimal release files from git tag."""
    version = tag.lstrip('v')
    release_date = get_tag_date(tag)
    tag_message = get_tag_message(tag)
    commits = get_commits_since_previous_tag(tag)
    
    if repo_url is None:
        try:
            result = subprocess.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                capture_output=True,
                text=True,
                check=True
            )
            url = result.stdout.strip()
            if url.startswith('git@'):
                url = url.replace('git@github.com:', 'https://github.com/').replace('.git', '')
            elif url.endswith('.git'):
                url = url[:-4]
            repo_url = url
        except Exception:
            repo_url = "https://github.com/yuvaraj3855/preocr"
    
    # Create releases directory
    releases_dir = Path("releases")
    releases_dir.mkdir(exist_ok=True)
    
    # Generate Markdown
    md_content = f"""# Release {tag}

**Release Date**: {release_date}
**Git Tag**: {tag}
**Status**: Released

## Changes

{tag_message}

## Commits

"""
    for commit in commits[:10]:  # Show top 10 commits
        md_content += f"- {commit}\n"
    
    if len(commits) > 10:
        md_content += f"\n*... and {len(commits) - 10} more commits*\n"
    
    md_content += f"""
## Artifacts

- PyPI: https://pypi.org/project/preocr/{version}/
- GitHub Release: {repo_url}/releases/tag/{tag}
"""
    
    # Generate JSON
    json_content = {
        "version": version,
        "tag": tag,
        "release_date": release_date,
        "status": "released",
        "changes": {
            "added": [],
            "changed": [],
            "fixed": []
        },
        "tag_message": tag_message,
        "commits": commits[:10],
        "artifacts": {
            "pypi": f"https://pypi.org/project/preocr/{version}/",
            "github": f"{repo_url}/releases/tag/{tag}"
        },
        "note": "This release file was auto-generated from git tag. CHANGELOG.md entry may be missing."
    }
    
    md_file = releases_dir / f"{tag}.md"
    json_file = releases_dir / f"{tag}.json"
    
    md_file.write_text(md_content)
    json_file.write_text(json.dumps(json_content, indent=2) + '\n')
    
    return md_file, json_file


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill release files from git tags"
    )
    parser.add_argument(
        '--version',
        help='Specific version to backfill (e.g., v0.5.0). If not provided, backfills all missing versions.'
    )
    parser.add_argument(
        '--repo-url',
        help='GitHub repository URL (default: auto-detect from git config)'
    )
    
    args = parser.parse_args()
    
    # Get existing release files
    releases_dir = Path("releases")
    existing_versions = set()
    if releases_dir.exists():
        for json_file in releases_dir.glob("v*.json"):
            try:
                data = json.loads(json_file.read_text())
                existing_versions.add(data['tag'])
            except Exception:
                continue
    
    # Get all git tags
    all_tags = get_git_tags()
    
    if args.version:
        # Backfill specific version
        if args.version not in all_tags:
            print(f"Error: Tag {args.version} not found in git tags", file=sys.stderr)
            sys.exit(1)
        
        if args.version in existing_versions:
            print(f"Release files for {args.version} already exist. Use --force to overwrite.")
            sys.exit(0)
        
        print(f"Generating release files for {args.version}...")
        md_file, json_file = generate_minimal_release_files(args.version, args.repo_url)
        print(f"✓ Generated {md_file}")
        print(f"✓ Generated {json_file}")
    else:
        # Backfill all missing versions
        missing_tags = [tag for tag in all_tags if tag not in existing_versions]
        
        if not missing_tags:
            print("All versions have release files.")
            return
        
        print(f"Found {len(missing_tags)} missing release files:")
        for tag in missing_tags:
            print(f"  {tag}")
        print()
        
        for tag in missing_tags:
            print(f"Generating release files for {tag}...")
            try:
                md_file, json_file = generate_minimal_release_files(tag, args.repo_url)
                print(f"✓ Generated {md_file}")
                print(f"✓ Generated {json_file}")
            except Exception as e:
                print(f"✗ Error generating {tag}: {e}", file=sys.stderr)
        
        print(f"\n✓ Backfilled {len(missing_tags)} release files")


if __name__ == "__main__":
    main()

