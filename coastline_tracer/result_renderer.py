# -*- coding: utf-8 -*-
"""
CoastlineTracer - 结果分色渲染器

根据 source_layer 字段自动分色显示追踪结果。

版权所有 (C) 2024 liccgithub
本程序遵循 GNU 通用公共许可证 v3 发布。
"""

from PyQt5.QtGui import QColor
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLineSymbol,
    QgsPointXY,
    QgsProject,
    QgsRendererCategory,
    QgsVectorLayer,
    QgsWkbTypes,
)
from PyQt5.QtCore import QVariant


# 各来源图层的渲染颜色和线宽
LAYER_STYLES = {
    'coast': {
        'color': '#2196F3',     # 蓝色 - 海岸线
        'width': '3',
        'label': '海岸线',
    },
    'build_coast': {
        'color': '#FF9800',     # 橙色 - 建设线
        'width': '2.5',
        'label': '建设线',
    },
    'land_border': {
        'color': '#795548',     # 棕色 - 陆地边界
        'width': '2',
        'label': '陆地边界',
    },
    '__default__': {
        'color': '#9E9E9E',     # 灰色 - 未知来源
        'width': '2',
        'label': '其他',
    },
}


class ResultRenderer:
    """
    追踪结果分色渲染器

    根据 source_layer 字段自动分色显示：
    - coast（海岸线）→ 蓝色 #2196F3，线宽 3
    - build_coast（建设线）→ 橙色 #FF9800，线宽 2.5
    - land_border（陆地边界）→ 棕色 #795548，线宽 2

    使用 QgsCategorizedSymbolRenderer 实现
    """

    @staticmethod
    def create_result_layer(trace_result):
        """根据追踪结果创建临时矢量图层。

        Args:
            trace_result: TraceResult 对象

        Returns:
            QgsVectorLayer: 结果图层（已添加要素，未加入项目）
        """
        # 创建内存图层
        layer = QgsVectorLayer('LineString?crs=EPSG:4326', '海岸线追踪结果', 'memory')
        provider = layer.dataProvider()

        # 添加属性字段
        provider.addAttributes([
            QgsField('segment_id', QVariant.Int, 'int', 10),
            QgsField('source_layer', QVariant.String, 'text', 50),
            QgsField('length_m', QVariant.Double, 'double', 15, 3),
            QgsField('priority', QVariant.Int, 'int', 5),
            QgsField('cost', QVariant.Double, 'double', 15, 3),
        ])
        layer.updateFields()

        # 来源名称到优先级的映射
        priority_map = {
            'coast': 1,
            'build_coast': 2,
            'land_border': 3,
        }

        # 添加要素
        features = []
        for i, edge in enumerate(trace_result.path_edges):
            geom = edge.get('geometry')
            if geom is None:
                continue

            feat = QgsFeature(layer.fields())
            feat.setGeometry(geom)
            src_layer = edge.get('source_layer', 'unknown')
            feat.setAttributes([
                i + 1,
                src_layer,
                round(edge.get('length_m', 0.0), 3),
                priority_map.get(src_layer, 99),
                round(edge.get('cost', 0.0), 3),
            ])
            features.append(feat)

        provider.addFeatures(features)
        layer.updateExtents()

        # 应用分色渲染
        ResultRenderer.apply_renderer(layer)

        return layer

    @staticmethod
    def apply_renderer(layer):
        """为图层应用分色渲染器。

        Args:
            layer: QgsVectorLayer
        """
        categories = []

        # 已知来源类别
        for src_key, style in LAYER_STYLES.items():
            if src_key == '__default__':
                continue
            symbol = QgsLineSymbol.createSimple({
                'color': style['color'],
                'width': style['width'],
                'capstyle': 'round',
                'joinstyle': 'round',
            })
            category = QgsRendererCategory(
                src_key,
                symbol,
                style['label']
            )
            categories.append(category)

        # 默认类别（未知来源）
        default_style = LAYER_STYLES['__default__']
        default_symbol = QgsLineSymbol.createSimple({
            'color': default_style['color'],
            'width': default_style['width'],
            'capstyle': 'round',
        })
        default_cat = QgsRendererCategory(
            '',
            default_symbol,
            default_style['label']
        )
        categories.append(default_cat)

        renderer = QgsCategorizedSymbolRenderer('source_layer', categories)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    @staticmethod
    def add_to_project(layer):
        """将图层添加到当前 QGIS 项目。

        Args:
            layer: QgsVectorLayer

        Returns:
            QgsVectorLayer: 添加后的图层
        """
        QgsProject.instance().addMapLayer(layer)
        return layer
