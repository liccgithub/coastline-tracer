# -*- coding: utf-8 -*-
"""
CoastlineTracer - 高性能图构建引擎

使用空间裁剪、并查集合并和邻接表构建加权图，
支持序列化缓存避免重复构建。

版权所有 (C) 2024 liccgithub
本程序遵循 GNU 通用公共许可证 v3 发布。
"""

import math
import pickle
import time
from collections import defaultdict

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsProject,
    QgsRectangle,
    QgsSpatialIndex,
    QgsWkbTypes,
)


class UnionFind:
    """并查集（Union-Find）数据结构，用于节点合并。"""

    def __init__(self):
        self.parent = {}
        self.rank = {}

    def find(self, x):
        """查找根节点（路径压缩）。"""
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        """合并两个集合（按秩合并）。"""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank.get(rx, 0) < self.rank.get(ry, 0):
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank.get(rx, 0) == self.rank.get(ry, 0):
            self.rank[rx] = self.rank.get(rx, 0) + 1


class GraphBuilder:
    """
    高性能图构建引擎

    核心特性：
    1. 空间裁剪：根据 A/B 点自动计算 BoundingBox（扩展缓冲区），
       使用 QgsSpatialIndex 只加载相关区域的要素，避免全球数据全部加载
    2. 并查集（Union-Find）节点合并：距离小于 tolerance 的节点合并为同一节点，
       使用空间哈希网格分块处理，时间复杂度从 O(n²) 降到 O(n)
    3. 图结构：adjacency list（邻接表），dict[node_id] -> list[(neighbor_id, cost, edge_info)]
    4. 边成本 = 几何长度(米) × 优先级权重系数
    5. 支持图序列化缓存（pickle），相同数据不需要重建图
    """

    # 目标坐标系（统一转换到 WGS84）
    TARGET_CRS = QgsCoordinateReferenceSystem('EPSG:4326')

    def __init__(self, progress_callback=None):
        """初始化图构建器。

        Args:
            progress_callback: 进度回调函数 progress_callback(percent, message)
        """
        self.progress_callback = progress_callback
        self.dist_calc = QgsDistanceArea()
        self.dist_calc.setEllipsoid('WGS84')

        # 图数据结构
        self.nodes = {}          # node_id -> (x, y)
        self.adjacency = defaultdict(list)  # node_id -> [(neighbor_id, cost, edge_info)]
        self.node_coords = []    # [(x, y)] 用于 KD-Tree 索引

    def _report(self, percent, message):
        """汇报进度。"""
        if self.progress_callback:
            self.progress_callback(percent, message)

    def _get_transform(self, layer):
        """获取图层到目标 CRS 的坐标变换。

        Args:
            layer: QgsVectorLayer

        Returns:
            QgsCoordinateTransform 或 None（如果不需要转换）
        """
        src_crs = layer.crs()
        if src_crs == self.TARGET_CRS:
            return None
        return QgsCoordinateTransform(
            src_crs,
            self.TARGET_CRS,
            QgsProject.instance()
        )

    def _point_to_cell(self, x, y, cell_size):
        """将坐标转换为网格单元键。"""
        return (int(math.floor(x / cell_size)), int(math.floor(y / cell_size)))

    def _merge_nodes(self, raw_points, tolerance_deg):
        """使用空间哈希网格 + 并查集合并近邻节点。

        Args:
            raw_points: list of (x, y, point_id)
            tolerance_deg: 合并容差（度数）

        Returns:
            dict: point_id -> canonical_node_id
            dict: canonical_node_id -> (x, y)
        """
        uf = UnionFind()
        grid = defaultdict(list)

        # 建立网格索引
        for x, y, pid in raw_points:
            cell = self._point_to_cell(x, y, tolerance_deg)
            grid[cell].append((x, y, pid))
            uf.find(pid)  # 初始化

        # 对每个网格及其相邻网格进行合并
        for (cx, cy), pts in grid.items():
            # 检查当前格和相邻格
            neighbors_cells = [
                (cx + dx, cy + dy)
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
            ]
            neighbor_pts = []
            for nc in neighbors_cells:
                neighbor_pts.extend(grid.get(nc, []))

            for x1, y1, pid1 in pts:
                for x2, y2, pid2 in neighbor_pts:
                    if pid1 >= pid2:
                        continue
                    dx = x1 - x2
                    dy = y1 - y2
                    if dx * dx + dy * dy <= tolerance_deg * tolerance_deg:
                        uf.union(pid1, pid2)

        # 构建代表节点映射
        canonical_coords = {}
        for x, y, pid in raw_points:
            root = uf.find(pid)
            if root not in canonical_coords:
                canonical_coords[root] = (x, y)

        # point_id -> canonical_node_id
        mapping = {pid: uf.find(pid) for _, _, pid in raw_points}

        return mapping, canonical_coords

    def _calc_edge_length(self, geom):
        """计算边的地理长度（米）。

        Args:
            geom: QgsGeometry（线几何）

        Returns:
            float: 长度（米）
        """
        try:
            return self.dist_calc.measureLength(geom)
        except Exception:
            return geom.length() * 111320  # 粗略估算

    def build_graph(self, layers_config, bbox=None, tolerance=50.0):
        """构建加权图。

        Args:
            layers_config: list of {
                'layer': QgsVectorLayer,
                'weight': float,
                'name': str
            }
            bbox: QgsRectangle 或 None（不裁剪）
            tolerance: 节点合并容差（米），默认 50 米

        Returns:
            dict: 图结构 {
                'nodes': {node_id: (x, y)},
                'adjacency': {node_id: [(neighbor_id, cost, edge_info), ...]},
                'node_list': [(x, y)]  # 用于 KD-Tree
            }
        """
        start_time = time.time()
        self._report(0, '开始构建网络图...')

        # 容差转换为度（约 1 度 = 111320 米）
        tolerance_deg = tolerance / 111320.0

        all_raw_points = []   # (x, y, point_id)
        all_segments = []     # (p1_id, p2_id, length_m, weight, layer_name, geom)
        point_id_counter = [0]

        def next_pid():
            pid = point_id_counter[0]
            point_id_counter[0] += 1
            return pid

        total_layers = len(layers_config)
        for layer_idx, config in enumerate(layers_config):
            layer = config['layer']
            weight = config['weight']
            layer_name = config['name']

            base_progress = int(layer_idx / total_layers * 60)
            self._report(base_progress, f'正在加载图层: {layer_name}...')

            # 坐标变换
            transform = self._get_transform(layer)

            # 空间裁剪：构建空间索引
            if bbox is not None:
                spatial_index = QgsSpatialIndex(layer.getFeatures())
                feat_ids = spatial_index.intersects(bbox)
                features = [layer.getFeature(fid) for fid in feat_ids]
            else:
                features = list(layer.getFeatures())

            self._report(
                base_progress + 5,
                f'{layer_name}: 已加载 {len(features)} 条要素'
            )

            # 检查图层类型
            if layer.wkbType() not in (
                QgsWkbTypes.LineString,
                QgsWkbTypes.MultiLineString,
                QgsWkbTypes.LineStringZ,
                QgsWkbTypes.MultiLineStringZ,
                QgsWkbTypes.LineString25D,
                QgsWkbTypes.MultiLineString25D,
            ):
                continue

            # 处理每条要素
            for feat in features:
                geom = feat.geometry()
                if geom is None or geom.isEmpty():
                    continue

                # 坐标转换
                if transform:
                    geom.transform(transform)

                # 提取所有线段的端点（标准模式：使用顶点）
                lines = []
                if QgsWkbTypes.isMultiType(geom.wkbType()):
                    lines = geom.asMultiPolyline()
                else:
                    lines = [geom.asPolyline()]

                for line in lines:
                    if len(line) < 2:
                        continue

                    # 为每个顶点分配 point_id
                    pids = []
                    for pt in line:
                        pid = next_pid()
                        all_raw_points.append((pt.x(), pt.y(), pid))
                        pids.append(pid)

                    # 记录线段
                    from qgis.core import QgsGeometry, QgsPointXY
                    for i in range(len(pids) - 1):
                        seg_geom = QgsGeometry.fromPolylineXY([
                            QgsPointXY(line[i].x(), line[i].y()),
                            QgsPointXY(line[i + 1].x(), line[i + 1].y()),
                        ])
                        length_m = self._calc_edge_length(seg_geom)
                        all_segments.append((
                            pids[i], pids[i + 1],
                            length_m, weight, layer_name,
                            seg_geom
                        ))

        self._report(65, f'正在合并节点（容差 {tolerance} 米）...')

        if not all_raw_points:
            return {'nodes': {}, 'adjacency': {}, 'node_list': []}

        # 合并近邻节点
        mapping, canonical_coords = self._merge_nodes(all_raw_points, tolerance_deg)

        self._report(80, '正在构建邻接表...')

        # 构建图
        nodes = canonical_coords
        adjacency = defaultdict(list)

        for p1_id, p2_id, length_m, weight, layer_name, seg_geom in all_segments:
            n1 = mapping[p1_id]
            n2 = mapping[p2_id]
            if n1 == n2:
                continue  # 同一节点，跳过自环

            cost = length_m * weight
            edge_info = {
                'source_layer': layer_name,
                'length_m': length_m,
                'weight': weight,
                'geometry': seg_geom,
            }
            adjacency[n1].append((n2, cost, edge_info))
            adjacency[n2].append((n1, cost, edge_info))  # 无向图

        # 节点坐标列表（用于 KD-Tree）
        node_ids = sorted(nodes.keys())
        node_list = [(nodes[nid][0], nodes[nid][1]) for nid in node_ids]

        elapsed = time.time() - start_time
        self._report(
            100,
            f'图构建完成！节点: {len(nodes)}，边: {sum(len(v) for v in adjacency.values()) // 2}，'
            f'耗时: {elapsed:.1f} 秒'
        )

        graph = {
            'nodes': nodes,
            'adjacency': dict(adjacency),
            'node_list': node_list,
            'node_ids': node_ids,
        }
        return graph

    def save_cached_graph(self, graph, path):
        """序列化图到文件缓存。

        Args:
            graph: 图字典
            path: 缓存文件路径
        """
        try:
            with open(path, 'wb') as f:
                pickle.dump(graph, f, protocol=pickle.HIGHEST_PROTOCOL)
            return True
        except Exception as e:
            return False

    def load_cached_graph(self, path):
        """从文件加载缓存图。

        Args:
            path: 缓存文件路径

        Returns:
            dict 或 None
        """
        try:
            with open(path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            return None

    @staticmethod
    def compute_bbox(point_a, point_b, buffer_percent=20):
        """计算 A/B 点的包围盒并扩展缓冲区。

        Args:
            point_a: (lon, lat) 元组
            point_b: (lon, lat) 元组
            buffer_percent: 缓冲区扩展百分比

        Returns:
            QgsRectangle
        """
        min_x = min(point_a[0], point_b[0])
        max_x = max(point_a[0], point_b[0])
        min_y = min(point_a[1], point_b[1])
        max_y = max(point_a[1], point_b[1])

        # 最小尺寸保证（至少 1 度范围）
        if max_x - min_x < 1.0:
            cx = (max_x + min_x) / 2
            min_x = cx - 0.5
            max_x = cx + 0.5
        if max_y - min_y < 1.0:
            cy = (max_y + min_y) / 2
            min_y = cy - 0.5
            max_y = cy + 0.5

        width = max_x - min_x
        height = max_y - min_y
        buf_x = width * buffer_percent / 100
        buf_y = height * buffer_percent / 100

        return QgsRectangle(
            min_x - buf_x,
            min_y - buf_y,
            max_x + buf_x,
            max_y + buf_y
        )
