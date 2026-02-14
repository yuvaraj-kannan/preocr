#!/usr/bin/env python3
"""
Generate release files (Markdown + JSON) from CHANGELOG.md entries.

Usage:
    python scripts/generate_release.py [version]
    python scripts/generate_release.py v0.7.0
    python scripts/generate_release.py  # Uses current version from version.py
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from preocr.version import __version__
except ImportError:
    __version__ = None


def get_current_version() -> str:
    """Get current version from version.py."""
    if __version__:
        return __version__
    version_file = Path("preocr/version.py")
    if not version_file.exists():
        raise FileNotFoundError("preocr/version.py not found")
    content = version_file.read_text()
    match = re.search(r'__version__ = ["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError("Could not find __version__ in version.py")
    return match.group(1)


def parse_changelog(changelog_path: Path) -> Dict[str, Dict]:
    """Parse CHANGELOG.md and extract version information."""
    if not changelog_path.exists():
        raise FileNotFoundError(f"CHANGELOG.md not found at {changelog_path}")

    content = changelog_path.read_text()
    versions = {}

    # Pattern to match version headers: ## [0.4.0] - 2024-12-31
    version_pattern = r"^## \[([^\]]+)\](?:\s*-\s*(\d{4}-\d{2}-\d{2}))?"

    # Pattern to match section headers: ### Added, ### Changed, etc.
    section_pattern = r"^### (\w+)"

    current_version = None
    current_date = None
    current_section = None
    current_items = []

    lines = content.split("\n")

    for i, line in enumerate(lines):
        # Check for version header
        version_match = re.match(version_pattern, line)
        if version_match:
            # Save previous version if exists
            if current_version:
                if current_version not in versions:
                    versions[current_version] = {"date": current_date, "changes": {}}
                if current_section and current_items:
                    versions[current_version]["changes"][current_section.lower()] = current_items

            current_version = version_match.group(1)
            current_date = version_match.group(2) if version_match.group(2) else None
            current_section = None
            current_items = []
            continue

        # Check for section header
        section_match = re.match(section_pattern, line)
        if section_match:
            # Save previous section items
            if current_version and current_section and current_items:
                if current_version not in versions:
                    versions[current_version] = {"date": current_date, "changes": {}}
                versions[current_version]["changes"][current_section.lower()] = current_items

            current_section = section_match.group(1)
            current_items = []
            continue

        # Collect list items
        if current_version and line.strip().startswith("-"):
            item = line.strip()[1:].strip()  # Remove '- ' prefix
            if item:
                current_items.append(item)

    # Save last version
    if current_version:
        if current_version not in versions:
            versions[current_version] = {"date": current_date, "changes": {}}
        if current_section and current_items:
            versions[current_version]["changes"][current_section.lower()] = current_items

    return versions


def get_github_repo_url() -> str:
    """Get GitHub repository URL from git config or default."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
        # Convert SSH to HTTPS if needed
        if url.startswith("git@"):
            url = url.replace("git@github.com:", "https://github.com/").replace(".git", "")
        elif url.endswith(".git"):
            url = url[:-4]
        return url
    except Exception:
        # Default fallback
        return "https://github.com/yuvaraj3855/preocr"


def generate_markdown_release(version: str, version_data: Dict, repo_url: str) -> str:
    """Generate Markdown release file."""
    tag = f"v{version}"
    release_date = version_data.get("date") or datetime.now().strftime("%Y-%m-%d")
    changes = version_data.get("changes", {})

    lines = [
        f"# Release {tag}",
        "",
        f"**Release Date**: {release_date}",
        f"**Git Tag**: {tag}",
        "**Status**: Released",
        "",
        "## Changes",
        "",
    ]

    # Standard section order
    section_order = [
        "added",
        "changed",
        "deprecated",
        "removed",
        "fixed",
        "security",
        "performance",
    ]
    section_titles = {
        "added": "Added",
        "changed": "Changed",
        "deprecated": "Deprecated",
        "removed": "Removed",
        "fixed": "Fixed",
        "security": "Security",
        "performance": "Performance",
    }

    # Add sections in order
    for section_key in section_order:
        if section_key in changes:
            lines.append(f"### {section_titles.get(section_key, section_key.title())}")
            lines.append("")
            for item in changes[section_key]:
                lines.append(f"- {item}")
            lines.append("")

    # Add any other sections
    for section_key, items in changes.items():
        if section_key not in section_order:
            lines.append(f"### {section_key.title()}")
            lines.append("")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")

    # Add artifacts section
    lines.extend(
        [
            "## Artifacts",
            "",
            f"- PyPI: https://pypi.org/project/preocr/{version}/",
            f"- GitHub Release: {repo_url}/releases/tag/{tag}",
            "",
        ]
    )

    return "\n".join(lines)


def generate_json_release(version: str, version_data: Dict, repo_url: str) -> Dict:
    """Generate JSON release file."""
    tag = f"v{version}"
    release_date = version_data.get("date") or datetime.now().strftime("%Y-%m-%d")
    changes = version_data.get("changes", {})

    return {
        "version": version,
        "tag": tag,
        "release_date": release_date,
        "status": "released",
        "changes": changes,
        "artifacts": {
            "pypi": f"https://pypi.org/project/preocr/{version}/",
            "github": f"{repo_url}/releases/tag/{tag}",
        },
    }


def generate_release_files(
    version: Optional[str] = None, changelog_path: Optional[Path] = None
) -> Tuple[Path, Path]:
    """Generate release files for a given version."""
    if version is None:
        version = get_current_version()

    # Remove 'v' prefix if present
    version = version.lstrip("v")

    if changelog_path is None:
        changelog_path = Path("docs/CHANGELOG.md")

    # Parse changelog
    versions = parse_changelog(changelog_path)

    if version not in versions:
        raise ValueError(
            f"Version {version} not found in CHANGELOG.md. "
            f"Available versions: {', '.join(sorted(versions.keys(), reverse=True))}"
        )

    version_data = versions[version]
    repo_url = get_github_repo_url()

    # Create releases directory
    releases_dir = Path("releases")
    releases_dir.mkdir(exist_ok=True)

    # Generate files
    tag = f"v{version}"
    md_file = releases_dir / f"{tag}.md"
    json_file = releases_dir / f"{tag}.json"

    # Generate Markdown
    md_content = generate_markdown_release(version, version_data, repo_url)
    md_file.write_text(md_content)

    # Generate JSON
    json_content = generate_json_release(version, version_data, repo_url)
    json_file.write_text(json.dumps(json_content, indent=2) + "\n")

    print(f"✓ Generated {md_file}")
    print(f"✓ Generated {json_file}")

    return md_file, json_file


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate release files from CHANGELOG.md")
    parser.add_argument(
        "version",
        nargs="?",
        help="Version to generate (e.g., v0.7.0 or 0.7.0). Defaults to current version.",
    )
    parser.add_argument(
        "--changelog", type=Path, help="Path to CHANGELOG.md (default: docs/CHANGELOG.md)"
    )

    args = parser.parse_args()

    try:
        generate_release_files(args.version, args.changelog)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
