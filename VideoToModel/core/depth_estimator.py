"""
深度估计器 - 混合策略
优先使用深度学习，降级到传统算法
"""

import numpy as np
import cv2
import subprocess
import sys
import json
import base64
import io
from PIL import Image
from scipy.ndimage import gaussian_filter, sobel
from scipy import ndimage
import os


class DepthEstimator:
    def __init__(self):
        self._device = None
        self._midas_available = None

    def _check_midas_available(self):
        """检测MiDaS是否可用（通过子进程测试）"""
        if self._midas_available is not None:
            return self._midas_available
        
        try:
            worker_path = os.path.join(os.path.dirname(__file__), 'midas_worker.py')
            test_image = np.zeros((100, 100, 3), dtype=np.uint8)
            _, buffer = cv2.imencode('.png', cv2.cvtColor(test_image, cv2.COLOR_RGB2BGR))
            encoded = base64.b64encode(buffer).decode('utf-8')
            
            result = subprocess.run(
                [sys.executable, worker_path, encoded],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    if data.get('success'):
                        self._midas_available = True
                        print("[MiDaS] 检测成功")
                        return True
                except:
                    pass
            
            print(f"[MiDaS] 检测失败: {result.stderr}")
            self._midas_available = False
            return False
        except Exception as e:
            print(f"[提示] 深度学习不可用: {e}")
            self._midas_available = False
            return False

    def has_midas(self):
        """检查MiDaS是否可能可用"""
        return self._check_midas_available()

    def get_status_text(self):
        """返回可读的状态文本"""
        if self._midas_available is None:
            return "ℹ 点击转换时会自动检测深度学习支持"
        if self._midas_available:
            return "✓ MiDaS深度学习可用 (选择 auto 或 midas 算法启用)"
        return "⚠ 深度学习未启用，当前使用传统算法"

    def estimate(self, image, method='auto', **kwargs):
        """
        估计深度图
        
        参数:
            image: RGB图像 (H, W, 3)
            method: 算法选择
                - 'auto': 自动选择（优先MiDaS）
                - 'midas': 使用MiDaS深度学习
                - 'fusion': 智能融合（多种传统算法）
                - 'laplacian': 拉普拉斯算子
                - 'gradient': 梯度算子
                - 'canny': Canny边缘
                - 'harris': Harris角点
                - 'sift': SIFT特征
                - 'bilateral': 双边滤波
                - 'guided': 导向滤波
                - 'multiscale': 多尺度融合
        
        返回:
            depth: 深度图 (H, W)
        """
        if method == 'auto':
            if self.has_midas():
                return self._estimate_midas(image)
            else:
                return self._estimate_fusion(image, **kwargs)
        
        methods = {
            'midas': self._estimate_midas,
            'fusion': self._estimate_fusion,
            'laplacian': self._estimate_laplacian,
            'gradient': self._estimate_gradient,
            'canny': self._estimate_canny,
            'harris': self._estimate_harris,
            'sift': self._estimate_sift,
            'bilateral': self._estimate_bilateral,
            'guided': self._estimate_guided,
            'multiscale': self._estimate_multiscale,
        }
        
        if method in methods:
            return methods[method](image, **kwargs)
        else:
            return self._estimate_fusion(image, **kwargs)

    def _estimate_midas(self, image):
        """使用子进程运行MiDaS深度学习模型"""
        if not self._check_midas_available():
            return self._estimate_fusion(image)
        
        try:
            worker_path = os.path.join(os.path.dirname(__file__), 'midas_worker.py')
            
            img_pil = Image.fromarray(image)
            buffer = io.BytesIO()
            img_pil.save(buffer, format='PNG')
            encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            result = subprocess.run(
                [sys.executable, worker_path, encoded],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data.get('success'):
                    depth = np.array(data['depth'])
                    return depth
            
            print(f"[MiDaS] 推理失败，降级到传统算法: {result.stderr}")
            return self._estimate_fusion(image)
        except Exception as e:
            print(f"[MiDaS] 推理失败，降级到传统算法: {e}")
            return self._estimate_fusion(image)

    def _estimate_fusion(self, image, sigma=2.0):
        """智能融合深度估计"""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float64)
        gray_blur = gaussian_filter(gray, sigma=sigma)

        grad = self._compute_gradient(gray_blur, sigma)
        lap = self._compute_laplacian(gray_blur, sigma)
        canny = self._compute_canny(gray, sigma)
        struct = self._compute_structure_tensor(gray_blur, sigma)
        harris = self._compute_harris(gray_blur, sigma)
        sift = self._compute_sift_response(image, sigma)

        depth = 0.25 * grad + 0.15 * lap + 0.15 * canny + 0.15 * struct + 0.15 * harris + 0.15 * sift
        depth /= depth.max() + 1e-10

        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        value_channel = hsv[:, :, 2].astype(np.float64) / 255.0
        depth = depth * 0.6 + (1.0 - value_channel) * 0.4

        depth = gaussian_filter(depth, sigma=sigma * 0.3)
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)

        return 1.0 - depth

    def _estimate_laplacian(self, image, sigma=2.0):
        """拉普拉斯算子"""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float64)
        gray_blur = gaussian_filter(gray, sigma=sigma)
        laplacian = cv2.Laplacian(gray_blur, cv2.CV_64F, ksize=5)
        depth = gaussian_filter(np.abs(laplacian), sigma=sigma * 0.5)
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)
        return 1.0 - depth

    def _estimate_gradient(self, image, sigma=2.0):
        """梯度算子"""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float64)
        gray_blur = gaussian_filter(gray, sigma=sigma)
        sobelx = cv2.Sobel(gray_blur, cv2.CV_64F, 1, 0, ksize=5)
        sobely = cv2.Sobel(gray_blur, cv2.CV_64F, 0, 1, ksize=5)
        magnitude = np.sqrt(sobelx**2 + sobely**2)
        depth = gaussian_filter(magnitude, sigma=sigma * 0.5)
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)
        return 1.0 - depth

    def _estimate_canny(self, image, sigma=2.0):
        """Canny边缘"""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float64)
        edges = cv2.Canny(gray.astype(np.uint8), 50, 150)
        depth = gaussian_filter(edges.astype(np.float64) / 255.0, sigma=sigma)
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)
        return 1.0 - depth

    def _estimate_harris(self, image, sigma=2.0):
        """Harris角点"""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float64)
        gray_blur = gaussian_filter(gray, sigma=sigma)
        Ix = sobel(gray_blur, axis=1)
        Iy = sobel(gray_blur, axis=0)
        Ixx = gaussian_filter(Ix**2, sigma=sigma)
        Iyy = gaussian_filter(Iy**2, sigma=sigma)
        Ixy = gaussian_filter(Ix * Iy, sigma=sigma)
        det = Ixx * Iyy - Ixy**2
        trace = Ixx + Iyy + 1e-10
        depth = det / trace
        depth = gaussian_filter(depth, sigma=sigma * 0.5)
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)
        return 1.0 - depth

    def _estimate_sift(self, image, sigma=2.0):
        """SIFT特征响应"""
        try:
            sift = cv2.SIFT_create()
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            kp, des = sift.detectAndCompute(gray, None)
            
            depth = np.zeros(gray.shape, dtype=np.float64)
            if kp:
                for p in kp:
                    x, y = int(p.pt[0]), int(p.pt[1])
                    if 0 <= y < depth.shape[0] and 0 <= x < depth.shape[1]:
                        depth[y, x] += p.response
            
            depth = gaussian_filter(depth, sigma=sigma * 2)
            depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)
            return 1.0 - depth
        except:
            return self._estimate_harris(image, sigma)

    def _estimate_bilateral(self, image, sigma=2.0):
        """双边滤波保持边缘"""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float64)
        bilateral = cv2.bilateralFilter(gray.astype(np.uint8), 9, 75, 75)
        laplacian = cv2.Laplacian(bilateral, cv2.CV_64F, ksize=5)
        depth = gaussian_filter(np.abs(laplacian), sigma=sigma * 0.5)
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)
        return 1.0 - depth

    def _estimate_guided(self, image, sigma=2.0):
        """导向滤波增强"""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float64)
        gray_blur = gaussian_filter(gray, sigma=sigma)
        
        eps = 0.01
        r = 4
        mean_I = cv2.boxFilter(gray_blur, cv2.CV_64F, (r, r))
        mean_p = cv2.boxFilter(gray_blur, cv2.CV_64F, (r, r))
        mean_Ip = cv2.boxFilter(gray_blur * gray_blur, cv2.CV_64F, (r, r))
        cov_Ip = mean_Ip - mean_I * mean_p
        
        mean_II = cv2.boxFilter(gray_blur * gray_blur, cv2.CV_64F, (r, r))
        var_I = mean_II - mean_I * mean_I
        
        a = cov_Ip / (var_I + eps)
        b = mean_p - a * mean_I
        
        mean_a = cv2.boxFilter(a, cv2.CV_64F, (r, r))
        mean_b = cv2.boxFilter(b, cv2.CV_64F, (r, r))
        
        guided = mean_a * gray_blur + mean_b
        laplacian = cv2.Laplacian(guided, cv2.CV_64F, ksize=5)
        depth = gaussian_filter(np.abs(laplacian), sigma=sigma * 0.5)
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)
        return 1.0 - depth

    def _estimate_multiscale(self, image, sigma=2.0):
        """多尺度特征融合"""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float64)
        
        depths = []
        for scale in [0.5, 1.0, 2.0]:
            scaled_sigma = sigma * scale
            gray_blur = gaussian_filter(gray, sigma=scaled_sigma)
            laplacian = cv2.Laplacian(gray_blur, cv2.CV_64F, ksize=5)
            depth = gaussian_filter(np.abs(laplacian), sigma=scaled_sigma * 0.5)
            depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)
            depths.append(depth)
        
        depth = np.mean(depths, axis=0)
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)
        return 1.0 - depth

    def _compute_gradient(self, gray, sigma):
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=5)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=5)
        return np.sqrt(sobelx**2 + sobely**2)

    def _compute_laplacian(self, gray, sigma):
        return np.abs(cv2.Laplacian(gray, cv2.CV_64F, ksize=5))

    def _compute_canny(self, gray, sigma):
        edges = cv2.Canny(gray.astype(np.uint8), 50, 150)
        return edges.astype(np.float64) / 255.0

    def _compute_structure_tensor(self, gray, sigma):
        Ix = sobel(gray, axis=1)
        Iy = sobel(gray, axis=0)
        Ixx = gaussian_filter(Ix**2, sigma=sigma)
        Iyy = gaussian_filter(Iy**2, sigma=sigma)
        Ixy = gaussian_filter(Ix * Iy, sigma=sigma)
        det = Ixx * Iyy - Ixy**2
        trace = Ixx + Iyy + 1e-10
        return det / trace

    def _compute_harris(self, gray, sigma):
        Ix = sobel(gray, axis=1)
        Iy = sobel(gray, axis=0)
        Ixx = gaussian_filter(Ix**2, sigma=sigma)
        Iyy = gaussian_filter(Iy**2, sigma=sigma)
        Ixy = gaussian_filter(Ix * Iy, sigma=sigma)
        det = Ixx * Iyy - Ixy**2
        trace = Ixx + Iyy + 1e-10
        return det / trace

    def _compute_sift_response(self, image, sigma):
        try:
            sift = cv2.SIFT_create()
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            kp, _ = sift.detectAndCompute(gray, None)
            depth = np.zeros(gray.shape, dtype=np.float64)
            if kp:
                for p in kp:
                    x, y = int(p.pt[0]), int(p.pt[1])
                    if 0 <= y < depth.shape[0] and 0 <= x < depth.shape[1]:
                        depth[y, x] += p.response
            return depth
        except:
            return np.zeros((image.shape[0], image.shape[1]))