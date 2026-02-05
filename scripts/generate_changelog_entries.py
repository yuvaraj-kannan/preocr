#!/usr/bin/env python3
"""
Generate CHANGELOG.md entries from git commits for missing versions.

This script analyzes git commits between tags and generates CHANGELOG.md
entries following the Keep a Changelog format.

Usage:
    python scripts/generate_changelog_entries.py
    python scripts/generate_changelog_entries.py --version v0.5.0
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


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
            return date_str.split()[0]  # Return YYYY-MM-DD
    except Exception:
        pass
    return datetime.now().strftime('%Y-%m-%d')


def get_commits_between_tags(start_tag: str, end_tag: str) -> list:
    """Get commit messages between two tags."""
    try:
        result = subprocess.run(
            ['git', 'log', '--format=%s', f'{start_tag}..{end_tag}'],
            capture_output=True,
            text=True,
            check=True
        )
        commits = [c.strip() for c in result.stdout.strip().split('\n') if c.strip()]
        # Filter out version bump commits
        commits = [c for c in commits if not re.match(r'^(chore|bump).*version', c, re.I)]
        return commits
    except Exception:
        return []


def categorize_commit(commit: str) -> str:
    """Categorize commit into Added/Changed/Fixed/etc."""
    commit_lower = commit.lower()
    
    if commit_lower.startswith('feat'):
        return 'Added'
    elif commit_lower.startswith('fix'):
        return 'Fixed'
    elif commit_lower.startswith('refactor'):
        return 'Changed'
    elif commit_lower.startswith('chore'):
        # Skip chore commits unless they're significant
        if 'ci' in commit_lower or 'cd' in commit_lower or 'workflow' in commit_lower:
            return 'Changed'
        return None
    elif commit_lower.startswith('docs'):
        return None  # Skip documentation-only commits
    elif commit_lower.startswith('test'):
        return None  # Skip test-only commits
    else:
        return 'Changed'


def generate_changelog_entry(version: str, start_tag: str, end_tag: str) -> str:
    """Generate a CHANGELOG.md entry for a version."""
    date = get_tag_date(end_tag)
    commits = get_commits_between_tags(start_tag, end_tag)
    
    # Categorize commits
    categorized = {
        'Added': [],
        'Changed': [],
        'Fixed': [],
        'Removed': [],
        'Security': []
    }
    
    for commit in commits:
        category = categorize_commit(commit)
        if category and category in categorized:
            # Clean up commit message
            msg = commit
            # Remove conventional commit prefix
            msg = re.sub(r'^(feat|fix|refactor|chore|docs|test)[:!]\s*', '', msg, flags=re.I)
            # Capitalize first letter
            if msg:
                msg = msg[0].upper() + msg[1:] if len(msg) > 1 else msg.upper()
            categorized[category].append(msg)
    
    # Build changelog entry
    lines = [f"## [{version}] - {date}", ""]
    
    # Add sections that have content
    for section in ['Added', 'Changed', 'Fixed', 'Removed', 'Security']:
        if categorized[section]:
            lines.append(f"### {section}")
            lines.append("")
            for item in categorized[section]:
                lines.append(f"- {item}")
            lines.append("")
    
    return '\n'.join(lines)


def get_all_tags() -> list:
    """Get all version tags."""
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
    except Exception:
        return []


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate CHANGELOG.md entries from git commits"
    )
    parser.add_argument(
        '--version',
        help='Specific version to generate entry for (e.g., v0.5.0)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Generate entries for all missing versions'
    )
    
    args = parser.parse_args()
    
    tags = get_all_tags()
    
    if args.version:
        # Generate for specific version
        if args.version not in tags:
            print(f"Error: Tag {args.version} not found", file=sys.stderr)
            sys.exit(1)
        
        version_index = tags.index(args.version)
        if version_index == 0:
            print(f"Error: {args.version} is the first tag, cannot determine previous tag", file=sys.stderr)
            sys.exit(1)
        
        prev_tag = tags[version_index - 1]
        version = args.version.lstrip('v')
        entry = generate_changelog_entry(version, prev_tag, args.version)
        print(entry)
    elif args.all:
        # Generate for all missing versions (0.5.0 onwards)
        print("# Generated CHANGELOG Entries\n")
        print("# Add these entries to CHANGELOG.md after the [Unreleased] section\n")
        
        for i in range(1, len(tags)):
            tag = tags[i]
            version = tag.lstrip('v')
            
            # Only generate for versions 0.5.0 and above
            version_parts = version.split('.')
            if len(version_parts) >= 2:
                major, minor = int(version_parts[0]), int(version_parts[1])
                if major == 0 and minor < 5:
                    continue
            
            prev_tag = tags[i - 1]
            entry = generate_changelog_entry(version, prev_tag, tag)
            print(entry)
            print("---")
            print()
    else:
        print("Usage:")
        print("  python scripts/generate_changelog_entries.py --version v0.5.0")
        print("  python scripts/generate_changelog_entries.py --all")
        sys.exit(1)


if __name__ == "__main__":
    main()

