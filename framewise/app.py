from __future__ import annotations

import os
from typing import Optional

import cv2
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

from .markup import MarkupView
from .review import ReviewData, ReviewSaver, ReviewStore
from .video import VideoLoader


class FramewiseApp(QtWidgets.QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setApplicationName("Framewise")
        self._window = MainWindow()

    def run(self) -> int:
        self._window.show()
        return self.exec_()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Framewise")
        self.resize(1200, 800)

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

        tool_layout = QtWidgets.QHBoxLayout()
        tool_layout.addWidget(self._pen_button)
        tool_layout.addWidget(self._rect_button)
        tool_layout.addWidget(QtWidgets.QLabel("Width"))
        tool_layout.addWidget(self._width_spin)
        tool_layout.addWidget(self._color_button)
        tool_layout.addStretch(1)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(self._frame_label)
        right_layout.addWidget(self._time_label)
        right_layout.addLayout(tool_layout)
        right_layout.addWidget(self._clear_button)
        right_layout.addWidget(QtWidgets.QLabel("Comments"))
        right_layout.addWidget(self._comment_edit, 1)

        right_panel = QtWidgets.QWidget()
        right_panel.setLayout(right_layout)
        right_panel.setMinimumWidth(320)

        center_layout = QtWidgets.QHBoxLayout()
        center_layout.addWidget(self._markup_view, 1)
        center_layout.addWidget(right_panel)

        center_widget = QtWidgets.QWidget()
        center_widget.setLayout(center_layout)

        bottom_layout = QtWidgets.QVBoxLayout()
        bottom_layout.addWidget(center_widget, 1)
        bottom_layout.addWidget(self._frame_slider)

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

    def _open_video(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Video", os.getcwd(), "Video Files (*.mp4 *.mov *.avi *.mkv);;All Files (*)"
        )
        if not path:
            return
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
        self._loading_frame = False

    def _on_frame_changed(self, index: int) -> None:
        if self._loading_frame:
            return
        if self._current_frame_index is not None:
            self._commit_current_frame()
        self._load_frame(index)

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

    @staticmethod
    def _frame_to_pixmap(frame: np.ndarray) -> QtGui.QPixmap:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        bytes_per_line = channels * width
        image = QtGui.QImage(rgb.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888)
        return QtGui.QPixmap.fromImage(image)
