#!/usr/bin/env python3
"""Build Commander using Nuitka for better performance."""

import subprocess
import sys
from pathlib import Path


def build():
    project_root = Path(__file__).parent.parent
    main_script = project_root / "src" / "commander" / "__main__.py"

    args = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        "--enable-plugin=pyside6",
        # Output settings
        f"--output-dir={project_root / 'dist'}",
        "--output-filename=Commander",
        # Exclude unused Qt modules
        "--nofollow-import-to=PySide6.QtWebEngine*",
        "--nofollow-import-to=PySide6.Qt3D*",
        "--nofollow-import-to=PySide6.QtMultimedia*",
        "--nofollow-import-to=PySide6.QtSql",
        "--nofollow-import-to=PySide6.QtTest",
        "--nofollow-import-to=PySide6.QtQuick*",
        "--nofollow-import-to=PySide6.QtQml*",
        "--nofollow-import-to=PySide6.QtDesigner",
        "--nofollow-import-to=PySide6.QtHelp",
        "--nofollow-import-to=PySide6.QtCharts",
        "--nofollow-import-to=PySide6.QtDataVisualization",
        # Exclude other unused modules
        "--nofollow-import-to=tkinter",
        "--nofollow-import-to=matplotlib",
        "--nofollow-import-to=numpy",
        # Optimization
        "--lto=yes",
        "--remove-output",
        # Add source path
        f"--include-package-data=commander",
    ]

    # Platform-specific options
    if sys.platform == "darwin":
        args.extend([
            "--macos-create-app-bundle",
            "--macos-app-name=Commander",
        ])
    elif sys.platform == "win32":
        args.extend([
            "--windows-disable-console",
        ])

    # Main script
    args.append(str(main_script))

    print("Building Commander with Nuitka...")
    print("This may take several minutes...")
    print(f"Command: {' '.join(args)}")

    result = subprocess.run(args, cwd=project_root)

    if result.returncode == 0:
        print("\nBuild successful!")
        print(f"Output: {project_root / 'dist'}")
    else:
        print("\nBuild failed!")
        sys.exit(1)


if __name__ == "__main__":
    build()
