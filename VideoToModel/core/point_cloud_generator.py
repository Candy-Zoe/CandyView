"""
点云生成器
"""

import numpy as np
import open3d as o3d


class PointCloudGenerator:
    def __init__(self):
        pass

    def create_from_depth(self, image, depth, scale=0.2):
        """
        从深度图创建点云
        
        参数:
            image: RGB图像 (H, W, 3)
            depth: 深度图 (H, W)
            scale: 深度缩放因子
        
        返回:
            pcd: Open3D点云对象
        """
        h, w = image.shape[:2]
        
        xx, yy = np.meshgrid(np.arange(w), np.arange(h))
        
        xx = (xx - w / 2) * scale / w
        yy = (yy - h / 2) * scale / h
        zz = depth * scale * 2
        
        points = np.stack([xx.flatten(), -yy.flatten(), zz.flatten()], axis=1)
        colors = image.reshape(-1, 3) / 255.0
        
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd.colors = o3d.utility.Vector3dVector(colors)
        
        return pcd

    def downsample(self, pcd, voxel_size=0.01):
        """体素下采样"""
        return pcd.voxel_down_sample(voxel_size=voxel_size)

    def estimate_normals(self, pcd, voxel_size=0.01):
        """估计法线"""
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=voxel_size * 5, max_nn=30
            )
        )
        return pcd

    def remove_outliers(self, pcd, nb_neighbors=20, std_ratio=2.0):
        """移除离群点"""
        pcd, _ = pcd.remove_statistical_outlier(
            nb_neighbors=nb_neighbors, std_ratio=std_ratio
        )
        return pcd
