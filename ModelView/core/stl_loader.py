"""
STL模型加载器
支持ASCII和二进制STL格式
"""

import struct
import os
import numpy as np
from typing import Optional, List
from core.base_loader import BaseModelLoader, ModelData


class STLLoader(BaseModelLoader):
    """STL格式模型加载器 - 增强版"""

    def supports_format(self, extension: str) -> bool:
        return extension.lower() == '.stl'

    def get_supported_formats(self) -> List[str]:
        return ['.stl']

    def load(self, file_path: str) -> Optional[ModelData]:
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, 'rb') as f:
                header = f.read(80)
                if header[:5].decode('ascii', errors='ignore').lower().startswith('solid'):
                    f.seek(0)
                    return self._parse_ascii_stl(file_path)
                else:
                    return self._parse_binary_stl(file_path)
        except Exception as e:
            print(f"STL load error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_binary_stl(self, file_path: str) -> ModelData:
        """解析二进制STL"""
        model = ModelData()
        model.format = "STL"
        model.name = os.path.basename(file_path)

        vertices = []
        normals = []
        triangles = []

        with open(file_path, 'rb') as f:
            f.read(80)
            tri_count = struct.unpack('<I', f.read(4))[0]

            if tri_count > 10_000_000:
                print(f"[STL] Warning: Large triangle count ({tri_count}), may take time...")
            
            for i in range(tri_count):
                try:
                    nx, ny, nz = struct.unpack('<fff', f.read(12))
                    normals.append([nx, ny, nz])

                    v1 = list(struct.unpack('<fff', f.read(12)))
                    v2 = list(struct.unpack('<fff', f.read(12)))
                    v3 = list(struct.unpack('<fff', f.read(12)))

                    base_idx = len(vertices)
                    vertices.extend([v1, v2, v3])
                    triangles.append([base_idx, base_idx + 1, base_idx + 2])

                    f.read(2)
                except:
                    break

        model.vertices = vertices
        model.triangles = triangles
        model.normals = normals if normals else self._compute_normals(vertices, triangles)

        return model

    def _parse_ascii_stl(self, file_path: str) -> ModelData:
        """解析ASCII STL"""
        model = ModelData()
        model.format = "STL"
        model.name = os.path.basename(file_path)

        vertices = []
        normals = []
        triangles = []

        current_normal = [0, 0, 1]
        current_face_verts = []

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip().lower()
                
                if not line:
                    continue

                if line.startswith('facet normal'):
                    parts = line.split()
                    if len(parts) >= 5:
                        current_normal = [float(parts[2]), float(parts[3]), float(parts[4])]
                        current_face_verts = []

                elif line.startswith('vertex'):
                    parts = line.split()
                    if len(parts) >= 4:
                        v = [float(parts[1]), float(parts[2]), float(parts[3])]
                        current_face_verts.append(v)

                elif line.startswith('endloop'):
                    if len(current_face_verts) >= 3:
                        base_idx = len(vertices)
                        vertices.extend(current_face_verts[:3])
                        triangles.append([base_idx, base_idx + 1, base_idx + 2])
                        normals.append(current_normal)
                        if len(current_face_verts) > 3:
                            for i in range(3, len(current_face_verts)):
                                base_idx = len(vertices)
                                vertices.append(current_face_verts[i])
                                vertices.append(current_face_verts[0])
                                vertices.append(current_face_verts[i - 1])
                                triangles.append([base_idx, base_idx + 1, base_idx + 2])

        model.vertices = vertices
        model.triangles = triangles
        model.normals = normals if normals else self._compute_normals(vertices, triangles)

        return model
