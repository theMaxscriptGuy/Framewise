from __future__ import annotations

from typing import List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from .review import MarkupShape


class MarkupView(QtWidgets.QGraphicsView):
    markups_changed = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setMouseTracking(True)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        self._mode = "pen"
        self._color = QtGui.QColor("#ff0000")
        self._width = 2
        self._background_item: Optional[QtWidgets.QGraphicsPixmapItem] = None
        self._current_path_item: Optional[QtWidgets.QGraphicsPathItem] = None
        self._current_rect_item: Optional[QtWidgets.QGraphicsRectItem] = None
        self._start_pos: Optional[QtCore.QPointF] = None
        self._pen_started = False

    def set_frame(self, pixmap: QtGui.QPixmap) -> None:
        scene = self.scene()
        if scene is None:
            return
        scene.clear()
        self._background_item = scene.addPixmap(pixmap)
        self._background_item.setZValue(0)
        scene.setSceneRect(QtCore.QRectF(pixmap.rect()))
        self.fitInView(scene.sceneRect(), QtCore.Qt.KeepAspectRatio)

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def set_color(self, color: QtGui.QColor) -> None:
        self._color = color

    def set_width(self, width: int) -> None:
        self._width = max(1, int(width))

    def clear_markups(self) -> None:
        scene = self.scene()
        if scene is None:
            return
        for item in scene.items():
            if item is self._background_item:
                continue
            scene.removeItem(item)
        self.markups_changed.emit()

    def load_markups(self, markups: List[MarkupShape]) -> None:
        scene = self.scene()
        if scene is None:
            return
        for item in scene.items():
            if item is self._background_item:
                continue
            scene.removeItem(item)
        for markup in markups:
            if markup.shape == "rect" and len(markup.points) >= 2:
                start = QtCore.QPointF(*markup.points[0])
                end = QtCore.QPointF(*markup.points[1])
                rect = QtCore.QRectF(start, end).normalized()
                item = scene.addRect(rect, QtGui.QPen(QtGui.QColor(markup.color), markup.width))
                item.setZValue(1)
                item.setData(0, markup)
            else:
                path = QtGui.QPainterPath()
                for i, point in enumerate(markup.points):
                    qpoint = QtCore.QPointF(*point)
                    if i == 0:
                        path.moveTo(qpoint)
                    else:
                        path.lineTo(qpoint)
                item = scene.addPath(path, QtGui.QPen(QtGui.QColor(markup.color), markup.width))
                item.setZValue(1)
                item.setData(0, markup)
        self.markups_changed.emit()

    def export_markups(self) -> List[MarkupShape]:
        scene = self.scene()
        if scene is None:
            return []
        markups: List[MarkupShape] = []
        for item in scene.items():
            if item is self._background_item:
                continue
            stored = item.data(0)
            if isinstance(stored, MarkupShape):
                markups.append(stored)
                continue
            if isinstance(item, QtWidgets.QGraphicsRectItem):
                rect = item.rect()
                markup = MarkupShape(
                    shape="rect",
                    points=[[rect.left(), rect.top()], [rect.right(), rect.bottom()]],
                    color=item.pen().color().name(),
                    width=int(item.pen().widthF()),
                )
                markups.append(markup)
            elif isinstance(item, QtWidgets.QGraphicsPathItem):
                path = item.path()
                points = []
                for i in range(int(path.elementCount())):
                    element = path.elementAt(i)
                    points.append([element.x, element.y])
                markup = MarkupShape(
                    shape="pen",
                    points=points,
                    color=item.pen().color().name(),
                    width=int(item.pen().widthF()),
                )
                markups.append(markup)
        return markups

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.LeftButton or not self._background_item:
            super().mousePressEvent(event)
            return
        scene_pos = self.mapToScene(event.pos())
        self._start_pos = scene_pos
        if self._mode == "rect":
            pen = QtGui.QPen(self._color, self._width)
            self._current_rect_item = self.scene().addRect(QtCore.QRectF(scene_pos, scene_pos), pen)
            self._current_rect_item.setZValue(1)
        else:
            pen = QtGui.QPen(self._color, self._width)
            path = QtGui.QPainterPath()
            self._current_path_item = self.scene().addPath(path, pen)
            self._current_path_item.setZValue(1)
            path = self._current_path_item.path()
            path.moveTo(scene_pos)
            self._current_path_item.setPath(path)
            self._pen_started = True
        event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self._background_item:
            super().mouseMoveEvent(event)
            return
        if self._mode == "rect" and self._current_rect_item and self._start_pos is not None:
            scene_pos = self.mapToScene(event.pos())
            rect = QtCore.QRectF(self._start_pos, scene_pos).normalized()
            self._current_rect_item.setRect(rect)
            event.accept()
            return
        if self._mode == "pen" and self._current_path_item:
            scene_pos = self.mapToScene(event.pos())
            path = self._current_path_item.path()
            if not self._pen_started or path.elementCount() == 0:
                path.moveTo(scene_pos)
                self._pen_started = True
            else:
                path.lineTo(scene_pos)
            self._current_path_item.setPath(path)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() != QtCore.Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return
        if self._mode == "rect" and self._current_rect_item:
            rect = self._current_rect_item.rect()
            markup = MarkupShape(
                shape="rect",
                points=[[rect.left(), rect.top()], [rect.right(), rect.bottom()]],
                color=self._current_rect_item.pen().color().name(),
                width=int(self._current_rect_item.pen().widthF()),
            )
            self._current_rect_item.setData(0, markup)
            self._current_rect_item = None
        elif self._mode == "pen" and self._current_path_item:
            path = self._current_path_item.path()
            if not self._pen_started:
                scene_pos = self.mapToScene(event.pos())
                path.moveTo(scene_pos)
            points = []
            for i in range(int(path.elementCount())):
                element = path.elementAt(i)
                points.append([element.x, element.y])
            markup = MarkupShape(
                shape="pen",
                points=points,
                color=self._current_path_item.pen().color().name(),
                width=int(self._current_path_item.pen().widthF()),
            )
            self._current_path_item.setData(0, markup)
            self._current_path_item = None
            self._pen_started = False
        self._start_pos = None
        self.markups_changed.emit()
        event.accept()
