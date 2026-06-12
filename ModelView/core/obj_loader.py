"""
OBJ模型加载器
支持带材质和纹理的OBJ文件
"""

import os
import numpy as np
from typing import Optional, List, Dict, Tuple
from core.base_loader import BaseModelLoader, ModelData


class OBJLoader(BaseModelLoader):
    """OBJ格式模型加载器 - 增强版"""

    def supports_format(self, extension: str) -> bool:
        return extension.lower() == '.obj'

    def get_supported_formats(self) -> List[str]:
        return ['.obj']

    def load(self, file_path: str) -> Optional[ModelData]:
        if not os.path.exists(file_path):
            return None

        try:
            return self._parse_obj(file_path)
        except Exception as e:
            print(f"OBJ load error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_obj(self, file_path: str) -> ModelData:
        """解析OBJ文件"""
        model = ModelData()
        model.format = "OBJ"
        model.name = os.path.basename(file_path)

        # 数据存储
        vertices = []
        normals = []
        texcoords = []
        triangles = []
        colors = []

        # 用于去重的顶点缓存
        vertex_map = {}  # (v_idx, vn_idx, vt_idx) -> new_idx
        unique_vertices = []
        unique_normals = []
        unique_texcoords = []
        unique_colors = []

        # 材质信息
        mtl_data = {}
        current_mtl = None
        current_color = [0.75, 0.75, 0.8]

        base_dir = os.path.dirname(file_path)

        # 解析MTL文件
        mtl_path = file_path.replace('.obj', '.mtl')
        if os.path.exists(mtl_path):
            mtl_data = self._parse_mtl(mtl_path)

        # OBJ数据
        raw_vertices = []
        raw_normals = []
        raw_texcoords = []

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split()
                if not parts:
                    continue

                cmd = parts[0]

                if cmd == 'v':
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    raw_vertices.append([x, y, z])
                    if len(parts) >= 7:
                        r, g, b = float(parts[4]), float(parts[5]), float(parts[6])
                        colors.append([min(1.0, max(0.0, r)), min(1.0, max(0.0, g)), min(1.0, max(0.0, b))])
                    else:
                        colors.append(None)

                elif cmd == 'vn':
                    nx, ny, nz = float(parts[1]), float(parts[2]), float(parts[3])
                    raw_normals.append([nx, ny, nz])

                elif cmd == 'vt':
                    s = float(parts[1])
                    t = 1.0 - float(parts[2]) if len(parts) > 2 else 0.0
                    raw_texcoords.append([s, t])

                elif cmd == 'f':
                    face_verts = []
                    face_texcoords = []
                    face_normals = []

                    for p in parts[1:]:
                        indices = p.split('/')
                        v_idx = int(indices[0]) - 1
                        vt_idx = int(indices[1]) - 1 if len(indices) > 1 and indices[1] else -1
                        vn_idx = int(indices[2]) - 1 if len(indices) > 2 and indices[2] else -1

                        key = (v_idx, vn_idx, vt_idx)
                        if key not in vertex_map:
                            v = raw_vertices[v_idx] if v_idx < len(raw_vertices) else [0, 0, 0]
                            vn = raw_normals[vn_idx] if vn_idx >= 0 and vn_idx < len(raw_normals) else [0, 0, 1]
                            vt = raw_texcoords[vt_idx] if vt_idx >= 0 and vt_idx < len(raw_texcoords) else [0, 0]

                            idx = len(unique_vertices)
                            vertex_map[key] = idx
                            unique_vertices.append(v)
                            unique_normals.append(vn)
                            unique_texcoords.append(vt)
                            if v_idx < len(colors) and colors[v_idx] is not None:
                                unique_colors.append(colors[v_idx])
                            else:
                                unique_colors.append(current_color)

                        face_verts.append(vertex_map[key])

                    if len(face_verts) >= 3:
                        for i in range(1, len(face_verts) - 1):
                            triangles.append([face_verts[0], face_verts[i], face_verts[i + 1]])

                elif cmd == 'usemtl':
                    if len(parts) > 1:
                        current_mtl = parts[1]
                        if current_mtl in mtl_data:
                            current_color = mtl_data[current_mtl].get('Kd', current_color)

                elif cmd == 'mtllib':
                    mtl_file = parts[1]
                    mtl_full_path = os.path.join(base_dir, mtl_file) if base_dir else mtl_file
                    if os.path.exists(mtl_full_path):
                        mtl_data.update(self._parse_mtl(mtl_full_path))

        model.vertices = unique_vertices
        model.triangles = triangles
        model.normals = unique_normals if unique_normals else self._compute_normals(unique_vertices, triangles)
        model.texcoords = unique_texcoords if unique_texcoords else None
        model.colors = unique_colors if any(c is not None for c in unique_colors) else None

        # 查找纹理文件
        for ext in ['.png', '.jpg', '.jpeg', '.bmp']:
            tex_path = os.path.join(base_dir, model.name.replace('.obj', f'_diffuse{ext}'))
            if os.path.exists(tex_path):
                model.texture_path = tex_path
                break
            tex_path = os.path.join(base_dir, model.name.replace('.obj', f'_baseColor{ext}'))
            if os.path.exists(tex_path):
                model.texture_path = tex_path
                break

        return model

    def _parse_mtl(self, mtl_path: str) -> Dict[str, Dict]:
        """解析MTL材质文件"""
        materials = {}
        current_name = None
        current_data = {}

        try:
            with open(mtl_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split()
                    if not parts:
                        continue

                    cmd = parts[0]

                    if cmd == 'newmtl':
                        if current_name:
                            materials[current_name] = current_data
                        current_name = parts[1] if len(parts) > 1 else None
                        current_data = {}

                    elif cmd == 'Kd' and current_name:
                        current_data['Kd'] = [float(parts[1]), float(parts[2]), float(parts[3])]

                    elif cmd == 'Ks' and current_name:
                        current_data['Ks'] = [float(parts[1]), float(parts[2]), float(parts[3])]

                    elif cmd == 'Ka' and current_name:
                        current_data['Ka'] = [float(parts[1]), float(parts[2]), float(parts[3])]

                    elif cmd == 'map_Kd' and current_name and len(parts) > 1:
                        current_data['map_Kd'] = parts[1]

                    elif cmd == 'Ns' and current_name and len(parts) > 1:
                        current_data['Ns'] = float(parts[1])

                    elif cmd == 'd' and current_name and len(parts) > 1:
                        current_data['d'] = float(parts[1])

                if current_name:
                    materials[current_name] = current_data

        except Exception as e:
            print(f"MTL parse error: {e}")

        return materials
