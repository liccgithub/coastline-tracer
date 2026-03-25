# -*- coding: utf-8 -*-
"""
CoastlineTracer - 导出管理器

支持多种格式导出：SHP、GeoJSON、GeoPackage、KML、CSV。

版权所有 (C) 2024 liccgithub
本程序遵循 GNU 通用公共许可证 v3 发布。
"""

import os

from PyQt5.QtWidgets import QFileDialog, QApplication
from PyQt5.QtCore import QSettings
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsVectorFileWriter,
    QgsProject,
)
from qgis.utils import iface as qgis_iface


class ExportManager:
    """
    支持多种格式导出：
    1. Shapefile (.shp)
    2. GeoJSON (.geojson)
    3. GeoPackage (.gpkg)
    4. KML (.kml)
    5. CSV（坐标序列）
    6. 复制到剪贴板（WKT 格式）

    使用 QgsVectorFileWriter 实现。
    """

    # 格式配置
    FORMAT_CONFIG = {
        'shp': {
            'driver': 'ESRI Shapefile',
            'ext': '.shp',
            'filter': 'Shapefile (*.shp)',
            'label': 'Shapefile',
        },
        'geojson': {
            'driver': 'GeoJSON',
            'ext': '.geojson',
            'filter': 'GeoJSON (*.geojson)',
            'label': 'GeoJSON',
        },
        'gpkg': {
            'driver': 'GPKG',
            'ext': '.gpkg',
            'filter': 'GeoPackage (*.gpkg)',
            'label': 'GeoPackage',
        },
        'kml': {
            'driver': 'KML',
            'ext': '.kml',
            'filter': 'KML (*.kml)',
            'label': 'KML',
        },
    }

    def __init__(self, parent_widget=None):
        """初始化导出管理器。

        Args:
            parent_widget: 父窗口控件（用于对话框）
        """
        self.parent = parent_widget
        self._last_dir = QSettings().value('CoastlineTracer/last_export_dir', '')

    def export(self, layer, format_key):
        """导出图层为指定格式。

        Args:
            layer: QgsVectorLayer（结果图层）
            format_key: 格式键（'shp', 'geojson', 'gpkg', 'kml'）

        Returns:
            bool: 是否导出成功
        """
        config = self.FORMAT_CONFIG.get(format_key)
        if config is None:
            return False

        # 弹出文件保存对话框
        path, _ = QFileDialog.getSaveFileName(
            self.parent,
            f'导出为 {config["label"]}',
            os.path.join(self._last_dir, f'coastline_trace{config["ext"]}'),
            config['filter']
        )
        if not path:
            return False

        # 确保后缀正确
        if not path.lower().endswith(config['ext']):
            path += config['ext']

        # 保存上次使用目录
        self._last_dir = os.path.dirname(path)
        QSettings().setValue('CoastlineTracer/last_export_dir', self._last_dir)

        return self._write_layer(layer, path, config['driver'])

    def export_csv(self, layer):
        """导出为 CSV 坐标序列。

        Args:
            layer: QgsVectorLayer

        Returns:
            bool: 是否导出成功
        """
        path, _ = QFileDialog.getSaveFileName(
            self.parent,
            '导出为 CSV',
            os.path.join(self._last_dir, 'coastline_trace.csv'),
            'CSV 文件 (*.csv)'
        )
        if not path:
            return False
        if not path.lower().endswith('.csv'):
            path += '.csv'

        self._last_dir = os.path.dirname(path)
        QSettings().setValue('CoastlineTracer/last_export_dir', self._last_dir)

        try:
            lines = ['segment_id,source_layer,length_m,wkt']
            for feat in layer.getFeatures():
                sid = feat['segment_id']
                src = feat['source_layer']
                length = feat['length_m']
                wkt = feat.geometry().asWkt()
                lines.append(f'{sid},{src},{length},"{wkt}"')

            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            self._show_success(f'CSV 已导出至: {path}')
            return True
        except Exception as e:
            self._show_error(f'导出 CSV 失败: {str(e)}')
            return False

    def copy_to_clipboard(self, layer):
        """将追踪结果复制到剪贴板（WKT 格式）。

        Args:
            layer: QgsVectorLayer
        """
        lines = []
        for feat in layer.getFeatures():
            lines.append(feat.geometry().asWkt())

        text = '\n'.join(lines)
        QApplication.clipboard().setText(text)
        self._show_success(f'已复制 {len(lines)} 段线要素的 WKT 坐标到剪贴板')

    def _write_layer(self, layer, path, driver):
        """使用 QgsVectorFileWriter 写出图层。"""
        crs = QgsCoordinateReferenceSystem('EPSG:4326')

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = driver
        options.fileEncoding = 'UTF-8'

        error, msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            path,
            QgsProject.instance().transformContext(),
            options
        )

        if error == QgsVectorFileWriter.NoError:
            self._show_success(f'已成功导出到: {path}')
            return True
        else:
            self._show_error(f'导出失败: {msg}')
            return False

    def _show_success(self, message):
        """在 QGIS 消息栏显示成功通知。"""
        try:
            qgis_iface.messageBar().pushSuccess('CoastlineTracer', message)
        except Exception:
            pass

    def _show_error(self, message):
        """在 QGIS 消息栏显示错误通知。"""
        try:
            qgis_iface.messageBar().pushCritical('CoastlineTracer', message)
        except Exception:
            pass
