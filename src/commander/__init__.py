"""Commander - Cross-platform file explorer with image viewer."""

__version__ = "0.0.9"
__build_date__ = ""  # Set by CI during build, or generated at runtime if empty


def get_build_date() -> str:
    """Get build date, generating current time if not set by CI."""
    if __build_date__:
        return __build_date__
    # Development mode - show current time
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
