"""
STL模型加载器
支持ASCII和二进制STL格式
"""

import struct
import os
from typing import Optional, List
from core.base_loader import BaseModelLoader, ModelData


class STLLoader(BaseModelLoader):
    """STL格式模型加载器"""

    def supports_format(self, extension: str) -> bool:
        """检查是否支持STL格式"""
        return extension.lower() == '.stl'

    def get_supported_formats(self) -> List[str]:
        """获取支持的格式列表"""
        return ['.stl']

    def load(self, file_path: str) -> Optional[ModelData]:
        """加载STL文件"""
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, 'rb') as f:
                return self._parse_stl(f)
        except Exception as e:
            print(f"STL load error: {e}")
            return None

    def _parse_stl(self, file):
        """解析STL文件"""
        model = ModelData()
        model.format = "STL"
        model.name = os.path.basename(file.name)

        # 检查是ASCII还是二进制格式
        header = file.read(80)
        if header[:5].decode('ascii', errors='ignore').startswith('solid'):
            # ASCII格式
            return self._parse_ascii_stl(file, header, model)
        else:
            # 二进制格式
            return self._parse_binary_stl(file, header, model)

    def _parse_binary_stl(self, file, header, model):
        """解析二进制STL"""
        vertices = []
        triangles = []
        normals = []

        # 读取三角形数量
        file.seek(80)
        tri_count = struct.unpack('<I', file.read(4))[0]

        # 读取每个三角形
        for i in range(tri_count):
            # 读取法线
            nx, ny, nz = struct.unpack('<fff', file.read(12))
            normals.append([nx, ny, nz])

            # 读取三个顶点
            v1 = [struct.unpack('<fff', file.read(12))]
            v2 = [struct.unpack('<fff', file.read(12))]
            v3 = [struct.unpack('<fff', file.read(12))]
            
            # 计算顶点索引
            base_idx = len(vertices)
            vertices.extend(v1)
            vertices.extend(v2)
            vertices.extend(v3)
            triangles.append([base_idx, base_idx + 1, base_idx + 2])

            # 跳过属性字节
            file.read(2)

        model.vertices = [list(v[0]) for v in vertices]
        model.triangles = triangles
        model.normals = normals

        return model

    def _parse_ascii_stl(self, file, header, model):
        """解析ASCII STL"""
        vertices = []
        triangles = []
        normals = []

        # 从头开始读取
        file.seek(0)
        
        vertex_cache = {}
        tri_count = 0

        for line in file:
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='ignore')
            
            line = line.strip().lower()
            
            if line.startswith('facet normal'):
                parts = line.split()
                nx, ny, nz = float(parts[2]), float(parts[3]), float(parts[4])
                normals.append([nx, ny, nz])
            
            elif line.startswith('vertex'):
                parts = line.split()
                v = (float(parts[1]), float(parts[2]), float(parts[3]))
                if v not in vertex_cache:
                    vertex_cache[v] = len(vertices)
                    vertices.append(list(v))
            
            elif line.startswith('endloop'):
                if len(vertex_cache) >= 3:
                    tri_indices = list(vertex_cache.values())[-3:]
                    triangles.append(tri_indices)
                    tri_count += 1
                    vertex_cache = {}

        model.vertices = vertices
        model.triangles = triangles
        model.normals = normals if normals else self._compute_normals(vertices, triangles)

        return model
