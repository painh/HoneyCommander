"""Progress dialog for file operations."""

import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
)


class FileOperationWorker(QThread):
    """Worker thread for file operations."""

    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal(int)  # count of successful operations
    error = Signal(str)

    def __init__(self, operation: str, sources: list[Path], destination: Path):
        super().__init__()
        self.operation = operation  # "copy", "move", "paste"
        self.sources = sources
        self.destination = destination
        self._cancelled = False
        self._result = 0

    def run(self):
        """Run the file operation."""
        from commander.core.file_operations import FileOperations
        ops = FileOperations()

        def progress_callback(current: int, total: int, filename: str) -> bool:
            self.progress.emit(current, total, filename)
            return self._cancelled

        try:
            if self.operation == "paste":
                self._result = ops.paste(self.destination, progress_callback)
            elif self.operation == "copy":
                self._result = ops.copy(self.sources, self.destination, progress_callback)
            elif self.operation == "move":
                self._result = ops.move(self.sources, self.destination, progress_callback)

            self.finished.emit(self._result)
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        """Cancel the operation."""
        self._cancelled = True


class ProgressDialog(QDialog):
    """Dialog showing file operation progress."""

    def __init__(self, operation: str, sources: list[Path], destination: Path, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.sources = sources
        self.destination = destination
        self._start_time = time.time()
        self._result = 0

        self._setup_ui()
        self._start_operation()

        op_name = {"copy": "Copying", "move": "Moving", "paste": "Pasting"}.get(operation, "Processing")
        self.setWindowTitle(f"{op_name} Files")
        self.setMinimumWidth(400)
        self.setModal(True)

    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)

        # Operation label
        self._operation_label = QLabel("Preparing...")
        layout.addWidget(self._operation_label)

        # Current file
        self._file_label = QLabel("")
        self._file_label.setStyleSheet("color: gray;")
        layout.addWidget(self._file_label)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        layout.addWidget(self._progress_bar)

        # Stats row
        stats_layout = QHBoxLayout()

        self._size_label = QLabel("0 B / 0 B")
        stats_layout.addWidget(self._size_label)

        stats_layout.addStretch()

        self._time_label = QLabel("Time remaining: calculating...")
        stats_layout.addWidget(self._time_label)

        layout.addLayout(stats_layout)

        # Speed
        self._speed_label = QLabel("")
        layout.addWidget(self._speed_label)

        # Cancel button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel)
        button_layout.addWidget(self._cancel_btn)

        layout.addLayout(button_layout)

    def _start_operation(self):
        """Start the file operation in background."""
        self._worker = FileOperationWorker(self.operation, self.sources, self.destination)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int, filename: str):
        """Handle progress update."""
        if total > 0:
            percent = int(current * 100 / total)
            self._progress_bar.setValue(percent)

            # Update labels
            self._file_label.setText(filename)
            self._size_label.setText(f"{self._format_size(current)} / {self._format_size(total)}")

            # Calculate speed and time remaining
            elapsed = time.time() - self._start_time
            if elapsed > 0 and current > 0:
                speed = current / elapsed
                self._speed_label.setText(f"Speed: {self._format_size(int(speed))}/s")

                remaining_bytes = total - current
                if speed > 0:
                    remaining_time = remaining_bytes / speed
                    self._time_label.setText(f"Time remaining: {self._format_time(remaining_time)}")

            op_name = {"copy": "Copying", "move": "Moving", "paste": "Pasting"}.get(
                self.operation, "Processing"
            )
            self._operation_label.setText(f"{op_name}...")

    def _on_finished(self, count: int):
        """Handle operation completion."""
        self._result = count
        self.accept()

    def _on_error(self, error: str):
        """Handle error."""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Error", f"Operation failed: {error}")
        self.reject()

    def _cancel(self):
        """Cancel the operation."""
        self._worker.cancel()
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setText("Cancelling...")

    def get_result(self) -> int:
        """Get the result (number of items processed)."""
        return self._result

    def _format_size(self, size: int) -> str:
        """Format size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _format_time(self, seconds: float) -> str:
        """Format time in human-readable format."""
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            mins = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            return f"{hours}h {mins}m"

    def closeEvent(self, event):
        """Handle close - cancel operation."""
        if self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
        super().closeEvent(event)
