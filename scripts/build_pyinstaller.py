#!/usr/bin/env python3
"""Build HoneyCommander using PyInstaller."""

import subprocess
import sys
from pathlib import Path


def build():
    project_root = Path(__file__).parent.parent
    main_script = project_root / "src" / "commander" / "__main__.py"

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(main_script),
        "--name=HoneyCommander",
        "--windowed",
        "--noconfirm",
        # Exclude unnecessary Qt modules to reduce size
        "--exclude-module=PySide6.QtWebEngine",
        "--exclude-module=PySide6.QtWebEngineCore",
        "--exclude-module=PySide6.QtWebEngineWidgets",
        "--exclude-module=PySide6.Qt3DCore",
        "--exclude-module=PySide6.Qt3DRender",
        "--exclude-module=PySide6.Qt3DInput",
        "--exclude-module=PySide6.Qt3DLogic",
        "--exclude-module=PySide6.Qt3DAnimation",
        "--exclude-module=PySide6.Qt3DExtras",
        "--exclude-module=PySide6.QtMultimedia",
        "--exclude-module=PySide6.QtMultimediaWidgets",
        "--exclude-module=PySide6.QtSql",
        "--exclude-module=PySide6.QtTest",
        "--exclude-module=PySide6.QtBluetooth",
        "--exclude-module=PySide6.QtNfc",
        "--exclude-module=PySide6.QtPositioning",
        "--exclude-module=PySide6.QtLocation",
        "--exclude-module=PySide6.QtSensors",
        "--exclude-module=PySide6.QtSerialPort",
        "--exclude-module=PySide6.QtWebSockets",
        "--exclude-module=PySide6.QtWebChannel",
        "--exclude-module=PySide6.QtRemoteObjects",
        "--exclude-module=PySide6.QtQuick",
        "--exclude-module=PySide6.QtQuickWidgets",
        "--exclude-module=PySide6.QtQml",
        "--exclude-module=PySide6.QtDesigner",
        "--exclude-module=PySide6.QtHelp",
        "--exclude-module=PySide6.QtPdf",
        "--exclude-module=PySide6.QtPdfWidgets",
        "--exclude-module=PySide6.QtCharts",
        "--exclude-module=PySide6.QtDataVisualization",
        "--exclude-module=PySide6.QtNetworkAuth",
        "--exclude-module=PySide6.QtScxml",
        "--exclude-module=PySide6.QtStateMachine",
        # Exclude other unused modules
        "--exclude-module=tkinter",
        "--exclude-module=matplotlib",
        "--exclude-module=numpy",
        "--exclude-module=scipy",
        "--exclude-module=pandas",
        # Paths
        f"--distpath={project_root / 'dist'}",
        f"--workpath={project_root / 'build'}",
        f"--specpath={project_root}",
        # Hidden imports
        "--hidden-import=PySide6.QtSvg",
        "--hidden-import=PIL.Image",
        # Collect all submodules
        "--collect-submodules=commander",
        # Add source path
        f"--paths={project_root / 'src'}",
    ]

    # Platform-specific options
    if sys.platform == "darwin":
        args.extend(
            [
                "--osx-bundle-identifier=com.honeycommander.app",
                "--icon=assets/icon.icns",
                "--add-data=assets:assets",
                "--add-data=src/commander/locales:commander/locales",
            ]
        )

    print("Building HoneyCommander...")
    print(f"Command: {' '.join(args)}")

    result = subprocess.run(args, cwd=project_root)

    if result.returncode == 0:
        print("\nBuild successful!")
        print(f"Output: {project_root / 'dist'}")

        # macOS: ad-hoc code signing to avoid "unidentified developer" warning
        if sys.platform == "darwin":
            app_path = project_root / "dist" / "HoneyCommander.app"
            if app_path.exists():
                print("\nSigning app with ad-hoc signature...")
                sign_result = subprocess.run(
                    ["codesign", "--force", "--deep", "--sign", "-", str(app_path)],
                    capture_output=True,
                    text=True,
                )
                if sign_result.returncode == 0:
                    print("App signed successfully!")
                else:
                    print(f"Warning: Signing failed: {sign_result.stderr}")
    else:
        print("\nBuild failed!")
        sys.exit(1)


if __name__ == "__main__":
    build()
