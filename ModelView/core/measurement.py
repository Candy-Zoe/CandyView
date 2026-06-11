"""
测量模块
提供两点距离测量功能
"""

import numpy as np
import open3d as o3d
from typing import List, Tuple, Optional


class MeasurementLine:
    """测量线段数据类"""
    def __init__(self, p1: np.ndarray, p2: np.ndarray):
        self.p1 = p1
        self.p2 = p2
        self.distance = np.linalg.norm(p2 - p1)
        self.line_set: Optional[o3d.geometry.LineSet] = None

    def create_line_geometry(self) -> o3d.geometry.LineSet:
        """创建线段几何体"""
        line = o3d.geometry.LineSet()
        line.points = o3d.utility.Vector3dVector([self.p1, self.p2])
        line.lines = o3d.utility.Vector2iVector([[0, 1]])
        line.colors = o3d.utility.Vector3dVector([[1.0, 0.0, 0.0]])  # 红色
        self.line_set = line
        return line

    def get_distance(self) -> float:
        """获取距离值"""
        return float(self.distance)


class MeasurementManager:
    """测量管理器"""

    def __init__(self):
        self.measurements: List[MeasurementLine] = []
        self.temp_point: Optional[np.ndarray] = None

    def add_measurement(self, p1: np.ndarray, p2: np.ndarray) -> MeasurementLine:
        """
        添加一条测量

        Args:
            p1: 起点坐标
            p2: 终点坐标

        Returns:
            MeasurementLine对象
        """
        measurement = MeasurementLine(p1, p2)
        measurement.create_line_geometry()
        self.measurements.append(measurement)
        return measurement

    def get_all_lines(self) -> List[o3d.geometry.LineSet]:
        """获取所有测量线段的几何体"""
        return [m.line_set for m in self.measurements if m.line_set is not None]

    def get_all_distances(self) -> List[float]:
        """获取所有测量距离"""
        return [m.get_distance() for m in self.measurements]

    def remove_measurement(self, index: int) -> bool:
        """删除指定索引的测量"""
        if 0 <= index < len(self.measurements):
            del self.measurements[index]
            return True
        return False

    def clear_all(self) -> None:
        """清除所有测量"""
        self.measurements.clear()
        self.temp_point = None

    def set_temp_point(self, point: Optional[np.ndarray]) -> None:
        """设置临时点（测量过程中的第一个点）"""
        self.temp_point = point

    def get_temp_point(self) -> Optional[np.ndarray]:
        """获取临时点"""
        return self.temp_point

    def create_sphere_marker(self, point: np.ndarray, radius: float = 0.05) -> o3d.geometry.TriangleMesh:
        """
        创建球体标记

        Args:
            point: 球心坐标
            radius: 球体半径

        Returns:
            球体几何体
        """
        sphere = o3d.geometry.TriangleMesh.create_sphere(radius=radius)
        sphere.translate(point)
        sphere.paint_uniform_color([0.0, 1.0, 0.0])  # 绿色
        return sphere

    def get_measurement_count(self) -> int:
        """获取测量数量"""
        return len(self.measurements)

    def get_measurement_info(self) -> List[Tuple[str, float]]:
        """获取测量信息列表"""
        return [(f"Line {i+1}", m.get_distance()) for i, m in enumerate(self.measurements)]
