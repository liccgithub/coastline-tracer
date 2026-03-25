# -*- coding: utf-8 -*-
"""
CoastlineTracer - 追踪统计面板

从 TraceResult 生成统计摘要，提供 HTML 格式显示文本。

版权所有 (C) 2024 liccgithub
本程序遵循 GNU 通用公共许可证 v3 发布。
"""


# 来源图层的显示名称
LAYER_DISPLAY_NAMES = {
    'coast': '海岸线',
    'build_coast': '建设线',
    'land_border': '陆地边界',
}

# 来源图层的颜色
LAYER_COLORS = {
    'coast': '#2196F3',
    'build_coast': '#FF9800',
    'land_border': '#795548',
}


class StatisticsPanel:
    """
    追踪统计信息管理

    从 TraceResult 生成统计摘要：
    - 总路径长度（km）
    - 各来源占比（百分比 + 长度）
    - 线段数量
    - 追踪耗时
    - 生成用于 UI 显示的 HTML 格式文本
    """

    def __init__(self, trace_result=None):
        """初始化统计面板。

        Args:
            trace_result: TraceResult 对象（可选，后续可通过 update 设置）
        """
        self.trace_result = trace_result

    def update(self, trace_result):
        """更新统计数据。

        Args:
            trace_result: TraceResult 对象
        """
        self.trace_result = trace_result

    def generate_html(self):
        """生成 HTML 格式的统计摘要。

        Returns:
            str: HTML 文本
        """
        if self.trace_result is None:
            return '<p style="color: gray;">暂无追踪结果</p>'

        result = self.trace_result

        if not result.success:
            return f'''
<div style="color: #e53935; padding: 10px;">
  <b>❌ 追踪失败</b><br>
  {result.error_message}
  <ul>
    {''.join(f'<li>{s}</li>' for s in result.suggestions)}
  </ul>
</div>
'''

        total_km = result.total_length_m / 1000.0
        total_m = result.total_length_m

        # 构建来源占比 HTML
        source_html = ''
        for src, length_m in sorted(
            result.source_breakdown.items(),
            key=lambda x: -x[1]
        ):
            if total_m > 0:
                pct = length_m / total_m * 100
            else:
                pct = 0.0
            km = length_m / 1000.0
            display_name = LAYER_DISPLAY_NAMES.get(src, src)
            color = LAYER_COLORS.get(src, '#9E9E9E')
            bar_width = int(pct * 2)  # 最宽 200px
            source_html += f'''
<tr>
  <td style="padding: 4px 8px; color: {color}; font-weight: bold;">
    ■ {display_name}
  </td>
  <td style="padding: 4px 8px; text-align: right;">
    {pct:.1f}%
  </td>
  <td style="padding: 4px 8px;">
    <div style="background: {color}; width: {bar_width}px; height: 12px;
         border-radius: 2px; display: inline-block;"></div>
  </td>
  <td style="padding: 4px 8px; text-align: right; color: gray;">
    {km:,.2f} km
  </td>
</tr>
'''

        html = f'''
<div style="font-family: 微软雅黑, Arial, sans-serif; font-size: 13px; padding: 8px;">
  <table width="100%" cellspacing="0" cellpadding="0">
    <tr>
      <td colspan="2" style="padding: 6px 8px; background: #E8F5E9; border-radius: 4px; margin-bottom: 8px;">
        <b style="color: #2E7D32;">✅ 追踪状态：成功</b>
      </td>
    </tr>
  </table>

  <table width="100%" cellspacing="4" cellpadding="0" style="margin-top: 8px;">
    <tr>
      <td style="padding: 4px 8px;"><b>📏 总路径长度</b></td>
      <td style="padding: 4px 8px; color: #1565C0; font-size: 14px;">
        <b>{total_km:,.2f} km</b>
        <span style="color: gray; font-size: 11px;">（{total_m:,.0f} 米）</span>
      </td>
    </tr>
    <tr>
      <td style="padding: 4px 8px;"><b>⏱ 追踪耗时</b></td>
      <td style="padding: 4px 8px;">{result.elapsed_seconds:.2f} 秒</td>
    </tr>
    <tr>
      <td style="padding: 4px 8px;"><b>🔗 线段数量</b></td>
      <td style="padding: 4px 8px;">{result.segment_count} 段</td>
    </tr>
  </table>

  <hr style="border: none; border-top: 1px solid #eee; margin: 8px 0;">
  <b style="padding: 4px 8px;">📊 来源占比</b>
  <table width="100%" cellspacing="0" cellpadding="0" style="margin-top: 6px;">
    {source_html}
  </table>
</div>
'''
        return html

    def generate_plain_text(self):
        """生成纯文本格式的统计摘要（用于日志输出）。

        Returns:
            str: 纯文本
        """
        if self.trace_result is None:
            return '暂无追踪结果'

        result = self.trace_result
        if not result.success:
            return f'追踪失败: {result.error_message}'

        total_km = result.total_length_m / 1000.0
        lines = [
            f'✅ 追踪成功！路径长度 {total_km:,.2f} km，共 {result.segment_count} 段',
            f'   耗时: {result.elapsed_seconds:.2f} 秒',
        ]
        for src, length_m in sorted(result.source_breakdown.items(), key=lambda x: -x[1]):
            km = length_m / 1000.0
            if result.total_length_m > 0:
                pct = length_m / result.total_length_m * 100
            else:
                pct = 0.0
            display = LAYER_DISPLAY_NAMES.get(src, src)
            lines.append(f'   {display}: {pct:.1f}% ({km:,.2f} km)')

        return '\n'.join(lines)
