#!/usr/bin/env python3
"""
Sync all release files from CHANGELOG.md.

This script generates release files for all versions found in CHANGELOG.md,
backfilling any missing releases.

Usage:
    python scripts/sync_releases.py
    python scripts/sync_releases.py --dry-run
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.generate_release import parse_changelog, generate_release_files, get_github_repo_url


def sync_all_releases(changelog_path: Path, dry_run: bool = False) -> None:
    """Sync all release files from CHANGELOG.md."""
    if not changelog_path.exists():
        print(f"Error: CHANGELOG.md not found at {changelog_path}", file=sys.stderr)
        sys.exit(1)
    
    # Parse changelog to get all versions
    versions = parse_changelog(changelog_path)
    
    if not versions:
        print("No versions found in CHANGELOG.md", file=sys.stderr)
        sys.exit(1)
    
    # Create releases directory
    releases_dir = Path("releases")
    if not dry_run:
        releases_dir.mkdir(exist_ok=True)
    
    # Sort versions (newest first)
    sorted_versions = sorted(versions.keys(), reverse=True)
    
    print(f"Found {len(sorted_versions)} versions in CHANGELOG.md")
    print(f"Syncing to {releases_dir}/")
    print()
    
    generated = []
    skipped = []
    errors = []
    
    for version in sorted_versions:
        # Skip "Unreleased" version
        if version.lower() == "unreleased":
            continue
        
        tag = f"v{version}"
        md_file = releases_dir / f"{tag}.md"
        json_file = releases_dir / f"{tag}.json"
        
        # Check if files already exist
        if md_file.exists() and json_file.exists():
            skipped.append(version)
            if not dry_run:
                print(f"⏭️  {tag}: Already exists, skipping")
            continue
        
        try:
            if dry_run:
                print(f"🔍 {tag}: Would generate")
            else:
                generate_release_files(version, changelog_path)
                generated.append(version)
                print(f"✅ {tag}: Generated")
        except Exception as e:
            errors.append((version, str(e)))
            print(f"❌ {tag}: Error - {e}", file=sys.stderr)
    
    print()
    print("Summary:")
    print(f"  Generated: {len(generated)}")
    print(f"  Skipped: {len(skipped)}")
    print(f"  Errors: {len(errors)}")
    
    if errors:
        print("\nErrors:")
        for version, error in errors:
            print(f"  {version}: {error}")
        sys.exit(1)
    
    if dry_run:
        print("\nDry run complete. Use without --dry-run to generate files.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync all release files from CHANGELOG.md"
    )
    parser.add_argument(
        '--changelog',
        type=Path,
        default=Path("docs/CHANGELOG.md"),
        help='Path to CHANGELOG.md (default: docs/CHANGELOG.md)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be generated without actually creating files'
    )
    
    args = parser.parse_args()
    
    sync_all_releases(args.changelog, args.dry_run)


if __name__ == "__main__":
    main()

