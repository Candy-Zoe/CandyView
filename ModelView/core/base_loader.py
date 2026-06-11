"""
基础模型加载器接口
定义所有模型加载器必须实现的接口
"""

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
