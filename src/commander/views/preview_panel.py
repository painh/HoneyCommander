"""Preview panel - right panel."""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, QSize, QFileSystemWatcher, QUrl
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QComboBox,
    QStackedWidget,
    QPushButton,
    QSlider,
    QCheckBox,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from commander.core.image_loader import load_pixmap, ALL_IMAGE_FORMATS
from commander.core.model3d_loader import SUPPORTED_3D_FORMATS
from commander.widgets.text_viewer import TextViewer
# from commander.widgets.model3d_viewer import Model3DViewer  # Disabled - causes UI freeze
from commander.utils.i18n import tr


class PreviewPanel(QWidget):
    """Right panel for file preview."""

    SUPPORTED_IMAGES = ALL_IMAGE_FORMATS
    SUPPORTED_VIDEO = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".m4v", ".flv"}
    SUPPORTED_AUDIO = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus"}
    SUPPORTED_3D = SUPPORTED_3D_FORMATS  # glTF, GLB, OBJ, FBX

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path: Path | None = None
        self._smooth_filter: bool = False  # Crispy/sharp by default

        # File watcher for auto-refresh
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)

        # Media player
        self._media_player: QMediaPlayer | None = None
        self._audio_output: QAudioOutput | None = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Filter selector at top (for images)
        self._filter_widget = QWidget()
        filter_layout = QHBoxLayout(self._filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 5)

        filter_label = QLabel(tr("filter") + ":")
        filter_label.setStyleSheet("font-size: 11px;")
        self._filter_combo = QComboBox()
        self._filter_combo.addItem(tr("filter_crispy"), False)  # Sharp/Crispy
        self._filter_combo.addItem(tr("filter_smooth"), True)  # Smooth
        self._filter_combo.setCurrentIndex(0)  # Crispy by default
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        self._filter_combo.setFixedWidth(100)

        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self._filter_combo)
        filter_layout.addStretch()

        layout.addWidget(self._filter_widget)

        # Stacked widget for different preview types
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=3)

        # === Image preview widget ===
        self._image_widget = QWidget()
        image_layout = QVBoxLayout(self._image_widget)
        image_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._scroll_area.setWidget(self._image_label)
        image_layout.addWidget(self._scroll_area)

        self._stack.addWidget(self._image_widget)

        # === Text preview widget ===
        self._text_widget = QWidget()
        text_layout = QVBoxLayout(self._text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self._text_viewer = TextViewer()
        self._text_viewer.content_modified.connect(self._on_text_modified)
        text_layout.addWidget(self._text_viewer)

        # Save button (hidden by default)
        self._save_button = QPushButton(tr("save"))
        self._save_button.clicked.connect(self._save_text_file)
        self._save_button.hide()
        text_layout.addWidget(self._save_button)

        self._stack.addWidget(self._text_widget)

        # === Large file widget ===
        self._large_file_widget = QWidget()
        large_layout = QVBoxLayout(self._large_file_widget)
        large_layout.setContentsMargins(10, 10, 10, 10)

        self._large_file_label = QLabel()
        self._large_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._large_file_label.setWordWrap(True)
        large_layout.addWidget(self._large_file_label)

        self._open_external_button = QPushButton(tr("open_with_external_app"))
        self._open_external_button.clicked.connect(self._open_with_external)
        large_layout.addWidget(self._open_external_button)
        large_layout.addStretch()

        self._stack.addWidget(self._large_file_widget)

        # === Placeholder widget ===
        self._placeholder_widget = QLabel()
        self._placeholder_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(self._placeholder_widget)

        # === Media (video/audio) widget ===
        self._media_widget = QWidget()
        media_layout = QVBoxLayout(self._media_widget)
        media_layout.setContentsMargins(0, 0, 0, 0)

        # Video display widget
        self._video_widget = QVideoWidget()
        self._video_widget.setMinimumHeight(100)
        media_layout.addWidget(self._video_widget, stretch=1)

        # Audio-only placeholder (shown when playing audio)
        self._audio_placeholder = QLabel()
        self._audio_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._audio_placeholder.setStyleSheet("font-size: 48px;")
        self._audio_placeholder.setText("🎵")
        self._audio_placeholder.hide()
        media_layout.addWidget(self._audio_placeholder, stretch=1)

        # Media controls
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(5, 5, 5, 5)
        controls_layout.setSpacing(5)

        # Time slider
        self._time_slider = QSlider(Qt.Orientation.Horizontal)
        self._time_slider.setRange(0, 0)
        self._time_slider.sliderMoved.connect(self._seek_media)
        self._time_slider.sliderPressed.connect(self._slider_pressed)
        self._time_slider.sliderReleased.connect(self._slider_released)
        controls_layout.addWidget(self._time_slider)

        # Buttons row
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)

        self._play_button = QPushButton("▶")
        self._play_button.setFixedWidth(40)
        self._play_button.clicked.connect(self._toggle_play)
        buttons_layout.addWidget(self._play_button)

        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setStyleSheet("font-size: 11px;")
        buttons_layout.addWidget(self._time_label)

        buttons_layout.addStretch()

        # Volume slider
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(70)
        self._volume_slider.setFixedWidth(80)
        self._volume_slider.valueChanged.connect(self._set_volume)
        buttons_layout.addWidget(QLabel("🔊"))
        buttons_layout.addWidget(self._volume_slider)

        # Loop checkbox
        self._loop_checkbox = QCheckBox(tr("loop") if tr("loop") != "loop" else "Loop")
        self._loop_checkbox.setChecked(False)
        buttons_layout.addWidget(self._loop_checkbox)

        controls_layout.addLayout(buttons_layout)
        media_layout.addWidget(controls_widget)

        self._stack.addWidget(self._media_widget)

        # === 3D model preview widget ===
        # Disabled due to PyVista/VTK causing UI freeze
        # self._model3d_widget = Model3DViewer()
        # self._stack.addWidget(self._model3d_widget)

        # Slider dragging state
        self._slider_dragging = False

        # File info
        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._info_label, stretch=1)

        # Show placeholder
        self._show_placeholder()

    def _on_filter_changed(self, index: int):
        """Handle filter selection change."""
        self._smooth_filter = self._filter_combo.currentData()
        # Refresh preview if we have an image
        if self._current_path and self._current_path.suffix.lower() in self.SUPPORTED_IMAGES:
            self._show_image_preview(self._current_path)

    def _show_placeholder(self):
        """Show placeholder when nothing is selected."""
        self._filter_widget.hide()
        self._stop_media()
        self._placeholder_widget.setText(tr("select_file_to_preview"))
        self._stack.setCurrentWidget(self._placeholder_widget)
        self._info_label.clear()

    def show_preview(self, path: Path):
        """Show preview for selected file."""
        # Remove old watch
        if self._current_path and self._watcher.files():
            self._watcher.removePaths(self._watcher.files())

        self._current_path = path

        if not path.exists():
            self._show_placeholder()
            return

        # Watch this file for changes
        if path.is_file():
            self._watcher.addPath(str(path))

        # Show file info
        self._show_file_info(path)

        # Stop any playing media first
        self._stop_media()

        # Determine preview type
        suffix = path.suffix.lower()

        if path.is_file() and suffix in self.SUPPORTED_IMAGES:
            # Image preview
            self._filter_widget.show()
            self._show_image_preview(path)
            self._stack.setCurrentWidget(self._image_widget)

        elif path.is_file() and suffix in self.SUPPORTED_VIDEO:
            # Video preview
            self._filter_widget.hide()
            self._show_media_preview(path, is_video=True)
            self._stack.setCurrentWidget(self._media_widget)

        elif path.is_file() and suffix in self.SUPPORTED_AUDIO:
            # Audio preview
            self._filter_widget.hide()
            self._show_media_preview(path, is_video=False)
            self._stack.setCurrentWidget(self._media_widget)

        elif path.is_file() and suffix in self.SUPPORTED_3D:
            # 3D model preview - disabled due to PyVista/VTK blocking issues
            self._filter_widget.hide()
            self._placeholder_widget.setText(
                f"3D Preview: {path.name}\n\n"
                "(3D preview temporarily disabled)"
            )
            self._stack.setCurrentWidget(self._placeholder_widget)

        elif path.is_file() and TextViewer.is_text_file(path):
            # Text file
            self._filter_widget.hide()

            if TextViewer.is_too_large(path):
                # Too large - show open external button
                size = self._format_size(TextViewer.get_file_size(path))
                self._large_file_label.setText(
                    f"{tr('file_too_large')}\n\n"
                    f"{tr('size')}: {size}\n"
                    f"{tr('max_size')}: {self._format_size(TextViewer.MAX_FILE_SIZE)}"
                )
                self._stack.setCurrentWidget(self._large_file_widget)
            else:
                # Load text file
                self._text_viewer.load_file(path)
                self._save_button.hide()
                self._stack.setCurrentWidget(self._text_widget)

        else:
            # No preview available
            self._filter_widget.hide()
            self._placeholder_widget.setText(tr("no_preview_available"))
            self._stack.setCurrentWidget(self._placeholder_widget)

    def _on_file_changed(self, path: str):
        """Handle file change - refresh preview."""
        changed_path = Path(path)
        if self._current_path and changed_path == self._current_path:
            # Re-add to watcher (Qt removes it after change)
            if changed_path.exists():
                self._watcher.addPath(str(changed_path))
                self._show_image_preview(changed_path)
                self._show_file_info(changed_path)

    def _show_image_preview(self, path: Path):
        """Show image preview."""
        try:
            pixmap = load_pixmap(path)
            if not pixmap.isNull():
                # Scale to fit while maintaining aspect ratio
                transform_mode = (
                    Qt.TransformationMode.SmoothTransformation
                    if self._smooth_filter
                    else Qt.TransformationMode.FastTransformation
                )
                scaled = pixmap.scaled(
                    self._scroll_area.size() - QSize(20, 20),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    transform_mode,
                )
                self._image_label.setPixmap(scaled)
            else:
                self._image_label.setText(tr("cannot_load_image"))
        except Exception as e:
            self._image_label.setText(f"Error: {e}")

    def _show_file_info(self, path: Path):
        """Show file information."""
        try:
            stat = path.stat()
            size = self._format_size(stat.st_size)
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

            info_parts = [
                f"<b>{path.name}</b>",
                f"Size: {size}",
                f"Modified: {modified}",
            ]

            if path.is_file():
                info_parts.insert(1, f"Type: {path.suffix or 'File'}")

            self._info_label.setText("<br>".join(info_parts))
        except OSError as e:
            self._info_label.setText(f"Error: {e}")

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def resizeEvent(self, event):
        """Handle resize - rescale image."""
        super().resizeEvent(event)
        if self._current_path and self._current_path.suffix.lower() in self.SUPPORTED_IMAGES:
            self._show_image_preview(self._current_path)

    def _on_text_modified(self, is_modified: bool):
        """Handle text modification."""
        if is_modified:
            self._save_button.show()
        else:
            self._save_button.hide()

    def _save_text_file(self):
        """Save the text file."""
        if self._text_viewer.save_file():
            self._save_button.hide()

    def _open_with_external(self):
        """Open file with external application."""
        if not self._current_path:
            return

        if sys.platform == "darwin":
            subprocess.run(["open", str(self._current_path)])
        elif sys.platform == "win32":
            import os

            os.startfile(str(self._current_path))
        else:
            subprocess.run(["xdg-open", str(self._current_path)])

    # === Media player methods ===

    def _init_media_player(self):
        """Initialize media player if not already done."""
        if self._media_player is None:
            self._media_player = QMediaPlayer()
            self._audio_output = QAudioOutput()
            self._media_player.setAudioOutput(self._audio_output)
            self._media_player.setVideoOutput(self._video_widget)

            # Connect signals
            self._media_player.positionChanged.connect(self._on_position_changed)
            self._media_player.durationChanged.connect(self._on_duration_changed)
            self._media_player.playbackStateChanged.connect(self._on_playback_state_changed)
            self._media_player.mediaStatusChanged.connect(self._on_media_status_changed)

            # Set initial volume
            self._audio_output.setVolume(self._volume_slider.value() / 100)

    def _show_media_preview(self, path: Path, is_video: bool):
        """Show media (video/audio) preview."""
        self._init_media_player()

        # Show/hide video widget based on media type
        if is_video:
            self._video_widget.show()
            self._audio_placeholder.hide()
        else:
            self._video_widget.hide()
            self._audio_placeholder.show()

        # Load media (don't auto-play - user clicks play button)
        self._media_player.setSource(QUrl.fromLocalFile(str(path)))
        self._play_button.setText("▶")

    def _stop_media(self):
        """Stop media playback."""
        if self._media_player is not None:
            self._media_player.stop()
            self._media_player.setSource(QUrl())
            self._play_button.setText("▶")
            self._time_slider.setValue(0)
            self._time_label.setText("00:00 / 00:00")

    def _toggle_play(self):
        """Toggle play/pause."""
        if self._media_player is None:
            return

        if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._media_player.pause()
        else:
            self._media_player.play()

    def _seek_media(self, position: int):
        """Seek to position."""
        if self._media_player is not None:
            self._media_player.setPosition(position)

    def _slider_pressed(self):
        """Handle slider press - pause updates."""
        self._slider_dragging = True

    def _slider_released(self):
        """Handle slider release - seek and resume updates."""
        self._slider_dragging = False
        if self._media_player is not None:
            self._media_player.setPosition(self._time_slider.value())

    def _set_volume(self, value: int):
        """Set volume."""
        if self._audio_output is not None:
            self._audio_output.setVolume(value / 100)

    def _on_position_changed(self, position: int):
        """Handle position change."""
        if not self._slider_dragging:
            self._time_slider.setValue(position)
        self._update_time_label(
            position, self._media_player.duration() if self._media_player else 0
        )

    def _on_duration_changed(self, duration: int):
        """Handle duration change."""
        self._time_slider.setRange(0, duration)
        self._update_time_label(0, duration)

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        """Handle playback state change."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._play_button.setText("⏸")
        else:
            self._play_button.setText("▶")

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        """Handle media status change - for loop functionality."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._loop_checkbox.isChecked():
                self._media_player.setPosition(0)
                self._media_player.play()

    def _update_time_label(self, position: int, duration: int):
        """Update time label."""
        pos_str = self._format_time(position)
        dur_str = self._format_time(duration)
        self._time_label.setText(f"{pos_str} / {dur_str}")

    def _format_time(self, ms: int) -> str:
        """Format milliseconds to MM:SS or HH:MM:SS."""
        seconds = ms // 1000
        minutes = seconds // 60
        hours = minutes // 60

        if hours > 0:
            return f"{hours}:{minutes % 60:02d}:{seconds % 60:02d}"
        return f"{minutes:02d}:{seconds % 60:02d}"
