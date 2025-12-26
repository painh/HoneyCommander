# Commander - Development Guide

## Project Overview
Cross-platform file explorer with image viewer (like HoneyView + Windows Explorer)

## Tech Stack
- Python 3.11+
- PySide6 (Qt6)
- uv (package manager)
- PyInstaller/Nuitka (build)

## Commands
```bash
# Run the app
uv run commander

# Build (after installing pyinstaller)
uv add pyinstaller --optional build
uv run python scripts/build_pyinstaller.py
```

## Git Workflow
1. Commit after each completed task
2. Push only when explicitly requested
3. Update this file when workflow changes

## Versioning
- **Always ask user** how much to bump version (patch/minor/major)
- Don't jump versions too much (e.g., 0.0.1 -> 0.1.0 is too big)
- Version is in `src/commander/__init__.py`
- Tag must match version (e.g., v0.0.2 for __version__ = "0.0.2")

## Project Structure
```
src/commander/
├── core/           # Business logic (file ops, archive handling)
├── views/          # Qt views (main window, file list, etc.)
├── widgets/        # Reusable widgets
└── utils/          # Utilities
```

## Key Features
- 3-panel layout (tree | list | preview)
- File operations (copy/paste/delete/rename)
- Drag & drop support
- Image preview and fullscreen viewer
- ZIP/RAR archive browsing
- Context menu with terminal access
- Hidden files visible by default
