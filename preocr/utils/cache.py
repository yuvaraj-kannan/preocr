"""Simple file-based caching for PreOCR results."""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .logger import get_logger

logger = get_logger(__name__)

# Default cache directory
_DEFAULT_CACHE_DIR = Path.home() / ".preocr" / "cache"
_CACHE_EXPIRY_SECONDS = 3600  # 1 hour


def get_cache_key(file_path: str) -> str:
    """
    Generate a cache key for a file.

    Uses file path and modification time to ensure cache invalidation
    when file changes.

    Args:
        file_path: Path to the file

    Returns:
        Cache key string
    """
    path = Path(file_path)
    if not path.exists():
        return hashlib.md5(str(file_path).encode()).hexdigest()

    # Include modification time in key
    mtime = path.stat().st_mtime
    key_string = f"{file_path}:{mtime}"
    return hashlib.md5(key_string.encode()).hexdigest()


def get_cache_path(cache_key: str, cache_dir: Optional[Path] = None) -> Path:
    """
    Get cache file path for a cache key.

    Args:
        cache_key: Cache key
        cache_dir: Cache directory (default: ~/.preocr/cache)

    Returns:
        Path to cache file
    """
    if cache_dir is None:
        cache_dir = _DEFAULT_CACHE_DIR

    cache_dir.mkdir(parents=True, exist_ok=True)
    # Restrict cache directory to owner-only access (rwx------)
    try:
        os.chmod(cache_dir, 0o700)
    except OSError:
        pass
    return cache_dir / f"{cache_key}.json"


def get_cached_result(file_path: str, cache_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Get cached result for a file.

    Args:
        file_path: Path to the file
        cache_dir: Cache directory (default: ~/.preocr/cache)

    Returns:
        Cached result dictionary or None if not found/expired
    """
    cache_key = get_cache_key(file_path)
    cache_path = get_cache_path(cache_key, cache_dir)

    if not cache_path.exists():
        return None

    try:
        # Check if cache is expired
        cache_age = time.time() - cache_path.stat().st_mtime
        if cache_age > _CACHE_EXPIRY_SECONDS:
            logger.debug(f"Cache expired for {file_path}")
            cache_path.unlink()
            return None

        # Load cached result
        with open(cache_path, "r") as f:
            result: Dict[str, Any] = json.load(f)

        logger.debug(f"Cache hit for {file_path}")
        return result
    except (IOError, OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to read cache: {e}")
        # Remove corrupted cache file
        try:
            cache_path.unlink()
        except Exception:
            pass
        return None


def cache_result(file_path: str, result: Dict[str, Any], cache_dir: Optional[Path] = None) -> None:
    """
    Cache result for a file.

    Args:
        file_path: Path to the file
        result: Result dictionary to cache
        cache_dir: Cache directory (default: ~/.preocr/cache)
    """
    cache_key = get_cache_key(file_path)
    cache_path = get_cache_path(cache_key, cache_dir)

    try:
        with open(cache_path, "w") as f:
            json.dump(result, f)
        # Restrict cache file to owner read/write only (rw-------)
        try:
            os.chmod(cache_path, 0o600)
        except OSError:
            pass
        logger.debug(f"Cached result for {file_path}")
    except (IOError, OSError) as e:
        logger.warning(f"Failed to write cache: {e}")


def clear_cache(cache_dir: Optional[Path] = None) -> int:
    """
    Clear all cached results.

    Args:
        cache_dir: Cache directory (default: ~/.preocr/cache)

    Returns:
        Number of cache files removed
    """
    if cache_dir is None:
        cache_dir = _DEFAULT_CACHE_DIR

    if not cache_dir.exists():
        return 0

    count = 0
    try:
        for cache_file in cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        logger.info(f"Cleared {count} cache files")
    except Exception as e:
        logger.warning(f"Failed to clear cache: {e}")

    return count
