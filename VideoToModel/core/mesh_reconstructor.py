"""
网格重建器
"""

import numpy as np
import open3d as o3d


class MeshReconstructor:
    def __init__(self):
        pass

    def ball_pivoting(self, pcd, voxel_size=0.01):
        """
        Ball Pivoting算法重建网格
        
        参数:
            pcd: 点云对象
            voxel_size: 体素大小
        
        返回:
            mesh: 网格对象
        """
        distances = pcd.compute_nearest_neighbor_distance()
        avg_dist = np.mean(np.asarray(distances))
        
        radii = [
            avg_dist * 1.5,
            avg_dist * 3,
            avg_dist * 6,
            avg_dist * 12
        ]
        
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd, o3d.utility.DoubleVector(radii)
        )
        
        if mesh is not None:
            mesh = self._post_process(mesh)
        
        return mesh

    def poisson(self, pcd, depth=9):
        """
        Poisson重建
        
        参数:
            pcd: 点云对象
            depth: 重建深度
        
        返回:
            mesh: 网格对象
        """
        try:
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd, depth=depth, width=0, scale=1.2
            )
            
            densities = np.asarray(densities)
            threshold = np.quantile(densities, 0.03)
            mesh.remove_vertices_by_mask(densities < threshold)
            
            mesh = self._post_process(mesh)
            return mesh
        except Exception as e:
            print(f"Poisson重建失败，使用Ball Pivoting: {e}")
            return self.ball_pivoting(pcd)

    def _post_process(self, mesh):
        """网格后处理"""
        mesh.remove_degenerate_triangles()
        mesh.remove_duplicated_triangles()
        mesh.remove_unreferenced_vertices()
        mesh.compute_vertex_normals()
        
        return mesh

    def save(self, mesh, path):
        """保存网格到文件"""
        if mesh is not None:
            o3d.io.write_triangle_mesh(path, mesh)
            return True
        return False
