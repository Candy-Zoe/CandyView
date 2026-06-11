"""
模型加载器管理器
统一管理所有模型加载器，Open3D作为优先保底方案
"""

import os
import numpy as np
from typing import Optional, List, Tuple

try:
    import open3d as o3d
    HAS_OPEN3D = True
except ImportError:
    HAS_OPEN3D = False

from core.base_loader import ModelData
from core.ply_loader import PLYLoader
from core.obj_loader import OBJLoader
from core.stl_loader import STLLoader
from core.gltf_loader import GLTFLoader


class ModelInfo:
    def __init__(self):
        self.vertices = 0
        self.triangles = 0
        self.has_texture = False
        self.has_normals = False
        self.has_vertex_colors = False
        self.bounding_box_min = (0, 0, 0)
        self.bounding_box_max = (0, 0, 0)
        self.bounding_box_size = (0, 0, 0)
        self.center = (0, 0, 0)
        self.file_path = ""
        self.format = ""


class ModelLoader:
    """模型加载器管理器"""

    def __init__(self):
        self.loaders = [PLYLoader(), OBJLoader(), STLLoader(), GLTFLoader()]

    def load_model(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        model_data = None
        error_msg = ""

        # 策略1: 优先尝试Open3D（最可靠）
        if HAS_OPEN3D:
            try:
                model_data = self._load_with_open3d(file_path, ext)
                if model_data and model_data.vertices:
                    info = self._get_model_info(model_data, file_path, ext)
                    return model_data, info
            except Exception as e:
                error_msg = f"Open3D: {e}"
                print(f"[WARN] Open3D load failed: {e}")

        # 策略2: 尝试自定义加载器
        for loader in self.loaders:
            if loader.supports_format(ext):
                try:
                    model_data = loader.load(file_path)
                    if model_data and model_data.vertices:
                        info = self._get_model_info(model_data, file_path, ext)
                        return model_data, info
                except Exception as e:
                    print(f"[WARN] {loader.__class__.__name__} failed: {e}")
                    continue

        raise ValueError(f"Failed to load model: {error_msg}")

    def _load_with_open3d(self, file_path, ext):
        """使用Open3D加载，支持多种格式"""
        mesh = None
        pcd = None

        # 尝试多种Open3D加载策略
        strategies = [
            lambda: o3d.io.read_triangle_mesh(file_path, True, True),
            lambda: o3d.io.read_triangle_mesh(file_path, True, False),
            lambda: o3d.io.read_triangle_mesh(file_path),
        ]

        for strat in strategies:
            try:
                m = strat()
                if m and m.has_vertices():
                    mesh = m
                    break
            except:
                continue

        # 如果网格加载失败，尝试点云
        if mesh is None or not mesh.has_vertices():
            try:
                pcd = o3d.io.read_point_cloud(file_path)
                if pcd and pcd.has_points():
                    # 点云转网格
                    pcd.estimate_normals()
                    distances = pcd.compute_nearest_neighbor_distance()
                    if len(distances) > 0:
                        avg_dist = float(np.mean(np.asarray(distances)))
                        r = max(avg_dist * 3, 0.001)
                        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
                            pcd, o3d.utility.DoubleVector([r, r * 2])
                        )
            except:
                pass

        if mesh is None or not mesh.has_vertices():
            return None

        # 转换为ModelData
        model = ModelData()
        model.format = ext.upper().replace('.', '')
        model.name = os.path.basename(file_path)

        vertices = np.asarray(mesh.vertices)
        model.vertices = vertices.tolist()

        if mesh.has_triangles():
            triangles = np.asarray(mesh.triangles)
            model.triangles = triangles.tolist()
        else:
            model.triangles = []

        if mesh.has_vertex_normals():
            model.normals = np.asarray(mesh.vertex_normals).tolist()

        if mesh.has_vertex_colors():
            colors = np.asarray(mesh.vertex_colors)
            if colors.max() > 1.5:
                colors = colors / 255.0
            model.colors = colors.tolist()

        model.texture_path = ""
        return model

    def _get_model_info(self, model_data, file_path, ext):
        info = ModelInfo()
        info.file_path = file_path
        info.format = ext.upper().replace('.', '')
        info.vertices = len(model_data.vertices)
        info.triangles = len(model_data.triangles)
        info.has_texture = bool(model_data.texture_path)
        info.has_normals = bool(model_data.normals)
        info.has_vertex_colors = bool(model_data.colors)

        if model_data.vertices:
            vertices = np.array(model_data.vertices)
            min_v = vertices.min(axis=0)
            max_v = vertices.max(axis=0)
            info.bounding_box_min = tuple(min_v)
            info.bounding_box_max = tuple(max_v)
            info.bounding_box_size = tuple(max_v - min_v)
            info.center = tuple((min_v + max_v) / 2)

        return info

    def get_format_filters(self):
        return [
            "3D Model Files (*.ply *.obj *.stl *.glb *.gltf)",
            "PLY Files (*.ply)",
            "OBJ Files (*.obj)",
            "STL Files (*.stl)",
            "GLTF Files (*.gltf *.glb)",
            "All Files (*.*)"
        ]
