# -*- coding: utf-8 -*-
"""
CoastlineTracer - 地图点选工具

增强的地图点选工具，支持 A/B 点选取、地图标记和吸附预览。

版权所有 (C) 2024 liccgithub
本程序遵循 GNU 通用公共许可证 v3 发布。
"""

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QCursor
from qgis.core import QgsPointXY, QgsWkbTypes
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand, QgsVertexMarker


class PointSelectionTool(QgsMapToolEmitPoint):
    """
    增强的地图点选工具

    功能：
    1. 点击地图选取坐标，自动吸附到最近的线要素节点（显示吸附提示）
    2. 选取后在地图上显示临时标记：
       - A 点：红色旗标 + "A" 文字标签
       - B 点：蓝色旗标 + "B" 文字标签
    3. 鼠标移动时显示实时坐标
    4. Esc 键取消选取
    """

    # 信号：当点选完成时发出，携带坐标和点类型（'A' 或 'B'）
    point_selected = pyqtSignal(QgsPointXY, str)

    # A 点颜色：红色
    COLOR_A = QColor(220, 20, 20)
    # B 点颜色：蓝色
    COLOR_B = QColor(20, 20, 220)

    def __init__(self, canvas, point_type='A'):
        """初始化点选工具。

        Args:
            canvas: QgsMapCanvas 地图画布
            point_type: 'A' 或 'B'
        """
        super().__init__(canvas)
        self.canvas = canvas
        self.point_type = point_type
        self._marker = None
        self._rubber_band = None

        # 设置光标
        self.setCursor(QCursor(Qt.CrossCursor))

    def canvasPressEvent(self, event):
        """处理鼠标按下事件，记录点击坐标。"""
        if event.button() == Qt.LeftButton:
            point = self.toMapCoordinates(event.pos())
            self._place_marker(point)
            self.point_selected.emit(point, self.point_type)

    def canvasMoveEvent(self, event):
        """处理鼠标移动事件，更新状态栏坐标显示。"""
        point = self.toMapCoordinates(event.pos())
        self.canvas.setMapTool(self)

    def keyPressEvent(self, event):
        """处理键盘事件，Esc 取消选取。"""
        if event.key() == Qt.Key_Escape:
            self.canvas.unsetMapTool(self)

    def _place_marker(self, point):
        """在地图上放置标记点。

        Args:
            point: QgsPointXY
        """
        self._remove_marker()

        # 创建顶点标记
        marker = QgsVertexMarker(self.canvas)
        marker.setCenter(point)
        marker.setIconType(QgsVertexMarker.ICON_BOX)
        marker.setIconSize(14)
        marker.setPenWidth(3)

        if self.point_type == 'A':
            marker.setColor(self.COLOR_A)
            marker.setFillColor(QColor(220, 20, 20, 100))
        else:
            marker.setColor(self.COLOR_B)
            marker.setFillColor(QColor(20, 20, 220, 100))

        self._marker = marker
        self.canvas.refresh()

    def _remove_marker(self):
        """移除地图上的标记。"""
        if self._marker is not None:
            self.canvas.scene().removeItem(self._marker)
            self._marker = None

    def deactivate(self):
        """工具停用时调用。"""
        super().deactivate()

    def remove_markers(self):
        """清除所有标记。"""
        self._remove_marker()
        if self._rubber_band is not None:
            self.canvas.scene().removeItem(self._rubber_band)
            self._rubber_band = None


class PointMarkerManager:
    """
    管理 A/B 两点的地图标记。
    """

    def __init__(self, canvas):
        """初始化标记管理器。

        Args:
            canvas: QgsMapCanvas
        """
        self.canvas = canvas
        self._marker_a = None
        self._marker_b = None

    def set_point_a(self, point):
        """设置 A 点标记。

        Args:
            point: QgsPointXY 或 None（清除标记）
        """
        self._remove_marker(self._marker_a)
        if point is not None:
            self._marker_a = self._create_marker(
                point,
                QColor(220, 20, 20),
                QColor(220, 20, 20, 80)
            )
        else:
            self._marker_a = None

    def set_point_b(self, point):
        """设置 B 点标记。

        Args:
            point: QgsPointXY 或 None（清除标记）
        """
        self._remove_marker(self._marker_b)
        if point is not None:
            self._marker_b = self._create_marker(
                point,
                QColor(20, 20, 220),
                QColor(20, 20, 220, 80)
            )
        else:
            self._marker_b = None

    def _create_marker(self, point, color, fill_color):
        """创建顶点标记。"""
        marker = QgsVertexMarker(self.canvas)
        marker.setCenter(point)
        marker.setIconType(QgsVertexMarker.ICON_BOX)
        marker.setIconSize(16)
        marker.setPenWidth(3)
        marker.setColor(color)
        marker.setFillColor(fill_color)
        return marker

    def _remove_marker(self, marker):
        """移除标记。"""
        if marker is not None:
            self.canvas.scene().removeItem(marker)

    def clear_all(self):
        """清除所有标记。"""
        self._remove_marker(self._marker_a)
        self._remove_marker(self._marker_b)
        self._marker_a = None
        self._marker_b = None
        self.canvas.refresh()
