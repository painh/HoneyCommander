"""Check for new releases on GitHub."""

import json
import urllib.request
import urllib.error
from typing import Optional
from dataclasses import dataclass

from commander import __version__

GITHUB_REPO = "painh/HoneyCommander"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


@dataclass
class ReleaseInfo:
    """Information about a GitHub release."""

    tag_name: str
    version: str
    html_url: str
    download_url: Optional[str]
    body: str


def parse_version(tag: str) -> str:
    """Extract version from tag (e.g., 'v0.0.1' -> '0.0.1')."""
    return tag.lstrip("v")


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two version strings.

    Returns:
        1 if v1 > v2, -1 if v1 < v2, 0 if equal
    """

    def normalize(v: str) -> list[int]:
        return [int(x) for x in v.split(".")]

    parts1 = normalize(v1)
    parts2 = normalize(v2)

    # Pad with zeros to make same length
    max_len = max(len(parts1), len(parts2))
    parts1.extend([0] * (max_len - len(parts1)))
    parts2.extend([0] * (max_len - len(parts2)))

    for p1, p2 in zip(parts1, parts2):
        if p1 > p2:
            return 1
        elif p1 < p2:
            return -1
    return 0


def check_for_updates() -> Optional[ReleaseInfo]:
    """
    Check GitHub for new releases.

    Returns ReleaseInfo if a newer version is available, None otherwise.
    """
    try:
        request = urllib.request.Request(
            RELEASES_API,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"HoneyCommander/{__version__}",
            },
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        tag_name = data.get("tag_name", "")
        remote_version = parse_version(tag_name)

        # Compare versions
        if compare_versions(remote_version, __version__) > 0:
            # Find download URL for current platform
            download_url = None
            import sys

            if sys.platform == "darwin":
                asset_name = "HoneyCommander-macOS.zip"
            elif sys.platform == "win32":
                asset_name = "HoneyCommander-Windows.zip"
            else:
                asset_name = None

            if asset_name:
                for asset in data.get("assets", []):
                    if asset.get("name") == asset_name:
                        download_url = asset.get("browser_download_url")
                        break

            return ReleaseInfo(
                tag_name=tag_name,
                version=remote_version,
                html_url=data.get("html_url", ""),
                download_url=download_url,
                body=data.get("body", ""),
            )

        return None

    except (urllib.error.URLError, json.JSONDecodeError, KeyError, Exception):
        # Silently fail - don't interrupt user if update check fails
        return None


def check_for_updates_async(callback):
    """
    Check for updates in a background thread.

    Args:
        callback: Function to call with ReleaseInfo or None
    """
    from PySide6.QtCore import QThread, Signal, QObject
    from typing import Any

    class UpdateWorker(QObject):
        finished = Signal(object)

        def run(self):
            result = check_for_updates()
            self.finished.emit(result)

    class UpdateThread(QThread):
        worker_ref: Any  # Store worker to prevent GC

        def __init__(self, worker: UpdateWorker):
            super().__init__()
            self.worker_ref = worker

        def run(self):
            self.worker_ref.run()

    worker = UpdateWorker()
    thread = UpdateThread(worker)
    worker.finished.connect(callback)
    worker.finished.connect(thread.quit)

    thread.start()
    return thread
