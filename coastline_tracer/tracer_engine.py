# -*- coding: utf-8 -*-
"""
CoastlineTracer - 路径追踪引擎

支持双向 Dijkstra 和 A* 算法，内置 KD-Tree 最近邻查找。

版权所有 (C) 2024 liccgithub
本程序遵循 GNU 通用公共许可证 v3 发布。
"""

import heapq
import math
import time
from dataclasses import dataclass, field


@dataclass
class TraceResult:
    """追踪结果数据类。"""
    success: bool
    path_edges: list = field(default_factory=list)
    # 每个元素: {'node_a': int, 'node_b': int, 'cost': float,
    #            'source_layer': str, 'length_m': float, 'geometry': QgsGeometry}
    total_length_m: float = 0.0
    source_breakdown: dict = field(default_factory=dict)
    # {'coast': 1234.5, 'build_coast': 567.8, 'land_border': 89.0}
    segment_count: int = 0
    elapsed_seconds: float = 0.0
    error_message: str = ''
    suggestions: list = field(default_factory=list)
    total_cost: float = 0.0


class KDTree:
    """
    简单的 2D KD-Tree 实现（不依赖外部库）。
    用于高效查找最近节点。
    """

    def __init__(self, points):
        """构建 KD-Tree。

        Args:
            points: list of (x, y) 坐标
        """
        self.n = len(points)
        if self.n == 0:
            self.root = None
            return
        indexed = list(enumerate(points))
        self.root = self._build(indexed, depth=0)

    def _build(self, points, depth):
        if not points:
            return None
        axis = depth % 2
        points.sort(key=lambda p: p[1][axis])
        mid = len(points) // 2
        return {
            'idx': points[mid][0],
            'point': points[mid][1],
            'left': self._build(points[:mid], depth + 1),
            'right': self._build(points[mid + 1:], depth + 1),
        }

    def _dist_sq(self, a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    def _nearest(self, node, target, depth, best):
        if node is None:
            return best
        d = self._dist_sq(node['point'], target)
        if d < best[0]:
            best = (d, node['idx'])
        axis = depth % 2
        diff = target[axis] - node['point'][axis]
        near, far = (node['left'], node['right']) if diff <= 0 else (node['right'], node['left'])
        best = self._nearest(near, target, depth + 1, best)
        if diff * diff < best[0]:
            best = self._nearest(far, target, depth + 1, best)
        return best

    def nearest(self, target):
        """查找最近点的索引。

        Args:
            target: (x, y) 坐标

        Returns:
            int: 最近点在原始 points 列表中的索引
        """
        if self.root is None:
            return None
        best = (float('inf'), None)
        best = self._nearest(self.root, target, 0, best)
        return best[1]


def _haversine_m(lon1, lat1, lon2, lat2):
    """使用 Haversine 公式计算两点之间的球面距离（米）。"""
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


class TracerEngine:
    """
    高性能路径追踪引擎

    支持：
    1. 双向 Dijkstra：从 A 和 B 两端同时搜索，相遇即停止
    2. A* 算法：使用 Haversine 距离作为启发函数
    3. 标准 Dijkstra

    附加功能：
    - 最近节点查找：使用 KD-Tree
    - 路径不可达诊断：返回详细原因和建议
    """

    def __init__(self):
        """初始化追踪引擎。"""
        self._kd_tree = None
        self._node_ids = None

    def build_kd_tree(self, graph):
        """从图构建 KD-Tree 索引。

        Args:
            graph: GraphBuilder.build_graph() 返回的图字典
        """
        node_ids = graph.get('node_ids', sorted(graph['nodes'].keys()))
        coords = [graph['nodes'][nid] for nid in node_ids]
        self._kd_tree = KDTree(coords)
        self._node_ids = node_ids

    def find_nearest_node(self, point, graph):
        """查找距离给定点最近的图节点。

        Args:
            point: (lon, lat) 坐标元组
            graph: 图字典

        Returns:
            int: 节点 ID，如果图为空则返回 None
        """
        if not graph['nodes']:
            return None

        # 延迟构建 KD-Tree
        if self._kd_tree is None or self._node_ids is None:
            self.build_kd_tree(graph)

        idx = self._kd_tree.nearest(point)
        if idx is None:
            return None
        return self._node_ids[idx]

    def trace_path(self, graph, start_node, end_node, algorithm='bidirectional_dijkstra'):
        """核心追踪方法。

        Args:
            graph: 图字典
            start_node: 起点节点 ID
            end_node: 终点节点 ID
            algorithm: 算法选择
                - 'dijkstra': 标准单向 Dijkstra
                - 'bidirectional_dijkstra': 双向 Dijkstra
                - 'astar': A* 算法

        Returns:
            TraceResult
        """
        start_time = time.time()

        if start_node is None or end_node is None:
            return TraceResult(
                success=False,
                error_message='⚠️ 请先设置起点 A 和终点 B',
                suggestions=['在"起止点"标签页设置 A/B 点坐标']
            )

        if start_node not in graph['nodes'] or end_node not in graph['nodes']:
            return TraceResult(
                success=False,
                error_message='❌ 起点或终点不在图中',
                suggestions=['检查 A/B 点是否在数据覆盖范围内', '增大节点合并容差']
            )

        if start_node == end_node:
            return TraceResult(
                success=True,
                path_edges=[],
                total_length_m=0.0,
                segment_count=0,
                elapsed_seconds=0.0
            )

        # 选择算法
        if algorithm == 'bidirectional_dijkstra':
            path_nodes, path_costs = self._bidirectional_dijkstra(graph, start_node, end_node)
        elif algorithm == 'astar':
            path_nodes, path_costs = self._astar(graph, start_node, end_node)
        else:
            path_nodes, path_costs = self._dijkstra(graph, start_node, end_node)

        elapsed = time.time() - start_time

        if path_nodes is None:
            return TraceResult(
                success=False,
                elapsed_seconds=elapsed,
                error_message='❌ 无法找到从 A 到 B 的连通路径。',
                suggestions=[
                    '增大节点合并容差（建议 100～500 米）',
                    '检查数据是否覆盖 A/B 点区域',
                    '降低低优先级图层的权重',
                    '禁用空间裁剪或增大缓冲区',
                ]
            )

        # 从路径节点重建路径边
        path_edges = self._reconstruct_edges(graph, path_nodes)
        total_length = sum(e['length_m'] for e in path_edges)
        total_cost = sum(e['cost'] for e in path_edges)

        # 统计各来源占比
        source_breakdown = {}
        for e in path_edges:
            src = e['source_layer']
            source_breakdown[src] = source_breakdown.get(src, 0.0) + e['length_m']

        return TraceResult(
            success=True,
            path_edges=path_edges,
            total_length_m=total_length,
            source_breakdown=source_breakdown,
            segment_count=len(path_edges),
            elapsed_seconds=elapsed,
            total_cost=total_cost
        )

    def _dijkstra(self, graph, start, end):
        """标准单向 Dijkstra 算法。"""
        dist = {start: 0.0}
        prev = {start: None}
        heap = [(0.0, start)]
        visited = set()

        while heap:
            d, u = heapq.heappop(heap)
            if u in visited:
                continue
            visited.add(u)
            if u == end:
                break
            for v, cost, _ in graph['adjacency'].get(u, []):
                nd = d + cost
                if nd < dist.get(v, float('inf')):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))

        if end not in dist:
            return None, None

        path = []
        cur = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path, dist[end]

    def _bidirectional_dijkstra(self, graph, start, end):
        """双向 Dijkstra 算法。

        从起点和终点同时搜索，相遇时停止。
        """
        # 正向
        dist_f = {start: 0.0}
        prev_f = {start: None}
        heap_f = [(0.0, start)]
        visited_f = set()

        # 反向
        dist_b = {end: 0.0}
        prev_b = {end: None}
        heap_b = [(0.0, end)]
        visited_b = set()

        best = float('inf')
        meeting = None

        def relax(heap, dist, prev, u, visited_other, dist_other):
            nonlocal best, meeting
            for v, cost, _ in graph['adjacency'].get(u, []):
                nd = dist[u] + cost
                if nd < dist.get(v, float('inf')):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))
                # 检查是否相遇
                if v in dist_other:
                    total = nd + dist_other[v]
                    if total < best:
                        best = total
                        meeting = v

        while heap_f or heap_b:
            # 正向步骤
            if heap_f:
                df, u = heapq.heappop(heap_f)
                if u not in visited_f:
                    visited_f.add(u)
                    if df <= best:
                        relax(heap_f, dist_f, prev_f, u, visited_b, dist_b)

            # 反向步骤
            if heap_b:
                db, v = heapq.heappop(heap_b)
                if v not in visited_b:
                    visited_b.add(v)
                    if db <= best:
                        relax(heap_b, dist_b, prev_b, v, visited_f, dist_f)

            # 终止条件
            min_f = heap_f[0][0] if heap_f else float('inf')
            min_b = heap_b[0][0] if heap_b else float('inf')
            if min_f + min_b >= best:
                break

        if meeting is None:
            # 尝试直接检查 end 是否可达
            if end in dist_f:
                meeting = end
                best = dist_f[end]
            else:
                return None, None

        # 重建路径：从 start 到 meeting（正向）+ 从 end 到 meeting（反向，需翻转）
        path_f = []
        cur = meeting
        while cur is not None:
            path_f.append(cur)
            cur = prev_f.get(cur)
        path_f.reverse()

        path_b = []
        cur = prev_b.get(meeting)
        while cur is not None:
            path_b.append(cur)
            cur = prev_b.get(cur)

        return path_f + path_b, best

    def _astar(self, graph, start, end):
        """A* 算法，使用 Haversine 距离作为启发函数。"""
        nodes = graph['nodes']
        ex, ey = nodes[end]

        def h(nid):
            nx, ny = nodes[nid]
            return _haversine_m(nx, ny, ex, ey)

        dist = {start: 0.0}
        prev = {start: None}
        heap = [(h(start), 0.0, start)]
        visited = set()

        while heap:
            _, d, u = heapq.heappop(heap)
            if u in visited:
                continue
            visited.add(u)
            if u == end:
                break
            for v, cost, _ in graph['adjacency'].get(u, []):
                nd = d + cost
                if nd < dist.get(v, float('inf')):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd + h(v), nd, v))

        if end not in dist:
            return None, None

        path = []
        cur = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path, dist[end]

    def _reconstruct_edges(self, graph, path_nodes):
        """从路径节点列表重建路径边信息。

        Args:
            graph: 图字典
            path_nodes: 有序节点 ID 列表

        Returns:
            list of dict
        """
        edges = []
        for i in range(len(path_nodes) - 1):
            u = path_nodes[i]
            v = path_nodes[i + 1]
            # 查找 u->v 的边
            best_edge = None
            best_cost = float('inf')
            for neighbor, cost, edge_info in graph['adjacency'].get(u, []):
                if neighbor == v and cost < best_cost:
                    best_cost = cost
                    best_edge = edge_info
            if best_edge is None:
                continue
            edges.append({
                'node_a': u,
                'node_b': v,
                'cost': best_cost,
                'source_layer': best_edge['source_layer'],
                'length_m': best_edge['length_m'],
                'geometry': best_edge.get('geometry'),
            })
        return edges
