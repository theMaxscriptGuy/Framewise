from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from qt_material import apply_stylesheet

from .markup import MarkupView
from .review import ReviewData, ReviewSaver, ReviewStore
from .video import VideoLoader


class VideoListWidget(QtWidgets.QListWidget):
    files_dropped = QtCore.pyqtSignal(list)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                paths.append(path)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()


class FramewiseApp(QtWidgets.QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setApplicationName("Framewise")
        # qt-material doesn't register icon search paths for PyQt5, so do it here.
        QtCore.QDir.addSearchPath("icon", str(Path.home() / ".qt_material" / "theme"))
        apply_stylesheet(self, theme="dark_teal.xml")
        self._window = MainWindow()

    def run(self) -> int:
        self._window.show()
        return self.exec_()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Framewise")
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        self._video = VideoLoader()
        self._store = ReviewStore()
        self._current_frame_index: Optional[int] = None
        self._loading_frame = False

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        self._markup_view = MarkupView()
        self._frame_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._frame_slider.setEnabled(False)

        self._frame_label = QtWidgets.QLabel("Frame: -")
        self._time_label = QtWidgets.QLabel("Time: -")

        self._comment_edit = QtWidgets.QTextEdit()
        self._comment_edit.setPlaceholderText("Write comments for this frame...")

        self._checkpoint_list = QtWidgets.QListWidget()
        self._checkpoint_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        self._video_list = VideoListWidget()
        self._video_list.setMinimumWidth(220)
        self._video_list.setToolTip("Drag and drop videos here")
        self._video_list.setIconSize(QtCore.QSize(160, 90))

        self._pen_button = QtWidgets.QToolButton()
        self._pen_button.setText("Pen")
        self._pen_button.setCheckable(True)
        self._pen_button.setChecked(True)

        self._rect_button = QtWidgets.QToolButton()
        self._rect_button.setText("Rectangle")
        self._rect_button.setCheckable(True)

        self._clear_button = QtWidgets.QPushButton("Clear Markups")

        self._width_spin = QtWidgets.QSpinBox()
        self._width_spin.setRange(1, 20)
        self._width_spin.setValue(2)

        self._color_button = QtWidgets.QPushButton("Color")
        self._color_button.setAutoDefault(False)

        self._zoom_in_button = QtWidgets.QPushButton("Zoom In")
        self._zoom_out_button = QtWidgets.QPushButton("Zoom Out")
        self._zoom_reset_button = QtWidgets.QPushButton("Reset Zoom")
        self._play_button = QtWidgets.QToolButton()
        self._play_button.setAutoRaise(True)
        self._play_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))

        self._play_timer = QtCore.QTimer(self)
        self._play_timer.setSingleShot(False)
        self._is_playing = False

        right_layout = QtWidgets.QVBoxLayout()

        center_layout = QtWidgets.QHBoxLayout()
        center_layout.addWidget(self._markup_view, 1)

        center_widget = QtWidgets.QWidget()
        center_widget.setLayout(center_layout)

        tools_grid = QtWidgets.QGridLayout()
        tools_grid.addWidget(self._frame_label, 0, 0, 1, 3)
        tools_grid.addWidget(self._time_label, 1, 0, 1, 3)
        tools_grid.addWidget(self._pen_button, 2, 0)
        tools_grid.addWidget(self._rect_button, 2, 1)
        tools_grid.addWidget(self._color_button, 3, 0)
        tools_grid.addWidget(QtWidgets.QLabel("Size"), 3, 1)
        tools_grid.addWidget(self._width_spin, 3, 2)
        tools_grid.addWidget(self._clear_button, 4, 0, 1, 3)
        tools_grid.addWidget(self._zoom_in_button, 5, 0)
        tools_grid.addWidget(self._zoom_out_button, 5, 1)
        tools_grid.addWidget(self._zoom_reset_button, 5, 2)
        tools_grid.addWidget(QtWidgets.QLabel("Comments"), 6, 0, 1, 3)
        tools_grid.addWidget(self._comment_edit, 7, 0, 1, 3)
        tools_grid.addWidget(QtWidgets.QLabel("Checkpoints"), 8, 0, 1, 3)
        tools_grid.addWidget(self._checkpoint_list, 9, 0, 1, 3)

        tools_group = QtWidgets.QGroupBox("Tools")
        tools_group.setLayout(tools_grid)

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(QtWidgets.QLabel("Videos"))
        left_layout.addWidget(self._video_list, 1)
        left_layout.addWidget(tools_group)

        left_panel = QtWidgets.QWidget()
        left_panel.setLayout(left_layout)

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addWidget(left_panel)
        top_layout.addWidget(center_widget, 1)
        top_layout.setStretch(0, 0)
        top_layout.setStretch(1, 1)

        top_widget = QtWidgets.QWidget()
        top_widget.setLayout(top_layout)

        bottom_layout = QtWidgets.QVBoxLayout()
        bottom_layout.addWidget(top_widget, 1)
        timeline_layout = QtWidgets.QHBoxLayout()
        timeline_layout.addWidget(self._play_button)
        timeline_layout.addWidget(self._frame_slider, 1)
        bottom_layout.addLayout(timeline_layout)

        container = QtWidgets.QWidget()
        container.setLayout(bottom_layout)
        self.setCentralWidget(container)

        self._setup_menu()

    def _setup_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        open_action = QtWidgets.QAction("Open Video", self)
        open_action.triggered.connect(self._open_video)
        file_menu.addAction(open_action)

        load_action = QtWidgets.QAction("Load Review", self)
        load_action.triggered.connect(self._load_review)
        file_menu.addAction(load_action)

        save_action = QtWidgets.QAction("Save Review", self)
        save_action.triggered.connect(self._save_review)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QtWidgets.QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _connect_signals(self) -> None:
        self._frame_slider.valueChanged.connect(self._on_frame_changed)
        self._pen_button.clicked.connect(self._select_pen)
        self._rect_button.clicked.connect(self._select_rect)
        self._width_spin.valueChanged.connect(self._change_width)
        self._color_button.clicked.connect(self._change_color)
        self._clear_button.clicked.connect(self._clear_markups)
        self._zoom_in_button.clicked.connect(self._zoom_in)
        self._zoom_out_button.clicked.connect(self._zoom_out)
        self._zoom_reset_button.clicked.connect(self._zoom_reset)
        self._play_button.clicked.connect(self._toggle_playback)
        self._play_timer.timeout.connect(self._playback_tick)
        self._comment_edit.textChanged.connect(self._on_comment_changed)
        self._checkpoint_list.itemActivated.connect(self._on_checkpoint_selected)
        self._video_list.itemDoubleClicked.connect(self._on_video_item_activated)
        self._video_list.files_dropped.connect(self._add_videos)

    def _open_video(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Video", os.getcwd(), "Video Files (*.mp4 *.mov *.avi *.mkv);;All Files (*)"
        )
        if not path:
            return
        self._load_video_path(path)

    def _load_review(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Review", os.getcwd(), "Framewise Review (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            review = ReviewSaver.load(path)
            if not review.video_path:
                raise ValueError("Review file is missing video path")
            info = self._video.load(review.video_path)
            review.fps = info.fps
            review.frame_count = info.frame_count
            self._store.set_review(review)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", str(exc))
            return

        self._frame_slider.setEnabled(True)
        self._frame_slider.setRange(0, max(0, self._video.info.frame_count - 1))
        self._frame_slider.setValue(0)
        self._load_frame(0)
        self._refresh_checkpoints()

    def _load_video_path(self, path: str) -> None:
        try:
            info = self._video.load(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", str(exc))
            return

        review = ReviewData(video_path=info.path, fps=info.fps, frame_count=info.frame_count)
        self._store.set_review(review)
        self._frame_slider.setEnabled(True)
        self._frame_slider.setRange(0, max(0, info.frame_count - 1))
        self._frame_slider.setValue(0)
        self._load_frame(0)
        self._refresh_checkpoints()
        self._stop_playback()

    def _add_videos(self, paths: list[str]) -> None:
        for path in paths:
            if not os.path.isfile(path):
                continue
            item = QtWidgets.QListWidgetItem(os.path.basename(path))
            item.setToolTip(path)
            item.setData(QtCore.Qt.UserRole, path)
            icon = self._make_thumbnail_icon(path)
            if icon is not None:
                item.setIcon(icon)
            self._video_list.addItem(item)

    def _on_video_item_activated(self, item: QtWidgets.QListWidgetItem) -> None:
        path = item.data(QtCore.Qt.UserRole)
        if isinstance(path, str) and path:
            self._load_video_path(path)

    def _make_thumbnail_icon(self, path: str) -> Optional[QtGui.QIcon]:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            cap.release()
            return None
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            return None
        pixmap = self._frame_to_pixmap(frame)
        if pixmap.isNull():
            return None
        target_size = self._video_list.iconSize()
        scaled = pixmap.scaled(target_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        return QtGui.QIcon(scaled)

    def _save_review(self) -> None:
        if not self._store.review:
            QtWidgets.QMessageBox.warning(self, "Warning", "No review to save")
            return
        self._commit_current_frame()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Review", os.getcwd(), "Framewise Review (*.json)"
        )
        if not path:
            return
        if not path.endswith(".json"):
            path = f"{path}.json"
        try:
            ReviewSaver.save(path, self._store.review)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", str(exc))
            return
        QtWidgets.QMessageBox.information(self, "Saved", "Review saved successfully")

    def _commit_current_frame(self) -> None:
        if self._current_frame_index is None or not self._store.review:
            return
        comment = self._comment_edit.toPlainText()
        self._store.update_comment(self._current_frame_index, comment)
        markups = self._markup_view.export_markups()
        self._store.update_markups(self._current_frame_index, markups)
        self._refresh_checkpoints()

    def _load_frame(self, index: int) -> None:
        if not self._video.is_loaded():
            return
        self._loading_frame = True
        try:
            frame, _ = self._video.read_frame(index)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", str(exc))
            self._loading_frame = False
            return

        pixmap = self._frame_to_pixmap(frame)
        self._markup_view.set_frame(pixmap)

        if self._store.review:
            frame_data = self._store.get_frame(index)
        self._comment_edit.setPlainText(frame_data.comment)
        self._markup_view.load_markups(frame_data.markups)

        self._current_frame_index = index
        self._update_labels(index)
        self._select_checkpoint(index)
        self._loading_frame = False

    def _on_frame_changed(self, index: int) -> None:
        if self._loading_frame:
            return
        if self._current_frame_index is not None:
            self._commit_current_frame()
        self._load_frame(index)
        if self._is_playing and self._video.info and index >= self._video.info.frame_count - 1:
            self._stop_playback()

    def _update_labels(self, index: int) -> None:
        self._frame_label.setText(f"Frame: {index}")
        if self._video.info and self._video.info.fps > 0:
            time_seconds = index / self._video.info.fps
            self._time_label.setText(f"Time: {time_seconds:.2f}s")
        else:
            self._time_label.setText("Time: -")

    def _select_pen(self) -> None:
        self._pen_button.setChecked(True)
        self._rect_button.setChecked(False)
        self._markup_view.set_mode("pen")

    def _select_rect(self) -> None:
        self._pen_button.setChecked(False)
        self._rect_button.setChecked(True)
        self._markup_view.set_mode("rect")

    def _change_width(self, value: int) -> None:
        self._markup_view.set_width(value)

    def _change_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(parent=self)
        if color.isValid():
            self._markup_view.set_color(color)

    def _clear_markups(self) -> None:
        self._markup_view.clear_markups()
        if self._current_frame_index is not None:
            self._store.update_markups(self._current_frame_index, [])
            self._refresh_checkpoints()

    def _zoom_in(self) -> None:
        self._markup_view.zoom_in()

    def _zoom_out(self) -> None:
        self._markup_view.zoom_out()

    def _zoom_reset(self) -> None:
        self._markup_view.reset_zoom()

    def _toggle_playback(self) -> None:
        if not self._video.is_loaded():
            return
        if self._is_playing:
            self._stop_playback()
            return
        self._frame_slider.setValue(0)
        self._start_playback()

    def _start_playback(self) -> None:
        if not self._video.info:
            return
        fps = self._video.info.fps if self._video.info.fps > 0 else 30.0
        interval_ms = max(1, int(1000 / fps))
        self._play_timer.start(interval_ms)
        self._is_playing = True
        self._play_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause))

    def _stop_playback(self) -> None:
        self._play_timer.stop()
        self._is_playing = False
        self._play_button.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay))

    def _playback_tick(self) -> None:
        if not self._video.info:
            self._stop_playback()
            return
        next_index = 0 if self._current_frame_index is None else self._current_frame_index + 1
        if next_index >= self._video.info.frame_count:
            self._stop_playback()
            return
        self._frame_slider.setValue(next_index)

    @staticmethod
    def _frame_to_pixmap(frame: np.ndarray) -> QtGui.QPixmap:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        bytes_per_line = channels * width
        image = QtGui.QImage(rgb.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888)
        return QtGui.QPixmap.fromImage(image)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if path:
            self._load_video_path(path)
            event.acceptProposedAction()

    def _refresh_checkpoints(self) -> None:
        if not self._store.review:
            self._checkpoint_list.clear()
            return
        reviewed = self._store.reviewed_frames()
        self._checkpoint_list.blockSignals(True)
        self._checkpoint_list.clear()
        for index in reviewed:
            time_label = "-"
            if self._video.info and self._video.info.fps > 0:
                time_seconds = index / self._video.info.fps
                time_label = f"{time_seconds:.2f}s"
            item = QtWidgets.QListWidgetItem(f"Frame {index} ({time_label})")
            item.setData(QtCore.Qt.UserRole, index)
            self._checkpoint_list.addItem(item)
        self._checkpoint_list.blockSignals(False)

    def _select_checkpoint(self, index: int) -> None:
        for row in range(self._checkpoint_list.count()):
            item = self._checkpoint_list.item(row)
            if item and item.data(QtCore.Qt.UserRole) == index:
                self._checkpoint_list.setCurrentRow(row)
                return
        self._checkpoint_list.clearSelection()

    def _on_checkpoint_selected(self, item: QtWidgets.QListWidgetItem) -> None:
        index = item.data(QtCore.Qt.UserRole)
        if isinstance(index, int):
            self._frame_slider.setValue(index)

    def _on_comment_changed(self) -> None:
        if self._loading_frame or self._current_frame_index is None:
            return
        self._store.update_comment(self._current_frame_index, self._comment_edit.toPlainText())
        self._refresh_checkpoints()
