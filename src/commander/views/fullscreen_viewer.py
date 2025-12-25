"""Fullscreen image viewer."""

import sys
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QApplication, QMenu,
    QMessageBox, QInputDialog, QFileDialog, QScrollArea,
)
from PySide6.QtGui import (
    QPixmap, QKeyEvent, QWheelEvent, QTransform, QCursor,
)

from commander.core.image_loader import load_pixmap


class FullscreenImageViewer(QWidget):
    """Fullscreen image viewer with navigation."""

    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._image_list: list[Path] = []
        self._current_index: int = 0
        self._zoom_level: float = 1.0
        self._original_pixmap: QPixmap | None = None
        self._displayed_pixmap: QPixmap | None = None
        self._rotation: int = 0  # 0, 90, 180, 270
        self._flip_h: bool = False
        self._flip_v: bool = False

        # Panning
        self._pan_start: QPoint | None = None

        # Filter mode
        self._smooth_filter: bool = True

        # Info overlay visibility
        self._info_overlay_visible: bool = False

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
        self.setStyleSheet("background-color: black;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area for large images
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("QScrollArea { border: none; background-color: black; }")

        # Image label inside scroll area
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet("background-color: black;")
        self._scroll_area.setWidget(self._image_label)

        layout.addWidget(self._scroll_area, stretch=1)

        # Info overlay (top-left, hidden by default)
        self._info_overlay = QLabel(self)
        self._info_overlay.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 180); padding: 10px; font-family: monospace;"
        )
        self._info_overlay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._info_overlay.hide()

        # Info label (bottom)
        self._info_label = QLabel()
        self._info_label.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 180); padding: 8px;"
        )
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._info_label)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def show_image(self, path: Path, image_list: list[Path] | None = None):
        """Show image and optionally set image list for navigation."""
        self._image_list = image_list or [path]

        try:
            self._current_index = self._image_list.index(path)
        except ValueError:
            self._image_list = [path]
            self._current_index = 0

        self._reset_transform()
        self._load_current_image()
        self.showFullScreen()

    def _reset_transform(self):
        """Reset all transformations."""
        self._zoom_level = 1.0
        self._rotation = 0
        self._flip_h = False
        self._flip_v = False

    def _load_current_image(self):
        """Load and display current image."""
        if not self._image_list:
            return

        path = self._image_list[self._current_index]
        self._original_pixmap = load_pixmap(path)

        if self._original_pixmap.isNull():
            self._image_label.setText(f"Cannot load: {path.name}")
            return

        # Calculate fit-to-screen scale and set as initial zoom
        self._zoom_level = self._get_fit_scale()
        self._update_display()
        self._update_info()

    def _get_fit_scale(self) -> float:
        """Calculate scale to fit image to screen (show entire image)."""
        if self._original_pixmap is None or self._original_pixmap.isNull():
            return 1.0
        transformed = self._get_transformed_pixmap()
        screen_size = QApplication.primaryScreen().size()
        return min(
            screen_size.width() / transformed.width(),
            screen_size.height() / transformed.height()
        )

    def _get_transformed_pixmap(self) -> QPixmap:
        """Get pixmap with rotation and flip applied."""
        if self._original_pixmap is None:
            return QPixmap()

        transform = QTransform()

        # Apply rotation
        if self._rotation != 0:
            transform.rotate(self._rotation)

        # Apply flip
        if self._flip_h:
            transform.scale(-1, 1)
        if self._flip_v:
            transform.scale(1, -1)

        if transform.isIdentity():
            return self._original_pixmap

        return self._original_pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

    def _update_display(self):
        """Update displayed image with current zoom."""
        if self._original_pixmap is None or self._original_pixmap.isNull():
            return

        # Get transformed pixmap
        transformed = self._get_transformed_pixmap()

        # Apply zoom level to original size
        new_size = QSize(
            int(transformed.width() * self._zoom_level),
            int(transformed.height() * self._zoom_level),
        )
        scaled = transformed.scaled(
            new_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation if self._smooth_filter
            else Qt.TransformationMode.FastTransformation,
        )

        self._displayed_pixmap = scaled
        self._image_label.setPixmap(scaled)
        self._image_label.resize(scaled.size())

    def _update_info(self):
        """Update info label."""
        if not self._image_list:
            return

        path = self._image_list[self._current_index]
        total = len(self._image_list)
        current = self._current_index + 1
        zoom_percent = int(self._zoom_level * 100)

        # File size
        try:
            size = path.stat().st_size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size/1024/1024:.1f} MB"
        except:
            size_str = ""

        # Resolution
        if self._original_pixmap and not self._original_pixmap.isNull():
            res_str = f"{self._original_pixmap.width()}x{self._original_pixmap.height()}"
        else:
            res_str = ""

        self._info_label.setText(
            f"{path.name} | {current}/{total} | {res_str} | {size_str} | {zoom_percent}%"
        )

    def _show_context_menu(self, pos):
        """Show context menu (꿀뷰 style)."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
            QMenu::separator {
                height: 1px;
                background: #555;
                margin: 5px 0;
            }
        """)

        # 열기 (Open)
        open_action = menu.addAction("열기 (F2)")
        open_action.triggered.connect(self._open_file_dialog)

        # 폴더 열기 (Open folder)
        open_folder_action = menu.addAction("폴더 열기 (F)")
        open_folder_action.triggered.connect(self._open_folder)

        # 닫기 (Close)
        close_action = menu.addAction("닫기 (F4)")
        close_action.triggered.connect(self.close)

        menu.addSeparator()

        # 이미지 선택 (Select image)
        select_action = menu.addAction("이미지 선택 (Enter)")
        select_action.triggered.connect(self._select_image)

        # 탐색기 열기 (Open in explorer)
        explorer_action = menu.addAction("탐색기 열기 (Ctrl+Enter)")
        explorer_action.triggered.connect(self._open_in_explorer)

        menu.addSeparator()

        # 필터 설정 submenu
        filter_menu = menu.addMenu("필터 설정")

        no_filter_action = filter_menu.addAction("필터 없음 (U)")
        no_filter_action.setCheckable(True)
        no_filter_action.setChecked(not self._smooth_filter)
        no_filter_action.triggered.connect(lambda: self._set_filter(False))

        smooth_filter_action = filter_menu.addAction("부드럽게+선명하게 (S)")
        smooth_filter_action.setCheckable(True)
        smooth_filter_action.setChecked(self._smooth_filter)
        smooth_filter_action.triggered.connect(lambda: self._set_filter(True))

        menu.addSeparator()

        # 이미지 이동 (Move image)
        move_action = menu.addAction("이미지 이동...")
        move_action.triggered.connect(self._move_image)

        # 영상 처리 submenu
        process_menu = menu.addMenu("영상 처리")

        rotate_cw_action = process_menu.addAction("시계방향 회전 (R)")
        rotate_cw_action.triggered.connect(self._rotate_clockwise)

        rotate_ccw_action = process_menu.addAction("반시계방향 회전 (Shift+R)")
        rotate_ccw_action.triggered.connect(self._rotate_counterclockwise)

        process_menu.addSeparator()

        flip_h_action = process_menu.addAction("좌우 반전 (H)")
        flip_h_action.triggered.connect(self._flip_horizontal)

        flip_v_action = process_menu.addAction("상하 반전 (V)")
        flip_v_action.triggered.connect(self._flip_vertical)

        menu.addSeparator()

        # 보기 모드 submenu
        view_menu = menu.addMenu("보기 모드")

        fit_action = view_menu.addAction("화면에 맞추기 (9)")
        fit_action.triggered.connect(self._zoom_fit)

        original_action = view_menu.addAction("원본 크기 (0, 1)")
        original_action.triggered.connect(self._zoom_original)

        view_menu.addSeparator()

        zoom_in_action = view_menu.addAction("확대 (+)")
        zoom_in_action.triggered.connect(self._zoom_in)

        zoom_out_action = view_menu.addAction("축소 (-)")
        zoom_out_action.triggered.connect(self._zoom_out)

        # 축소/확대 보기
        zoom_action = menu.addAction("축소/확대 보기")
        zoom_action.triggered.connect(self._show_zoom_dialog)

        menu.addSeparator()

        # 폴더 이동
        folder_menu = menu.addMenu("폴더 이동")

        prev_folder_action = folder_menu.addAction("이전 폴더 ([)")
        prev_folder_action.triggered.connect(self._prev_folder)

        next_folder_action = folder_menu.addAction("다음 폴더 (])")
        next_folder_action.triggered.connect(self._next_folder)

        menu.addSeparator()

        # 파일 정보/EXIF 정보 보기
        info_action = menu.addAction("파일 정보/EXIF 정보 보기 (TAB)")
        info_action.triggered.connect(self._toggle_file_info)

        menu.addSeparator()

        # 파일 삭제
        delete_action = menu.addAction("파일 삭제 (Del)")
        delete_action.triggered.connect(self._delete_current)

        # 사진 보관함으로 복사 (macOS)
        if sys.platform == "darwin":
            photos_action = menu.addAction("사진 보관함으로 복사 (Ins)")
            photos_action.triggered.connect(self._copy_to_photos)

        # 편집 프로그램 실행
        edit_action = menu.addAction("편집 프로그램 실행 (Ctrl+E)")
        edit_action.triggered.connect(self._open_in_editor)

        menu.addSeparator()

        # 클립보드로 복사하기
        copy_action = menu.addAction("클립보드로 복사하기 (Ctrl+C)")
        copy_action.triggered.connect(self._copy_to_clipboard)

        menu.addSeparator()

        # 종료
        exit_action = menu.addAction("종료 (X)")
        exit_action.triggered.connect(self.close)

        menu.exec(QCursor.pos())

    # === File Operations ===

    def _open_file_dialog(self):
        """Open file dialog to select image."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "이미지 열기",
            str(self._image_list[self._current_index].parent) if self._image_list else str(Path.home()),
            "Images (*.jpg *.jpeg *.png *.gif *.bmp *.webp *.tiff);;All Files (*)"
        )
        if path:
            new_path = Path(path)
            self._image_list = [new_path]
            self._current_index = 0
            self._reset_transform()
            self._load_current_image()

    def _open_folder(self):
        """Open folder dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "폴더 열기",
            str(self._image_list[self._current_index].parent) if self._image_list else str(Path.home())
        )
        if folder:
            folder_path = Path(folder)
            images = self._get_images_in_folder(folder_path)
            if images:
                self._image_list = images
                self._current_index = 0
                self._reset_transform()
                self._load_current_image()

    def _get_images_in_folder(self, folder: Path) -> list[Path]:
        """Get all images in folder."""
        extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico"}
        images = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in extensions]
        images.sort()
        return images

    def _get_sibling_folders(self) -> list[Path]:
        """Get sibling folders that contain images."""
        if not self._image_list:
            return []

        current_folder = self._image_list[self._current_index].parent
        parent = current_folder.parent

        try:
            folders = sorted([
                f for f in parent.iterdir()
                if f.is_dir() and self._get_images_in_folder(f)
            ])
            return folders
        except (PermissionError, OSError):
            return [current_folder]

    def _prev_folder(self):
        """Go to previous sibling folder."""
        if not self._image_list:
            return

        current_folder = self._image_list[self._current_index].parent
        folders = self._get_sibling_folders()

        if not folders:
            return

        try:
            idx = folders.index(current_folder)
            if idx > 0:
                new_folder = folders[idx - 1]
                images = self._get_images_in_folder(new_folder)
                if images:
                    self._image_list = images
                    self._current_index = 0
                    self._reset_transform()
                    self._load_current_image()
        except ValueError:
            pass

    def _next_folder(self):
        """Go to next sibling folder."""
        if not self._image_list:
            return

        current_folder = self._image_list[self._current_index].parent
        folders = self._get_sibling_folders()

        if not folders:
            return

        try:
            idx = folders.index(current_folder)
            if idx < len(folders) - 1:
                new_folder = folders[idx + 1]
                images = self._get_images_in_folder(new_folder)
                if images:
                    self._image_list = images
                    self._current_index = 0
                    self._reset_transform()
                    self._load_current_image()
        except ValueError:
            pass

    def _select_image(self):
        """Return to explorer with current image selected."""
        self.close()

    def _open_in_explorer(self):
        """Open current image in system file manager."""
        if not self._image_list:
            return
        path = self._image_list[self._current_index]
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["explorer", "/select,", str(path)])
        else:
            subprocess.run(["xdg-open", str(path.parent)])

    def _move_image(self):
        """Move current image to another folder."""
        if not self._image_list:
            return
        path = self._image_list[self._current_index]

        dest = QFileDialog.getExistingDirectory(
            self, "이미지 이동", str(path.parent)
        )
        if dest:
            import shutil
            try:
                new_path = Path(dest) / path.name
                shutil.move(str(path), str(new_path))

                # Remove from list and go to next
                self._image_list.pop(self._current_index)
                if not self._image_list:
                    self.close()
                    return
                if self._current_index >= len(self._image_list):
                    self._current_index = len(self._image_list) - 1
                self._load_current_image()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"이동 실패: {e}")

    def _delete_current(self):
        """Delete current image."""
        if not self._image_list:
            return

        path = self._image_list[self._current_index]
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"'{path.name}'을(를) 휴지통으로 이동하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                import send2trash
                send2trash.send2trash(str(path))

                self._image_list.pop(self._current_index)
                if not self._image_list:
                    self.close()
                    return
                if self._current_index >= len(self._image_list):
                    self._current_index = len(self._image_list) - 1
                self._load_current_image()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"삭제 실패: {e}")

    def _copy_to_photos(self):
        """Copy to Photos app (macOS)."""
        if not self._image_list or sys.platform != "darwin":
            return
        path = self._image_list[self._current_index]
        try:
            subprocess.run(["osascript", "-e",
                f'tell application "Photos" to import POSIX file "{path}"'])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"복사 실패: {e}")

    def _open_in_editor(self):
        """Open in default image editor."""
        if not self._image_list:
            return
        path = self._image_list[self._current_index]
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "Preview", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["mspaint", str(path)])
        else:
            subprocess.run(["gimp", str(path)])

    def _copy_to_clipboard(self):
        """Copy current image to clipboard."""
        if self._original_pixmap and not self._original_pixmap.isNull():
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(self._get_transformed_pixmap())

    # === Transform Operations ===

    def _rotate_clockwise(self):
        """Rotate image 90 degrees clockwise."""
        self._rotation = (self._rotation + 90) % 360
        self._update_display()
        self._update_info()

    def _rotate_counterclockwise(self):
        """Rotate image 90 degrees counter-clockwise."""
        self._rotation = (self._rotation - 90) % 360
        self._update_display()
        self._update_info()

    def _flip_horizontal(self):
        """Flip image horizontally."""
        self._flip_h = not self._flip_h
        self._update_display()

    def _flip_vertical(self):
        """Flip image vertically."""
        self._flip_v = not self._flip_v
        self._update_display()

    def _set_filter(self, smooth: bool):
        """Set filter mode."""
        self._smooth_filter = smooth
        self._update_display()

    # === Zoom & Navigation ===

    def _next_image(self):
        """Go to next image."""
        if self._current_index < len(self._image_list) - 1:
            self._current_index += 1
            self._reset_transform()
            self._load_current_image()

    def _prev_image(self):
        """Go to previous image."""
        if self._current_index > 0:
            self._current_index -= 1
            self._reset_transform()
            self._load_current_image()

    def _zoom_in(self):
        """Zoom in."""
        if self._zoom_level < 10.0:
            self._zoom_level *= 1.25
            self._update_display()
            self._update_info()

    def _zoom_out(self):
        """Zoom out."""
        if self._zoom_level > 0.1:
            self._zoom_level /= 1.25
            self._update_display()
            self._update_info()

    def _zoom_fit(self):
        """Fit image to screen (show entire image, key 9)."""
        self._zoom_level = self._get_fit_scale()
        self._update_display()
        self._update_info()

    def _zoom_original(self):
        """Zoom to original size (100%)."""
        if self._original_pixmap is None:
            return

        self._zoom_level = 1.0
        self._update_display()
        self._update_info()

    def _show_zoom_dialog(self):
        """Show zoom level dialog."""
        current = int(self._zoom_level * 100)
        value, ok = QInputDialog.getInt(
            self, "확대/축소", "확대율 (%):", current, 10, 1000
        )
        if ok:
            self._zoom_level = value / 100.0
            self._update_display()
            self._update_info()

    # === File Info ===

    def _toggle_file_info(self):
        """Toggle file info overlay (꿀뷰 style)."""
        self._info_overlay_visible = not self._info_overlay_visible

        if self._info_overlay_visible:
            self._update_info_overlay()
            self._info_overlay.show()
        else:
            self._info_overlay.hide()

    def _update_info_overlay(self):
        """Update info overlay content."""
        if not self._image_list:
            return

        path = self._image_list[self._current_index]
        lines = []

        # Basic file info
        lines.append(f"파일: {path.name}")
        lines.append(f"경로: {path.parent}")

        try:
            stat = path.stat()
            size = stat.st_size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size/1024/1024:.1f} MB"
            lines.append(f"크기: {size_str}")

            from datetime import datetime
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"수정일: {mtime}")

            if hasattr(stat, 'st_birthtime'):
                ctime = datetime.fromtimestamp(stat.st_birthtime).strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"생성일: {ctime}")
        except:
            pass

        # Image info
        if self._original_pixmap and not self._original_pixmap.isNull():
            lines.append(f"해상도: {self._original_pixmap.width()} x {self._original_pixmap.height()}")
            lines.append(f"비트 깊이: {self._original_pixmap.depth()}")

        # Try to read all EXIF data
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            with Image.open(path) as img:
                lines.append(f"포맷: {img.format}")
                lines.append(f"모드: {img.mode}")

                exif_data = img._getexif()
                if exif_data:
                    lines.append("")
                    lines.append("=== EXIF ===")
                    for tag_id, value in sorted(exif_data.items()):
                        tag = TAGS.get(tag_id, tag_id)
                        # Skip binary/long data
                        if isinstance(value, bytes) or (isinstance(value, str) and len(value) > 100):
                            continue
                        lines.append(f"{tag}: {value}")
        except:
            pass

        self._info_overlay.setText("\n".join(lines))
        self._info_overlay.adjustSize()
        self._info_overlay.move(10, 10)

    # === Event Handlers ===

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard input."""
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_Escape or key == Qt.Key.Key_X:
            self.close()
        elif key == Qt.Key.Key_F4:
            self.close()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Space, Qt.Key.Key_PageDown):
            self._next_image()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Backspace, Qt.Key.Key_PageUp):
            self._prev_image()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self._zoom_in()
        elif key == Qt.Key.Key_Minus:
            self._zoom_out()
        elif key == Qt.Key.Key_0:
            self._zoom_original()  # 100% 원본 크기
        elif key == Qt.Key.Key_9:
            self._zoom_fit()  # 화면에 맞추기
        elif key == Qt.Key.Key_1:
            self._zoom_original()  # 100% 원본 크기
        elif key == Qt.Key.Key_Home:
            self._current_index = 0
            self._reset_transform()
            self._load_current_image()
        elif key == Qt.Key.Key_End:
            self._current_index = len(self._image_list) - 1
            self._reset_transform()
            self._load_current_image()
        elif key == Qt.Key.Key_R:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._rotate_counterclockwise()
            else:
                self._rotate_clockwise()
        elif key == Qt.Key.Key_H:
            self._flip_horizontal()
        elif key == Qt.Key.Key_V:
            self._flip_vertical()
        elif key == Qt.Key.Key_Delete:
            self._delete_current()
        elif key == Qt.Key.Key_Tab:
            self._toggle_file_info()
        elif key == Qt.Key.Key_F2:
            self._open_file_dialog()
        elif key == Qt.Key.Key_F:
            self._open_folder()
        elif key == Qt.Key.Key_U:
            self._set_filter(False)
        elif key == Qt.Key.Key_S:
            self._set_filter(True)
        elif key == Qt.Key.Key_C and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._copy_to_clipboard()
        elif key == Qt.Key.Key_E and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._open_in_editor()
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self._open_in_explorer()
            else:
                self._select_image()
        elif key == Qt.Key.Key_Insert:
            if sys.platform == "darwin":
                self._copy_to_photos()
        elif key == Qt.Key.Key_BracketLeft:
            self._prev_folder()
        elif key == Qt.Key.Key_BracketRight:
            self._next_folder()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for navigation."""
        delta = event.angleDelta().y()
        if delta > 0:
            self._prev_image()  # Wheel up = previous
        elif delta < 0:
            self._next_image()  # Wheel down = next

    def mousePressEvent(self, event):
        """Handle mouse click."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Start panning (for zoomed images)
            self._pan_start = event.pos()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._zoom_fit()

    def mouseMoveEvent(self, event):
        """Handle mouse move for panning."""
        if self._pan_start and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()

            h_bar = self._scroll_area.horizontalScrollBar()
            v_bar = self._scroll_area.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._pan_start = None

    def closeEvent(self, event):
        """Handle close."""
        self.closed.emit()
        super().closeEvent(event)
