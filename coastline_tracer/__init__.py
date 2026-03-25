# -*- coding: utf-8 -*-
"""
CoastlineTracer - 基于优先级的海岸线自动追踪与连接 QGIS 插件

版权所有 (C) 2024 liccgithub
本程序是自由软件：你可以在自由软件基金会发布的 GNU 通用公共许可证条款下
重新分发和/或修改它，许可证版本为第3版或（根据你的选择）任何更高版本。
"""


def classFactory(iface):
    """QGIS 插件工厂函数，由 QGIS 在加载插件时调用。"""
    from .coastline_tracer import CoastlineTracer
    return CoastlineTracer(iface)
