"""3D model viewer widget for preview panel.

Uses PyVista and PyVistaQt for rendering 3D models.
"""

from pathlib import Path
import logging

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QApplication
from PySide6.QtCore import Qt, QThread, Signal

logger = logging.getLogger(__name__)

# Check if pyvistaqt is available
_PYVISTAQT_AVAILABLE = False
_QtInteractor = None

try:
    from pyvistaqt import QtInteractor
    import pyvista as pv

    # Allow empty meshes (e.g., animation-only files)
    pv.global_theme.allow_empty_mesh = True

    _PYVISTAQT_AVAILABLE = True
    _QtInteractor = QtInteractor
except ImportError:
    pv = None


class MeshLoaderThread(QThread):
    """Background thread for loading 3D meshes."""

    finished = Signal(object, str)  # mesh, error_message

    def __init__(self, path: Path):
        super().__init__()
        self._path = path

    def run(self):
        try:
            from commander.core.model3d_loader import load_mesh

            mesh = load_mesh(self._path)
            self.finished.emit(mesh, "")
        except Exception as e:
            logger.error(f"Error loading 3D model {self._path}: {e}")
            self.finished.emit(None, str(e))


class Model3DViewer(QWidget):
    """3D model viewer widget using PyVista.

    Controls:
        - Left mouse drag: Rotate
        - Middle mouse drag / Shift+Left: Pan
        - Mouse wheel: Zoom
        - 'r' key: Reset camera
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plotter = None
        self._current_path: Path | None = None
        self._loader_thread: MeshLoaderThread | None = None
        self._loading_label: QLabel | None = None
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if _PYVISTAQT_AVAILABLE:
            try:
                # Create PyVista Qt interactor
                self._plotter = _QtInteractor(self)
                self._plotter.set_background("#2b2b2b")  # Dark background
                self._plotter.enable_anti_aliasing()

                # Add default lighting
                from pyvista import Light
                headlight = Light(light_type="headlight", intensity=0.5)
                self._plotter.add_light(headlight)

                layout.addWidget(self._plotter.interactor)
            except Exception as e:
                logger.error(f"Failed to create PyVista interactor: {e}")
                self._plotter = None
                self._show_fallback_message(f"Failed to initialize 3D viewer:\n{e}")
        else:
            self._show_install_message()

    def _show_install_message(self):
        """Show install instructions with copyable command."""
        layout = self.layout()

        # Container widget
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.setSpacing(10)

        # Main message
        msg_label = QLabel("3D viewer not available.")
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_label.setStyleSheet("color: #888; font-size: 14px;")
        container_layout.addWidget(msg_label)

        # Python version warning
        import sys
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        if sys.version_info >= (3, 14):
            warn_label = QLabel(f"⚠️ Python {py_version} detected. VTK requires Python 3.11-3.13.")
            warn_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            warn_label.setWordWrap(True)
            warn_label.setStyleSheet("color: #f0ad4e; font-size: 11px; margin-top: 5px;")
            container_layout.addWidget(warn_label)

        # Install with label
        install_label = QLabel("Install with:")
        install_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        install_label.setStyleSheet("color: #888; font-size: 12px; margin-top: 10px;")
        container_layout.addWidget(install_label)

        # Command (selectable)
        install_cmd = "uv add pyvista pyvistaqt trimesh pyassimp --optional viewer-3d"
        cmd_label = QLabel(install_cmd)
        cmd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cmd_label.setWordWrap(True)
        cmd_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        cmd_label.setStyleSheet(
            "color: #ccc; font-family: monospace; font-size: 11px; "
            "background: #333; padding: 8px; border-radius: 4px;"
        )
        container_layout.addWidget(cmd_label)

        # Copy button
        copy_btn = QPushButton("Copy command")
        copy_btn.setFixedWidth(120)
        copy_btn.setStyleSheet(
            "QPushButton { background: #444; color: #ccc; border: 1px solid #555; "
            "padding: 5px 10px; border-radius: 4px; }"
            "QPushButton:hover { background: #555; }"
        )
        copy_btn.clicked.connect(lambda: self._copy_to_clipboard(install_cmd))
        container_layout.addWidget(copy_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        container_layout.addStretch()
        layout.addWidget(container)

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def _show_fallback_message(self, message: str):
        """Show fallback message when viewer is not available."""
        layout = self.layout()
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        label.setStyleSheet("color: #888; padding: 20px;")
        layout.addWidget(label)

    def load_model(self, path: Path) -> bool:
        """Load and display a 3D model asynchronously.

        Args:
            path: Path to the 3D model file

        Returns:
            True if loading started successfully
        """
        if self._plotter is None:
            return False

        self._current_path = path

        # Cancel any existing load
        if self._loader_thread is not None and self._loader_thread.isRunning():
            self._loader_thread.quit()
            self._loader_thread.wait(100)

        # Check format first (quick check)
        from commander.core.model3d_loader import is_supported_format

        if not is_supported_format(path):
            logger.warning(f"Unsupported 3D format: {path.suffix}")
            return False

        # Show loading indicator
        self._plotter.clear()
        self._plotter.add_text(
            "Loading...",
            position="upper_left",
            font_size=12,
            color="gray",
        )

        # Start background loading
        self._loader_thread = MeshLoaderThread(path)
        self._loader_thread.finished.connect(self._on_mesh_loaded)
        self._loader_thread.start()

        return True

    def _on_mesh_loaded(self, mesh, error: str):
        """Handle mesh loaded from background thread."""
        if self._plotter is None:
            return

        self._plotter.clear()

        if error:
            self._plotter.add_text(
                f"Error: {error}",
                position="upper_left",
                font_size=10,
                color="red",
            )
            return

        if mesh is None:
            self._plotter.add_text(
                "Failed to load model",
                position="upper_left",
                font_size=12,
                color="gray",
            )
            return

        # Check if mesh is empty (e.g., animation-only file)
        if mesh.n_points == 0:
            self._plotter.add_text(
                "No geometry data\n(animation-only file?)",
                position="upper_left",
                font_size=12,
                color="gray",
            )
            return

        try:
            # Add the mesh with nice defaults
            self._plotter.add_mesh(
                mesh,
                color="lightgray",
                smooth_shading=True,
                show_edges=False,
            )

            # Reset camera to fit the model
            self._plotter.reset_camera()
        except Exception as e:
            logger.error(f"Error rendering mesh: {e}")
            self._plotter.clear()
            self._plotter.add_text(
                f"Render error: {e}",
                position="upper_left",
                font_size=10,
                color="red",
            )

    def clear(self):
        """Clear the current model."""
        if self._plotter is not None:
            self._plotter.clear()
        self._current_path = None

    def set_wireframe(self, enabled: bool):
        """Toggle wireframe rendering."""
        if self._plotter is None or self._current_path is None:
            return

        # Reload with different style
        self.load_model(self._current_path)
        # Note: Would need to modify add_mesh call for wireframe

    def reset_camera(self):
        """Reset camera to default view."""
        if self._plotter is not None:
            self._plotter.reset_camera()

    def is_available(self) -> bool:
        """Check if 3D viewer is available."""
        return self._plotter is not None

    def closeEvent(self, event):
        """Handle widget close."""
        # Stop loading thread
        if self._loader_thread is not None and self._loader_thread.isRunning():
            self._loader_thread.quit()
            self._loader_thread.wait(100)

        if self._plotter is not None:
            try:
                self._plotter.close()
            except Exception:
                pass
        super().closeEvent(event)


# Import pyvista for light type if available
try:
    import pyvista
except ImportError:
    pyvista = None
