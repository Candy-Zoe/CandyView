"""
基础模型加载器接口
定义所有模型加载器必须实现的接口
"""

import numpy as np
from abc import ABC, abstractmethod
from typing import Tuple, Optional, List


class ModelData:
    """模型数据类"""
    def __init__(self):
        self.vertices = []
        self.triangles = []
        self.normals = []
        self.texcoords = []
        self.colors = []
        self.texture = None
        self.texture_path = ""
        self.name = ""
        self.format = ""
        self.center = [0, 0, 0]
        self.scale = 1.0

    def compute_normals(self):
        """计算顶点法线"""
        if not self.vertices or not self.triangles:
            self.normals = []
            return

        normals = [[0.0, 0.0, 0.0] for _ in range(len(self.vertices))]

        for tri in self.triangles:
            if len(tri) >= 3:
                i, j, k = tri[0], tri[1], tri[2]
                v1 = [self.vertices[j][0] - self.vertices[i][0],
                      self.vertices[j][1] - self.vertices[i][1],
                      self.vertices[j][2] - self.vertices[i][2]]
                v2 = [self.vertices[k][0] - self.vertices[i][0],
                      self.vertices[k][1] - self.vertices[i][1],
                      self.vertices[k][2] - self.vertices[i][2]]

                normal = [
                    v1[1] * v2[2] - v1[2] * v2[1],
                    v1[2] * v2[0] - v1[0] * v2[2],
                    v1[0] * v2[1] - v1[1] * v2[0]
                ]

                length = (normal[0]**2 + normal[1]**2 + normal[2]**2)**0.5
                if length > 0.0001:
                    normal = [n / length for n in normal]

                for idx in tri[:3]:
                    normals[idx][0] += normal[0]
                    normals[idx][1] += normal[1]
                    normals[idx][2] += normal[2]

        for i in range(len(normals)):
            length = (normals[i][0]**2 + normals[i][1]**2 + normals[i][2]**2)**0.5
            if length > 0.0001:
                normals[i] = [n / length for n in normals[i]]
            else:
                normals[i] = [0.0, 0.0, 1.0]

        self.normals = normals

    def normalize(self):
        """归一化模型到单位立方体"""
        if not self.vertices:
            return

        vertices = np.array(self.vertices)
        min_v = vertices.min(axis=0)
        max_v = vertices.max(axis=0)
        center = (min_v + max_v) / 2
        size = (max_v - min_v).max()

        if size > 0:
            scale = 2.0 / size
            self.vertices = ((vertices - center) * scale).tolist()
            self.center = center.tolist()
            self.scale = scale

        if self.normals:
            for i in range(len(self.normals)):
                length = (self.normals[i][0]**2 + self.normals[i][1]**2 + self.normals[i][2]**2)**0.5
                if length > 0.0001:
                    self.normals[i] = [n / length for n in self.normals[i]]


class BaseModelLoader(ABC):
    """模型加载器基类"""

    @abstractmethod
    def supports_format(self, extension: str) -> bool:
        """检查是否支持该格式"""
        pass

    @abstractmethod
    def load(self, file_path: str) -> Optional[ModelData]:
        """加载模型文件"""
        pass

    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """获取支持的格式列表"""
        pass

    def _compute_normals(self, vertices: List[List[float]], triangles: List[List[int]]) -> List[List[float]]:
        """计算顶点法线"""
        normals = [[0.0, 0.0, 0.0] for _ in range(len(vertices))]
        
        for tri in triangles:
            if len(tri) >= 3:
                i, j, k = tri[0], tri[1], tri[2]
                v1 = [vertices[j][0] - vertices[i][0],
                      vertices[j][1] - vertices[i][1],
                      vertices[j][2] - vertices[i][2]]
                v2 = [vertices[k][0] - vertices[i][0],
                      vertices[k][1] - vertices[i][1],
                      vertices[k][2] - vertices[i][2]]
                
                # 叉积计算法线
                normal = [
                    v1[1] * v2[2] - v1[2] * v2[1],
                    v1[2] * v2[0] - v1[0] * v2[2],
                    v1[0] * v2[1] - v1[1] * v2[0]
                ]
                
                # 归一化
                length = (normal[0]**2 + normal[1]**2 + normal[2]**2)**0.5
                if length > 0.0001:
                    normal = [n / length for n in normal]
                
                # 添加到三个顶点
                for idx in tri[:3]:
                    normals[idx][0] += normal[0]
                    normals[idx][1] += normal[1]
                    normals[idx][2] += normal[2]
        
        # 归一化所有法线
        for i in range(len(normals)):
            length = (normals[i][0]**2 + normals[i][1]**2 + normals[i][2]**2)**0.5
            if length > 0.0001:
                normals[i] = [n / length for n in normals[i]]
            else:
                normals[i] = [0.0, 0.0, 1.0]
        
        return normals
