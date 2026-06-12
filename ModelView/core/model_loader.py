"""
模型加载器管理器
协调各个加载器并在必要时使用Open3D保底
"""

import os
import numpy as np
from typing import Optional, Tuple
from core.base_loader import ModelData
from core.ply_loader import PLYLoader
from core.obj_loader import OBJLoader
from core.stl_loader import STLLoader
from core.gltf_loader import GLTFLoader


class ModelLoader:
    """模型加载器管理器"""

    def __init__(self):
        self.loaders = [
            PLYLoader(),
            OBJLoader(),
            STLLoader(),
            GLTFLoader()
        ]

    def load(self, file_path):
        """兼容性别名"""
        model, info = self.load_model(file_path)
        return model

    def load_model(self, file_path) -> Tuple[Optional[ModelData], dict]:
        """
        加载模型文件

        Returns:
            (ModelData, info_dict) - 模型数据和信息
        """
        if not os.path.exists(file_path):
            return None, {"error": "File not found"}

        ext = os.path.splitext(file_path)[1].lower()
        info = {"format": ext, "loader": "unknown"}

        # 1. 尝试使用自定义加载器
        for loader in self.loaders:
            if loader.supports_format(ext):
                info["loader"] = loader.__class__.__name__
                model = loader.load(file_path)
                if model and model.vertices:
                    model.normalize()
                    return model, info

        # 2. 使用Open3D保底
        return self._load_with_open3d(file_path, info)

    def _load_with_open3d(self, file_path: str, info: dict) -> Tuple[Optional[ModelData], dict]:
        """使用Open3D加载模型"""
        try:
            import open3d as o3d

            info["loader"] = "Open3D"

            # 尝试加载网格
            try:
                mesh = o3d.io.read_triangle_mesh(file_path)
                if mesh and len(mesh.vertices) > 0:
                    info["mesh_loaded"] = True
                    return self._open3d_mesh_to_model(mesh, info), info
            except:
                pass

            # 尝试加载点云并重建
            try:
                pcd = o3d.io.read_point_cloud(file_path)
                if pcd and len(pcd.points) > 0:
                    info["point_cloud_loaded"] = True
                    mesh = pcd.compute_convex_hull()[0]
                    if len(mesh.vertices) > 0:
                        return self._open3d_mesh_to_model(mesh, info), info
            except:
                pass

            info["error"] = "Open3D failed to load"
            return None, info

        except ImportError:
            info["error"] = "Open3D not installed"
            return None, info
        except Exception as e:
            info["error"] = str(e)
            return None, info

    def _open3d_mesh_to_model(self, mesh, info: dict) -> ModelData:
        """将Open3D网格转换为ModelData"""
        model = ModelData()

        vertices = np.asarray(mesh.vertices)
        triangles = np.asarray(mesh.triangles) if mesh.has_triangles() else []

        model.vertices = vertices.tolist()
        model.triangles = triangles.tolist() if len(triangles) > 0 else []

        if mesh.has_vertex_colors():
            colors = np.asarray(mesh.vertex_colors)
            if colors.max() > 1.5:
                colors = colors / 255.0
            model.colors = colors.tolist()
        elif mesh.has_textures():
            model.texcoords = np.asarray(mesh.texture_coords).tolist() if hasattr(mesh, 'texture_coords') else None

        if mesh.has_triangles() and len(triangles) > 0:
            model.normals = self._compute_normals(vertices, triangles)

        model.format = "Open3D"
        info["vertices"] = len(model.vertices)
        info["triangles"] = len(model.triangles)

        return model

    def _compute_normals(self, vertices, triangles):
        """计算顶点法线"""
        normals = [[0.0, 0.0, 0.0] for _ in range(len(vertices))]

        for tri in triangles:
            if len(tri) >= 3:
                i, j, k = tri[0], tri[1], tri[2]
                v1 = vertices[j] - vertices[i]
                v2 = vertices[k] - vertices[i]

                normal = np.cross(v1, v2)
                length = np.linalg.norm(normal)
                if length > 0.0001:
                    normal = normal / length

                for idx in tri[:3]:
                    normals[idx] += normal

        for i in range(len(normals)):
            length = np.linalg.norm(normals[i])
            if length > 0.0001:
                normals[i] = (normals[i] / length).tolist()
            else:
                normals[i] = [0.0, 0.0, 1.0]

        return normals

    @staticmethod
    def get_format_filters():
        """获取文件对话框过滤器"""
        return [
            "All Supported (*.ply *.obj *.stl *.gltf *.glb)",
            "PLY Files (*.ply)",
            "OBJ Files (*.obj)",
            "STL Files (*.stl)",
            "GLTF Files (*.gltf *.glb)",
            "All Files (*.*)"
        ]
