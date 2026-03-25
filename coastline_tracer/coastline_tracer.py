# -*- coding: utf-8 -*-
"""
CoastlineTracer - 主插件类

版权所有 (C) 2024 liccgithub
本程序遵循 GNU 通用公共许可证 v3 发布。
"""

import os
from PyQt5.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction
from qgis.core import QgsApplication


class CoastlineTracer:
    """主插件类，负责菜单注册、工具栏和快捷键管理。"""

    def __init__(self, iface):
        """构造函数。

        Args:
            iface: QGIS 接口对象
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.dialog = None
        self.actions = []
        self.menu = self.tr('海岸线追踪')
        self.toolbar = self.iface.addToolBar('CoastlineTracer')
        self.toolbar.setObjectName('CoastlineTracerToolBar')

        # 加载翻译
        locale = QSettings().value('locale/userLocale', 'zh_CN')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            f'coastline_tracer_{locale}.qm'
        )
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

    def tr(self, message):
        """翻译函数。"""
        return QCoreApplication.translate('CoastlineTracer', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
        shortcut=None
    ):
        """辅助方法：创建并注册动作。"""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        if shortcut is not None:
            action.setShortcut(shortcut)

        if add_to_toolbar:
            self.toolbar.addAction(action)
        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action
            )

        self.actions.append(action)
        return action

    def initGui(self):
        """初始化插件 GUI，由 QGIS 在加载时调用。"""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr('海岸线追踪器'),
            callback=self.run,
            parent=self.iface.mainWindow(),
            status_tip=self.tr('打开海岸线追踪器对话框'),
            whats_this=self.tr('基于优先级的海岸线自动追踪工具'),
            shortcut='Ctrl+Shift+T'
        )

    def unload(self):
        """卸载插件，清理 GUI 元素。"""
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.menu,
                action
            )
            self.iface.removeToolBarIcon(action)

        # 移除工具栏
        del self.toolbar

        # 关闭对话框
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def run(self):
        """运行插件，显示追踪器对话框。"""
        if self.dialog is None:
            from .coastline_tracer_dialog import CoastlineTracerDialog
            self.dialog = CoastlineTracerDialog(self.iface, self.iface.mainWindow())

        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
