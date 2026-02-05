#!/usr/bin/env python3
"""
Query release information from release files.

Usage:
    python scripts/get_release_info.py v0.7.0
    python scripts/get_release_info.py v0.7.0 --format json
    python scripts/get_release_info.py v0.7.0 --format markdown
"""

import argparse
import json
import sys
from pathlib import Path


def get_release_info(version: str, format_type: str = "json") -> str:
    """Get release information for a given version."""
    # Remove 'v' prefix if present for file lookup
    version_clean = version.lstrip('v')
    tag = f"v{version_clean}"
    
    releases_dir = Path("releases")
    
    if format_type == "json":
        json_file = releases_dir / f"{tag}.json"
        if not json_file.exists():
            raise FileNotFoundError(f"Release file not found: {json_file}")
        
        data = json.loads(json_file.read_text())
        return json.dumps(data, indent=2)
    
    elif format_type == "markdown":
        md_file = releases_dir / f"{tag}.md"
        if not md_file.exists():
            raise FileNotFoundError(f"Release file not found: {md_file}")
        
        return md_file.read_text()
    
    else:
        raise ValueError(f"Invalid format: {format_type}. Use 'json' or 'markdown'.")


def list_all_releases() -> list:
    """List all available releases."""
    releases_dir = Path("releases")
    if not releases_dir.exists():
        return []
    
    releases = []
    for json_file in releases_dir.glob("v*.json"):
        try:
            data = json.loads(json_file.read_text())
            releases.append({
                "version": data.get("version"),
                "tag": data.get("tag"),
                "release_date": data.get("release_date"),
                "status": data.get("status")
            })
        except Exception:
            continue
    
    # Sort by version (newest first)
    releases.sort(key=lambda x: tuple(map(int, x["version"].split("."))), reverse=True)
    return releases


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Query release information from release files"
    )
    parser.add_argument(
        'version',
        nargs='?',
        help='Version to query (e.g., v0.7.0 or 0.7.0). If not provided, lists all releases.'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'markdown'],
        default='json',
        help='Output format (default: json)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available releases'
    )
    
    args = parser.parse_args()
    
    try:
        if args.list or not args.version:
            releases = list_all_releases()
            if not releases:
                print("No releases found.", file=sys.stderr)
                sys.exit(1)
            
            print("Available releases:")
            print()
            for release in releases:
                print(f"  {release['tag']:10} - {release['release_date']:10} - {release['status']}")
        else:
            output = get_release_info(args.version, args.format)
            print(output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

