"""
OBJ模型加载器
支持带材质和纹理的OBJ文件
"""

import os
from typing import Optional, List, Dict
from core.base_loader import BaseModelLoader, ModelData


class OBJLoader(BaseModelLoader):
    """OBJ格式模型加载器"""

    def supports_format(self, extension: str) -> bool:
        """检查是否支持OBJ格式"""
        return extension.lower() == '.obj'

    def get_supported_formats(self) -> List[str]:
        """获取支持的格式列表"""
        return ['.obj']

    def load(self, file_path: str) -> Optional[ModelData]:
        """加载OBJ文件"""
        if not os.path.exists(file_path):
            return None

        try:
            return self._parse_obj(file_path)
        except Exception as e:
            print(f"OBJ load error: {e}")
            return None

    def _parse_obj(self, file_path: str) -> ModelData:
        """解析OBJ文件"""
        model = ModelData()
        model.format = "OBJ"
        model.name = os.path.basename(file_path)

        vertices = []
        normals = []
        texcoords = []
        triangles = []
        colors = []

        # 材质信息
        mtl_colors = {}
        current_mtl = None
        current_color = [0.7, 0.7, 0.7]

        # 尝试加载MTL文件
        mtl_path = file_path.replace('.obj', '.mtl')
        if os.path.exists(mtl_path):
            mtl_colors = self._parse_mtl(mtl_path)

        # 解析OBJ文件
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
                    # 顶点
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    vertices.append([x, y, z])
                    # 检查是否有顶点颜色 (v x y z r g b)
                    if len(parts) >= 7:
                        r, g, b = float(parts[4]), float(parts[5]), float(parts[6])
                        colors.append([r, g, b])

                elif cmd == 'vn':
                    # 法线
                    normals.append([float(parts[1]), float(parts[2]), float(parts[3])])

                elif cmd == 'vt':
                    # 纹理坐标
                    s = float(parts[1])
                    t = 1.0 - float(parts[2]) if len(parts) > 2 else 0.0
                    texcoords.append([s, t])

                elif cmd == 'f':
                    # 面
                    face = []
                    tex_indices = []
                    for p in parts[1:]:
                        indices = p.split('/')
                        v_idx = int(indices[0]) - 1  # OBJ索引从1开始
                        face.append(v_idx)
                        if len(indices) > 1 and indices[1]:
                            tex_indices.append(int(indices[1]) - 1)
                    if len(face) >= 3:
                        for i in range(1, len(face) - 1):
                            triangles.append([face[0], face[i], face[i+1]])
                            if tex_indices:
                                model.texcoords.extend([texcoords[tex_indices[0]],
                                                     texcoords[tex_indices[i]],
                                                     texcoords[tex_indices[i+1]]])

                elif cmd == 'usemtl':
                    # 使用材质
                    current_mtl = parts[1] if len(parts) > 1 else None
                    if current_mtl in mtl_colors:
                        current_color = mtl_colors[current_mtl]

                elif cmd == 'mtllib':
                    # 材质库文件
                    mtl_file = parts[1]
                    mtl_full_path = os.path.join(os.path.dirname(file_path), mtl_file)
                    if os.path.exists(mtl_full_path):
                        mtl_colors.update(self._parse_mtl(mtl_full_path))

        model.vertices = vertices
        model.triangles = triangles
        model.normals = normals if normals else self._compute_normals(vertices, triangles)
        model.colors = colors
        
        # 如果没有顶点颜色但有材质颜色，应用材质颜色
        if not colors and mtl_colors:
            model.colors = [current_color] * len(vertices)

        # 设置纹理路径
        if mtl_colors:
            for mtl, color in mtl_colors.items():
                # 尝试查找纹理文件
                tex_path = file_path.replace('.obj', '_diffuse.png')
                if os.path.exists(tex_path):
                    model.texture_path = tex_path
                    break
                tex_path = file_path.replace('.obj', '_diffuse.jpg')
                if os.path.exists(tex_path):
                    model.texture_path = tex_path
                    break

        return model

    def _parse_mtl(self, mtl_path: str) -> Dict[str, List[float]]:
        """解析MTL材质文件"""
        colors = {}
        current_name = None

        try:
            with open(mtl_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split()
                    if not parts:
                        continue

                    if parts[0] == 'newmtl':
                        current_name = parts[1] if len(parts) > 1 else None
                    elif parts[0] == 'Kd' and current_name:
                        # 漫反射颜色
                        r, g, b = float(parts[1]), float(parts[2]), float(parts[3])
                        colors[current_name] = [r, g, b]
                    elif parts[0] == 'map_Kd' and current_name:
                        # 纹理贴图路径
                        tex_path = parts[1]
                        colors[current_name] = [0.8, 0.8, 0.8]
        except Exception as e:
            print(f"MTL parse error: {e}")

        return colors
