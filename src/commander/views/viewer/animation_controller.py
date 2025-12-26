"""Animation controller for GIF/WebP playback."""

from pathlib import Path
from io import BytesIO

from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtGui import QPixmap, QMovie

from commander.utils.settings import Settings


class ThumbnailWorker(QObject):
    """Worker to generate frame thumbnails in background."""

    thumbnail_ready = Signal(int, QPixmap)  # frame_index, pixmap
    finished = Signal()

    def __init__(self, path: Path, frame_count: int, thumb_size: int = 70) -> None:
        super().__init__()
        self._path = path
        self._frame_count = frame_count
        self._thumb_size = thumb_size
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        """Generate thumbnails for all frames."""
        try:
            from PIL import Image

            with Image.open(self._path) as img:
                for i in range(self._frame_count):
                    if self._cancelled:
                        break

                    img.seek(i)
                    frame = img.copy()
                    frame.thumbnail((self._thumb_size, self._thumb_size))

                    if frame.mode != "RGBA":
                        frame = frame.convert("RGBA")

                    buffer = BytesIO()
                    frame.save(buffer, format="PNG")
                    buffer.seek(0)

                    pixmap = QPixmap()
                    pixmap.loadFromData(buffer.getvalue())

                    if not self._cancelled:
                        self.thumbnail_ready.emit(i, pixmap)
        except Exception as e:
            print(f"Error generating thumbnails: {e}")
        finally:
            self.finished.emit()


class AnimationController(QObject):
    """Controls animation playback and frame navigation."""

    frame_changed = Signal(int, QPixmap)  # frame_index, pixmap
    animation_started = Signal()
    animation_stopped = Signal()

    ANIMATED_FORMATS = {".gif", ".webp"}

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = Settings()
        self._movie: QMovie | None = None
        self._is_animated = False
        self._frame_count = 0
        self._current_frame = 0
        self._selected_frame = 0
        self._current_path: Path | None = None
        self._thumbnail_thread: QThread | None = None
        self._thumbnail_worker: ThumbnailWorker | None = None
        self._thumb_size = self._settings.load_animation_thumb_size()
        self._frame_thumbnails: list[QPixmap] = []

    @property
    def is_animated(self) -> bool:
        return self._is_animated

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def current_frame(self) -> int:
        return self._current_frame

    @property
    def thumb_size(self) -> int:
        return self._thumb_size

    def load(self, path: Path) -> bool:
        """Load animated image. Returns True if animated."""
        self.stop()

        suffix = path.suffix.lower()
        if suffix not in self.ANIMATED_FORMATS:
            return False

        # Check frame count using PIL
        try:
            from PIL import Image

            with Image.open(path) as img:
                frame_count = getattr(img, "n_frames", 1)
                if frame_count <= 1:
                    return False
        except Exception:
            return False

        self._is_animated = True
        self._frame_count = frame_count
        self._current_path = path
        self._current_frame = 0
        self._selected_frame = 0

        # Use QMovie for playback
        self._movie = QMovie(str(path))
        if not self._movie.isValid():
            self._movie = None
            self._is_animated = False
            return False

        self._movie.frameChanged.connect(self._on_frame_changed)
        return True

    def start(self) -> None:
        """Start animation playback."""
        if self._movie:
            self._movie.start()
            self.animation_started.emit()

    def stop(self) -> None:
        """Stop animation and cleanup."""
        self._stop_thumbnail_generation()
        if self._movie:
            self._movie.stop()
            try:
                self._movie.frameChanged.disconnect(self._on_frame_changed)
            except RuntimeError:
                pass
            self._movie = None
        self._is_animated = False
        self._frame_thumbnails.clear()

    def toggle(self) -> bool:
        """Toggle play/pause. Returns True if now playing."""
        if not self._movie or not self._current_path:
            return False

        if self._movie.state() == QMovie.MovieState.Running:
            self._movie.setPaused(True)
            self._selected_frame = self._current_frame
            return False
        else:
            # Recreate movie and start from selected frame
            self._movie.stop()
            try:
                self._movie.frameChanged.disconnect(self._on_frame_changed)
            except RuntimeError:
                pass

            self._movie = QMovie(str(self._current_path))
            self._movie.frameChanged.connect(self._on_frame_changed)
            self._movie.start()

            for _ in range(self._selected_frame):
                self._movie.jumpToNextFrame()

            return True

    def jump_to_frame(
        self, frame_index: int, zoom_level: float = 1.0, smooth: bool = False
    ) -> QPixmap | None:
        """Jump to specific frame. Returns the frame pixmap."""
        if not self._movie or not self._current_path:
            return None

        was_running = self._movie.state() == QMovie.MovieState.Running
        if was_running:
            self._movie.setPaused(True)

        self._current_frame = frame_index
        self._selected_frame = frame_index

        # Load frame with PIL
        try:
            from PIL import Image

            with Image.open(self._current_path) as img:
                img.seek(frame_index)
                frame = img.copy()

                if frame.mode != "RGBA":
                    frame = frame.convert("RGBA")

                buffer = BytesIO()
                frame.save(buffer, format="PNG")
                buffer.seek(0)

                pixmap = QPixmap()
                pixmap.loadFromData(buffer.getvalue())

                if was_running:
                    self._movie.setPaused(False)

                return pixmap
        except Exception as e:
            print(f"Error loading frame {frame_index}: {e}")
            return None

    def next_frame(self) -> None:
        """Go to next frame."""
        if self._is_animated:
            next_idx = (self._current_frame + 1) % self._frame_count
            self.jump_to_frame(next_idx)

    def prev_frame(self) -> None:
        """Go to previous frame."""
        if self._is_animated:
            prev_idx = (self._current_frame - 1) % self._frame_count
            self.jump_to_frame(prev_idx)

    def get_current_pixmap(self) -> QPixmap | None:
        """Get current frame pixmap from QMovie."""
        if self._movie:
            return self._movie.currentPixmap()
        return None

    def start_thumbnail_generation(
        self,
        on_thumbnail_ready: Signal,
        on_finished: Signal,
    ) -> None:
        """Start generating thumbnails in background."""
        if not self._current_path:
            return

        self._stop_thumbnail_generation()
        self._frame_thumbnails.clear()

        self._thumbnail_thread = QThread()
        self._thumbnail_worker = ThumbnailWorker(
            self._current_path, self._frame_count, self._thumb_size
        )
        self._thumbnail_worker.moveToThread(self._thumbnail_thread)

        self._thumbnail_thread.started.connect(self._thumbnail_worker.run)
        self._thumbnail_worker.thumbnail_ready.connect(on_thumbnail_ready)
        self._thumbnail_worker.finished.connect(on_finished)

        self._thumbnail_thread.start()

    def _stop_thumbnail_generation(self) -> None:
        """Stop background thumbnail generation."""
        if self._thumbnail_worker:
            self._thumbnail_worker.cancel()
        if self._thumbnail_thread and self._thumbnail_thread.isRunning():
            self._thumbnail_thread.quit()
            self._thumbnail_thread.wait(1000)
        self._thumbnail_thread = None
        self._thumbnail_worker = None

    def _on_frame_changed(self, frame_number: int) -> None:
        """Handle QMovie frame change."""
        self._current_frame = frame_number
        if self._movie:
            pixmap = self._movie.currentPixmap()
            if pixmap and not pixmap.isNull():
                self.frame_changed.emit(frame_number, pixmap)
