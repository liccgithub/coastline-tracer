# -*- coding: utf-8 -*-
"""
CoastlineTracer - 设置持久化管理器

使用 QSettings 保存用户参数，确保下次打开插件时恢复上次设置。

版权所有 (C) 2024 liccgithub
本程序遵循 GNU 通用公共许可证 v3 发布。
"""

from PyQt5.QtCore import QSettings


# 设置组名称
SETTINGS_GROUP = 'CoastlineTracer'

# 默认设置
DEFAULT_SETTINGS = {
    'coast_weight': 1.0,
    'build_coast_weight': 10.0,
    'land_border_weight': 100.0,
    'tolerance': 50.0,
    'algorithm': 'bidirectional_dijkstra',
    'preset_mode': 'standard',
    'enable_spatial_clip': True,
    'buffer_percent': 20,
    'point_a_lon': '',
    'point_a_lat': '',
    'point_b_lon': '',
    'point_b_lat': '',
    'coast_layer': '',
    'build_coast_layer': '',
    'land_border_layer': '',
    'last_export_dir': '',
    'window_width': 700,
    'window_height': 600,
}


class SettingsManager:
    """
    使用 QSettings 持久化保存用户设置。

    保存内容：
    - 上次选择的三个图层路径
    - 参数设置（容差、权重、算法选择）
    - 上次使用的 A/B 点坐标
    - 上次使用的预设模式
    - 窗口大小
    """

    def __init__(self):
        """初始化设置管理器。"""
        self.settings = QSettings()

    def save_settings(self, settings_dict):
        """保存设置字典到 QSettings。

        Args:
            settings_dict (dict): 要保存的设置键值对
        """
        self.settings.beginGroup(SETTINGS_GROUP)
        for key, value in settings_dict.items():
            self.settings.setValue(key, value)
        self.settings.endGroup()
        self.settings.sync()

    def load_settings(self):
        """从 QSettings 加载设置。

        Returns:
            dict: 设置字典，未设置的键使用默认值
        """
        result = dict(DEFAULT_SETTINGS)
        self.settings.beginGroup(SETTINGS_GROUP)
        for key in DEFAULT_SETTINGS:
            stored = self.settings.value(key)
            if stored is not None:
                # 类型转换
                default_val = DEFAULT_SETTINGS[key]
                try:
                    if isinstance(default_val, bool):
                        if isinstance(stored, str):
                            result[key] = stored.lower() in ('true', '1', 'yes')
                        else:
                            result[key] = bool(stored)
                    elif isinstance(default_val, float):
                        result[key] = float(stored)
                    elif isinstance(default_val, int):
                        result[key] = int(stored)
                    else:
                        result[key] = str(stored)
                except (ValueError, TypeError):
                    result[key] = default_val
        self.settings.endGroup()
        return result

    def reset_to_defaults(self):
        """重置所有设置为默认值。"""
        self.settings.beginGroup(SETTINGS_GROUP)
        self.settings.remove('')
        self.settings.endGroup()
        self.settings.sync()

    def save_window_geometry(self, width, height):
        """保存窗口尺寸。

        Args:
            width (int): 窗口宽度
            height (int): 窗口高度
        """
        self.save_settings({'window_width': width, 'window_height': height})

    def load_window_geometry(self):
        """加载窗口尺寸。

        Returns:
            tuple: (宽度, 高度)
        """
        settings = self.load_settings()
        return settings['window_width'], settings['window_height']
