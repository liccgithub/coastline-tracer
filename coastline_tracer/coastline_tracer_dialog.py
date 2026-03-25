# -*- coding: utf-8 -*-
"""
CoastlineTracer - 对话框逻辑类

包含所有 UI 交互逻辑：图层选择、A/B 点设置、图构建、路径追踪、结果显示和导出。

版权所有 (C) 2024 liccgithub
本程序遵循 GNU 通用公共许可证 v3 发布。
"""

import math
import os
import time
from datetime import datetime

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QDialog,
    QApplication,
    QMessageBox,
)
from PyQt5.QtGui import QColor
from PyQt5 import uic

from qgis.core import (
    QgsMapLayerProxyModel,
    QgsPointXY,
    QgsProject,
    QgsWkbTypes,
)
from qgis.gui import QgsMapCanvas

from .graph_builder import GraphBuilder
from .tracer_engine import TracerEngine
from .point_tool import PointSelectionTool, PointMarkerManager
from .result_renderer import ResultRenderer
from .statistics_panel import StatisticsPanel
from .export_manager import ExportManager
from .settings_manager import SettingsManager


# 加载 UI 文件
UI_FILE = os.path.join(os.path.dirname(__file__), 'coastline_tracer_dialog_base.ui')


class WorkerSignals(QObject):
    """工作线程信号。"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    log = pyqtSignal(str)


class GraphBuildWorker(QThread):
    """图构建后台工作线程。"""

    def __init__(self, layers_config, bbox, tolerance):
        super().__init__()
        self.layers_config = layers_config
        self.bbox = bbox
        self.tolerance = tolerance
        self.signals = WorkerSignals()
        self._result = None

    def run(self):
        """在后台线程中构建图。"""
        try:
            def progress_cb(percent, msg):
                self.signals.progress.emit(percent, msg)
                self.signals.log.emit(msg)

            builder = GraphBuilder(progress_callback=progress_cb)
            graph = builder.build_graph(
                self.layers_config,
                bbox=self.bbox,
                tolerance=self.tolerance
            )
            self.signals.finished.emit(graph)
        except Exception as e:
            self.signals.error.emit(f'图构建失败: {str(e)}')


class TraceWorker(QThread):
    """路径追踪后台工作线程。"""

    def __init__(self, graph, start_node, end_node, algorithm):
        super().__init__()
        self.graph = graph
        self.start_node = start_node
        self.end_node = end_node
        self.algorithm = algorithm
        self.signals = WorkerSignals()

    def run(self):
        """在后台线程中执行路径追踪。"""
        try:
            engine = TracerEngine()
            result = engine.trace_path(
                self.graph,
                self.start_node,
                self.end_node,
                algorithm=self.algorithm
            )
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(f'路径追踪失败: {str(e)}')


class CoastlineTracerDialog(QDialog):
    """
    CoastlineTracer 主对话框

    包含所有 UI 交互逻辑：
    - 图层选择与权重配置
    - A/B 点设置（地图点选 / 手动输入 / 粘贴）
    - 图构建与路径追踪
    - 结果统计与导出
    """

    # 算法名称映射
    ALGORITHM_MAP = {
        0: 'bidirectional_dijkstra',
        1: 'astar',
        2: 'dijkstra',
    }

    def __init__(self, iface, parent=None):
        """初始化对话框。

        Args:
            iface: QGIS 接口对象
            parent: 父窗口
        """
        super().__init__(parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()

        # 加载 UI
        uic.loadUi(UI_FILE, self)

        # 内部状态
        self._graph = None
        self._result_layer = None
        self._trace_result = None
        self._point_tool_a = None
        self._point_tool_b = None
        self._marker_manager = PointMarkerManager(self.canvas)
        self._graph_worker = None
        self._trace_worker = None

        # 模块
        self._stats_panel = StatisticsPanel()
        self._export_manager = ExportManager(self)
        self._settings_manager = SettingsManager()
        self._engine = TracerEngine()

        # 坐标
        self._point_a = None  # (lon, lat) 或 None
        self._point_b = None  # (lon, lat) 或 None

        # 初始化 UI
        self._setup_ui()
        self._connect_signals()
        self._load_settings()
        self._auto_detect_layers()

    # ──────────────────────────────────────────────────────────
    # UI 初始化
    # ──────────────────────────────────────────────────────────

    def _setup_ui(self):
        """初始化 UI 控件。"""
        # 图层筛选：只显示线要素图层
        self.cmb_coast.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.cmb_build_coast.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.cmb_land_border.setFilters(QgsMapLayerProxyModel.LineLayer)

        # 允许空选（用户可能只想使用部分图层）
        self.cmb_coast.setAllowEmptyLayer(True)
        self.cmb_build_coast.setAllowEmptyLayer(True)
        self.cmb_land_border.setAllowEmptyLayer(True)

        # 初始进度条
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat('%p%')

        # 结果统计初始显示
        self.txt_statistics.setHtml('<p style="color: gray; padding: 8px;">请先构建网络图并开始追踪</p>')

        # 禁用导出按钮（无结果时）
        self._set_export_enabled(False)

        # 禁用追踪按钮（无图时）
        self.btn_trace.setEnabled(False)

    def _connect_signals(self):
        """连接信号与槽。"""
        # 操作按钮
        self.btn_build_graph.clicked.connect(self._on_build_graph)
        self.btn_trace.clicked.connect(self._on_trace)
        self.btn_clear_result.clicked.connect(self._on_clear_result)
        self.btn_close.clicked.connect(self.close)

        # A/B 点操作
        self.btn_pick_a.clicked.connect(lambda: self._on_pick_point('A'))
        self.btn_pick_b.clicked.connect(lambda: self._on_pick_point('B'))
        self.btn_paste_a.clicked.connect(lambda: self._on_paste_coord('A'))
        self.btn_paste_b.clicked.connect(lambda: self._on_paste_coord('B'))
        self.btn_clear_a.clicked.connect(lambda: self._on_clear_point('A'))
        self.btn_clear_b.clicked.connect(lambda: self._on_clear_point('B'))
        self.btn_swap_ab.clicked.connect(self._on_swap_ab)

        # 坐标输入变化
        self.txt_a_lon.textChanged.connect(self._on_coord_changed)
        self.txt_a_lat.textChanged.connect(self._on_coord_changed)
        self.txt_b_lon.textChanged.connect(self._on_coord_changed)
        self.txt_b_lat.textChanged.connect(self._on_coord_changed)

        # 预设模式
        self.radio_fast.toggled.connect(lambda checked: self._on_preset_changed('fast') if checked else None)
        self.radio_standard.toggled.connect(lambda checked: self._on_preset_changed('standard') if checked else None)
        self.radio_precise.toggled.connect(lambda checked: self._on_preset_changed('precise') if checked else None)

        # 导出按钮
        self.btn_export_shp.clicked.connect(lambda: self._on_export('shp'))
        self.btn_export_geojson.clicked.connect(lambda: self._on_export('geojson'))
        self.btn_export_gpkg.clicked.connect(lambda: self._on_export('gpkg'))
        self.btn_export_kml.clicked.connect(lambda: self._on_export('kml'))
        self.btn_export_csv.clicked.connect(self._on_export_csv)
        self.btn_copy_wkt.clicked.connect(self._on_copy_wkt)

    def _auto_detect_layers(self):
        """自动检测并预选项目中的图层。"""
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            name = layer.name().lower()
            if layer.type() != layer.VectorLayer:
                continue
            if layer.geometryType() != QgsWkbTypes.LineGeometry:
                continue

            if 'coast' in name and 'build' not in name:
                self.cmb_coast.setLayer(layer)
            elif 'build' in name:
                self.cmb_build_coast.setLayer(layer)
            elif 'border' in name or 'land' in name:
                self.cmb_land_border.setLayer(layer)

    # ──────────────────────────────────────────────────────────
    # 设置管理
    # ──────────────────────────────────────────────────────────

    def _load_settings(self):
        """从 QSettings 恢复上次设置。"""
        settings = self._settings_manager.load_settings()

        self.spin_coast_weight.setValue(float(settings.get('coast_weight', 1.0)))
        self.spin_build_weight.setValue(float(settings.get('build_coast_weight', 10.0)))
        self.spin_border_weight.setValue(float(settings.get('land_border_weight', 100.0)))
        self.spin_tolerance.setValue(float(settings.get('tolerance', 50.0)))
        self.spin_buffer_pct.setValue(int(settings.get('buffer_percent', 20)))
        self.chk_spatial_clip.setChecked(bool(settings.get('enable_spatial_clip', True)))

        # 预设模式
        preset = settings.get('preset_mode', 'standard')
        if preset == 'fast':
            self.radio_fast.setChecked(True)
        elif preset == 'precise':
            self.radio_precise.setChecked(True)
        else:
            self.radio_standard.setChecked(True)

        # 算法
        algo = settings.get('algorithm', 'bidirectional_dijkstra')
        algo_map = {
            'bidirectional_dijkstra': 0,
            'astar': 1,
            'dijkstra': 2,
        }
        self.cmb_algorithm.setCurrentIndex(algo_map.get(algo, 0))

        # 上次 A/B 点
        a_lon = settings.get('point_a_lon', '')
        a_lat = settings.get('point_a_lat', '')
        b_lon = settings.get('point_b_lon', '')
        b_lat = settings.get('point_b_lat', '')
        if a_lon and a_lat:
            self.txt_a_lon.setText(str(a_lon))
            self.txt_a_lat.setText(str(a_lat))
        if b_lon and b_lat:
            self.txt_b_lon.setText(str(b_lon))
            self.txt_b_lat.setText(str(b_lat))

    def _save_settings(self):
        """保存当前设置到 QSettings。"""
        self._settings_manager.save_settings({
            'coast_weight': self.spin_coast_weight.value(),
            'build_coast_weight': self.spin_build_weight.value(),
            'land_border_weight': self.spin_border_weight.value(),
            'tolerance': self.spin_tolerance.value(),
            'buffer_percent': self.spin_buffer_pct.value(),
            'enable_spatial_clip': self.chk_spatial_clip.isChecked(),
            'algorithm': self.ALGORITHM_MAP.get(self.cmb_algorithm.currentIndex(), 'bidirectional_dijkstra'),
            'preset_mode': self._get_preset_mode(),
            'point_a_lon': self.txt_a_lon.text(),
            'point_a_lat': self.txt_a_lat.text(),
            'point_b_lon': self.txt_b_lon.text(),
            'point_b_lat': self.txt_b_lat.text(),
        })

    # ──────────────────────────────────────────────────────────
    # 预设模式
    # ──────────────────────────────────────────────────────────

    def _get_preset_mode(self):
        """获取当前预设模式名称。"""
        if self.radio_fast.isChecked():
            return 'fast'
        if self.radio_precise.isChecked():
            return 'precise'
        return 'standard'

    def _on_preset_changed(self, mode):
        """预设模式切换时更新参数。"""
        if mode == 'fast':
            self.spin_tolerance.setValue(100.0)
            self.spin_buffer_pct.setValue(30)
            self._log('已切换到快速模式: 容差=100m, 缓冲30%')
        elif mode == 'standard':
            self.spin_tolerance.setValue(50.0)
            self.spin_buffer_pct.setValue(20)
            self._log('已切换到标准模式: 容差=50m, 缓冲20%')
        elif mode == 'precise':
            self.spin_tolerance.setValue(10.0)
            self.spin_buffer_pct.setValue(10)
            self._log('已切换到精确模式: 容差=10m, 缓冲10%')

    # ──────────────────────────────────────────────────────────
    # 点选操作
    # ──────────────────────────────────────────────────────────

    def _on_pick_point(self, point_type):
        """从地图选取点。"""
        tool = PointSelectionTool(self.canvas, point_type)
        tool.point_selected.connect(self._on_point_selected)
        self.canvas.setMapTool(tool)
        self._log(f'请在地图上点击选取 {point_type} 点（按 Esc 取消）...')

        if point_type == 'A':
            self._point_tool_a = tool
        else:
            self._point_tool_b = tool

    def _on_point_selected(self, point, point_type):
        """处理地图点选结果。"""
        lon = round(point.x(), 6)
        lat = round(point.y(), 6)

        if point_type == 'A':
            self.txt_a_lon.setText(str(lon))
            self.txt_a_lat.setText(str(lat))
            self._marker_manager.set_point_a(point)
            self._log(f'A 点已设置: ({lon}, {lat})')
        else:
            self.txt_b_lon.setText(str(lon))
            self.txt_b_lat.setText(str(lat))
            self._marker_manager.set_point_b(point)
            self._log(f'B 点已设置: ({lon}, {lat})')

        # 恢复默认地图工具
        self.canvas.unsetMapTool(self.canvas.mapTool())

    def _on_paste_coord(self, point_type):
        """从剪贴板粘贴坐标。"""
        text = QApplication.clipboard().text().strip()
        if not text:
            return

        # 尝试解析 "lon,lat" 或 "lon lat" 格式
        parts = text.replace(',', ' ').split()
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                if point_type == 'A':
                    self.txt_a_lon.setText(str(lon))
                    self.txt_a_lat.setText(str(lat))
                else:
                    self.txt_b_lon.setText(str(lon))
                    self.txt_b_lat.setText(str(lat))
                self._log(f'{point_type} 点已从剪贴板粘贴: ({lon}, {lat})')
            except ValueError:
                self._log(f'⚠️ 无法解析剪贴板内容: {text}')

    def _on_clear_point(self, point_type):
        """清除点坐标。"""
        if point_type == 'A':
            self.txt_a_lon.clear()
            self.txt_a_lat.clear()
            self._marker_manager.set_point_a(None)
            self._point_a = None
        else:
            self.txt_b_lon.clear()
            self.txt_b_lat.clear()
            self._marker_manager.set_point_b(None)
            self._point_b = None
        self._update_ab_distance()

    def _on_swap_ab(self):
        """交换 A/B 点。"""
        a_lon = self.txt_a_lon.text()
        a_lat = self.txt_a_lat.text()
        self.txt_a_lon.setText(self.txt_b_lon.text())
        self.txt_a_lat.setText(self.txt_b_lat.text())
        self.txt_b_lon.setText(a_lon)
        self.txt_b_lat.setText(a_lat)
        self._log('已交换 A/B 点')

    def _on_coord_changed(self):
        """坐标输入变化时更新 A/B 点和直线距离。"""
        self._parse_points()
        self._update_ab_distance()

        # 更新地图标记
        if self._point_a:
            self._marker_manager.set_point_a(QgsPointXY(*self._point_a))
        if self._point_b:
            self._marker_manager.set_point_b(QgsPointXY(*self._point_b))

    def _parse_points(self):
        """解析 A/B 点坐标文本。"""
        try:
            lon = float(self.txt_a_lon.text())
            lat = float(self.txt_a_lat.text())
            self._point_a = (lon, lat)
        except (ValueError, AttributeError):
            self._point_a = None

        try:
            lon = float(self.txt_b_lon.text())
            lat = float(self.txt_b_lat.text())
            self._point_b = (lon, lat)
        except (ValueError, AttributeError):
            self._point_b = None

    def _update_ab_distance(self):
        """更新 A-B 直线距离显示。"""
        if self._point_a and self._point_b:
            dist_m = self._haversine_m(
                self._point_a[0], self._point_a[1],
                self._point_b[0], self._point_b[1]
            )
            dist_km = dist_m / 1000.0
            self.lbl_ab_dist.setText(f'📐 A-B 直线距离: {dist_km:,.2f} km')
        else:
            self.lbl_ab_dist.setText('📐 A-B 直线距离: --- km')

    @staticmethod
    def _haversine_m(lon1, lat1, lon2, lat2):
        """Haversine 球面距离（米）。"""
        r = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ──────────────────────────────────────────────────────────
    # 图构建
    # ──────────────────────────────────────────────────────────

    def _on_build_graph(self):
        """构建网络图。"""
        self._save_settings()

        # 收集图层配置
        layers_config = self._get_layers_config()
        if not layers_config:
            QMessageBox.warning(
                self, '⚠️ 警告',
                '请至少选择一个有效的线要素图层！'
            )
            return

        # 检查数据量
        total_features = sum(
            lc['layer'].featureCount()
            for lc in layers_config
        )
        if total_features > 500000:
            reply = QMessageBox.question(
                self,
                '📊 数据量较大',
                f'检测到超过 {total_features:,} 条要素，建议启用空间裁剪或使用快速模式。\n是否继续？',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        # 计算 BBox
        bbox = None
        if self.chk_spatial_clip.isChecked():
            self._parse_points()
            if self._point_a and self._point_b:
                bbox = GraphBuilder.compute_bbox(
                    self._point_a,
                    self._point_b,
                    self.spin_buffer_pct.value()
                )
                self._log(f'空间裁剪范围: {bbox.toString(4)}')
            else:
                self._log('ℹ️ 未设置 A/B 点，空间裁剪已跳过')

        tolerance = self.spin_tolerance.value()

        # 重置图缓存和追踪引擎
        self._graph = None
        self._engine = TracerEngine()
        self.btn_trace.setEnabled(False)

        # 在后台线程构建图
        self._set_ui_busy(True)
        self._update_progress(0, '正在启动图构建...')

        worker = GraphBuildWorker(layers_config, bbox, tolerance)
        worker.signals.progress.connect(self._update_progress)
        worker.signals.log.connect(self._log)
        worker.signals.finished.connect(self._on_graph_built)
        worker.signals.error.connect(self._on_worker_error)
        worker.finished.connect(worker.deleteLater)

        self._graph_worker = worker
        worker.start()

    def _get_layers_config(self):
        """获取有效的图层配置列表。"""
        configs = []

        layer_map = [
            (self.cmb_coast, self.spin_coast_weight, 'coast'),
            (self.cmb_build_coast, self.spin_build_weight, 'build_coast'),
            (self.cmb_land_border, self.spin_border_weight, 'land_border'),
        ]

        for cmb, spin, name in layer_map:
            layer = cmb.currentLayer()
            if layer is None:
                continue
            if layer.featureCount() == 0:
                self._log(f'⚠️ {layer.name()} 不包含任何要素，已跳过')
                continue
            if layer.geometryType() != QgsWkbTypes.LineGeometry:
                self._log(f'❌ {layer.name()} 不是线要素图层，已跳过')
                continue
            configs.append({
                'layer': layer,
                'weight': spin.value(),
                'name': name,
            })

        return configs

    def _on_graph_built(self, graph):
        """图构建完成回调。"""
        self._graph = graph
        self._engine.build_kd_tree(graph)

        node_count = len(graph.get('nodes', {}))
        edge_count = sum(len(v) for v in graph.get('adjacency', {}).values()) // 2

        self._log(f'✅ 图构建完成：{node_count} 个节点，{edge_count} 条边')
        self._update_progress(100, f'图构建完成（{node_count} 节点）')

        self.btn_trace.setEnabled(True)
        self._set_ui_busy(False)

        QMessageBox.information(
            self,
            '✅ 完成',
            f'网络图构建成功！\n节点数: {node_count:,}\n边数: {edge_count:,}'
        )

    # ──────────────────────────────────────────────────────────
    # 路径追踪
    # ──────────────────────────────────────────────────────────

    def _on_trace(self):
        """开始路径追踪。"""
        if self._graph is None:
            QMessageBox.warning(self, '⚠️ 警告', '请先构建网络图！')
            return

        self._parse_points()
        if self._point_a is None or self._point_b is None:
            QMessageBox.warning(self, '⚠️ 警告', '请先设置起点 A 和终点 B！')
            return

        # 查找最近节点
        start_node = self._engine.find_nearest_node(self._point_a, self._graph)
        end_node = self._engine.find_nearest_node(self._point_b, self._graph)

        if start_node is None or end_node is None:
            QMessageBox.critical(self, '❌ 错误', '无法在图中找到对应节点，请检查 A/B 点位置')
            return

        # 记录最近节点信息
        sx, sy = self._graph['nodes'][start_node]
        ex, ey = self._graph['nodes'][end_node]
        self._log(f'起点最近节点: ({sx:.4f}, {sy:.4f})')
        self._log(f'终点最近节点: ({ex:.4f}, {ey:.4f})')

        # 获取算法
        algorithm = self.ALGORITHM_MAP.get(self.cmb_algorithm.currentIndex(), 'bidirectional_dijkstra')
        self._log(f'使用算法: {self.cmb_algorithm.currentText()}')

        # 在后台线程追踪
        self._set_ui_busy(True)
        self._update_progress(0, '正在追踪路径...')

        worker = TraceWorker(self._graph, start_node, end_node, algorithm)
        worker.signals.progress.connect(self._update_progress)
        worker.signals.log.connect(self._log)
        worker.signals.finished.connect(self._on_trace_done)
        worker.signals.error.connect(self._on_worker_error)
        worker.finished.connect(worker.deleteLater)

        self._trace_worker = worker
        worker.start()

    def _on_trace_done(self, result):
        """追踪完成回调。"""
        self._trace_result = result
        self._set_ui_busy(False)

        if not result.success:
            self._update_progress(0, '追踪失败')
            self._log(result.error_message)
            for s in result.suggestions:
                self._log(f'  💡 {s}')

            # 显示错误对话框
            suggestions_text = '\n'.join(f'• {s}' for s in result.suggestions)
            QMessageBox.critical(
                self,
                '❌ 追踪失败',
                f'{result.error_message}\n\n建议：\n{suggestions_text}'
            )
            return

        # 更新进度
        total_km = result.total_length_m / 1000.0
        self._update_progress(100, f'追踪完成！{total_km:.2f} km，{result.segment_count} 段')

        # 统计信息
        stats = StatisticsPanel(result)
        self.txt_statistics.setHtml(stats.generate_html())
        self._log(stats.generate_plain_text())

        # 创建并显示结果图层
        self._show_result_layer(result)

        # 启用导出
        self._set_export_enabled(True)

        # 切换到结果标签页
        self.tabWidget.setCurrentWidget(self.tab_result)

        QMessageBox.information(
            self,
            '✅ 追踪完成',
            f'路径长度: {total_km:,.2f} km\n线段数量: {result.segment_count} 段\n耗时: {result.elapsed_seconds:.2f} 秒'
        )

    def _show_result_layer(self, result):
        """将追踪结果显示到地图。"""
        # 移除旧图层
        if self._result_layer is not None:
            QgsProject.instance().removeMapLayer(self._result_layer)
            self._result_layer = None

        # 创建新图层
        layer = ResultRenderer.create_result_layer(result)
        ResultRenderer.add_to_project(layer)
        self._result_layer = layer

        # 缩放到结果范围
        self.canvas.setExtent(layer.extent())
        self.canvas.refresh()

    # ──────────────────────────────────────────────────────────
    # 清除结果
    # ──────────────────────────────────────────────────────────

    def _on_clear_result(self):
        """清除追踪结果。"""
        if self._result_layer is not None:
            QgsProject.instance().removeMapLayer(self._result_layer)
            self._result_layer = None
        self._trace_result = None
        self.txt_statistics.setHtml('<p style="color: gray; padding: 8px;">已清除</p>')
        self._set_export_enabled(False)
        self._update_progress(0, '就绪')
        self._log('已清除追踪结果')

    # ──────────────────────────────────────────────────────────
    # 导出操作
    # ──────────────────────────────────────────────────────────

    def _on_export(self, format_key):
        """导出为指定格式。"""
        if self._result_layer is None:
            QMessageBox.warning(self, '⚠️ 警告', '请先执行追踪操作！')
            return
        self._export_manager.export(self._result_layer, format_key)

    def _on_export_csv(self):
        """导出为 CSV。"""
        if self._result_layer is None:
            QMessageBox.warning(self, '⚠️ 警告', '请先执行追踪操作！')
            return
        self._export_manager.export_csv(self._result_layer)

    def _on_copy_wkt(self):
        """复制 WKT 到剪贴板。"""
        if self._result_layer is None:
            QMessageBox.warning(self, '⚠️ 警告', '请先执行追踪操作！')
            return
        self._export_manager.copy_to_clipboard(self._result_layer)

    # ──────────────────────────────────────────────────────────
    # 错误处理
    # ──────────────────────────────────────────────────────────

    def _on_worker_error(self, message):
        """处理工作线程错误。"""
        self._set_ui_busy(False)
        self._update_progress(0, '出错')
        self._log(f'❌ {message}')
        QMessageBox.critical(self, '❌ 错误', message)

    # ──────────────────────────────────────────────────────────
    # UI 辅助方法
    # ──────────────────────────────────────────────────────────

    def _set_ui_busy(self, busy):
        """禁用/启用操作按钮。"""
        self.btn_build_graph.setEnabled(not busy)
        self.btn_trace.setEnabled(not busy and self._graph is not None)
        self.btn_clear_result.setEnabled(not busy)
        self.btn_pick_a.setEnabled(not busy)
        self.btn_pick_b.setEnabled(not busy)

    def _set_export_enabled(self, enabled):
        """启用/禁用导出按钮。"""
        for btn in [
            self.btn_export_shp,
            self.btn_export_geojson,
            self.btn_export_gpkg,
            self.btn_export_kml,
            self.btn_export_csv,
            self.btn_copy_wkt,
        ]:
            btn.setEnabled(enabled)

    def _update_progress(self, percent, message):
        """更新进度条。"""
        self.progress_bar.setValue(percent)
        self.lbl_progress_msg.setText(message)
        QApplication.processEvents()

    def _log(self, message):
        """追加日志消息（带时间戳）。"""
        ts = datetime.now().strftime('%H:%M:%S')
        self.txt_log.append(f'[{ts}] {message}')
        # 滚动到底部
        cursor = self.txt_log.textCursor()
        from PyQt5.QtGui import QTextCursor
        cursor.movePosition(QTextCursor.End)
        self.txt_log.setTextCursor(cursor)

    # ──────────────────────────────────────────────────────────
    # 对话框关闭
    # ──────────────────────────────────────────────────────────

    def closeEvent(self, event):
        """对话框关闭时保存设置并清理资源。"""
        self._save_settings()
        self._marker_manager.clear_all()

        # 取消后台工作线程
        if self._graph_worker and self._graph_worker.isRunning():
            self._graph_worker.terminate()
        if self._trace_worker and self._trace_worker.isRunning():
            self._trace_worker.terminate()

        super().closeEvent(event)
