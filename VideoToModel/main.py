"""
VideoToModel - 图片/视频转3D模型
优化版 - 改进深度估计和网格重建
"""

import sys
import os
import traceback
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QSpinBox, QDoubleSpinBox,
    QProgressBar, QMessageBox, QTextEdit, QGroupBox, QFormLayout,
    QCheckBox, QSlider, QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
import open3d as o3d


class ConversionThread(QThread):
    """转换线程"""
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(object, object)
    error = pyqtSignal(str)

    def __init__(self, input_path, params):
        super().__init__()
        self.input_path = input_path
        self.params = params

    def run(self):
        try:
            self.progress.emit(5, "加载输入...")

            depth_scale = float(self.params['depth_scale'])
            sigma = float(self.params['sigma'])
            voxel_size = float(self.params['voxel_size'])
            mesh_mode = self.params['mesh_mode']  # 'ball' or 'poisson'
            output_name = self.params['output_name']

            ext = os.path.splitext(self.input_path)[1].lower()

            if ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                self.progress.emit(10, "读取视频帧...")
                image = self._video_to_image(self.input_path)
            else:
                self.progress.emit(10, "加载图片...")
                img = Image.open(self.input_path)
                image = np.array(img.convert('RGB'))

            if image is None or image.size == 0:
                self.error.emit("图像加载失败")
                return

            self.progress.emit(25, "估计深度...")
            depth = self._estimate_depth(image, sigma)

            self.progress.emit(50, "生成点云...")
            pcd = self._create_point_cloud(image, depth, depth_scale)

            self.progress.emit(70, "下采样...")
            pcd_down = pcd.voxel_down_sample(voxel_size=voxel_size)

            self.progress.emit(80, "估计法线...")
            pcd_down.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size * 5, max_nn=30))

            self.progress.emit(90, "生成网格...")
            if mesh_mode == 'ball':
                mesh = self._ball_pivoting(pcd_down, voxel_size)
            else:
                mesh = self._poisson_reconstruction(pcd_down)

            self.progress.emit(95, "导出PLY...")
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)

            output_path = os.path.join(output_dir, output_name)
            if mesh is not None:
                mesh.compute_vertex_normals()
                o3d.io.write_triangle_mesh(output_path, mesh)
            else:
                o3d.io.write_point_cloud(output_path, pcd)

            self.progress.emit(100, "完成!")
            self.finished_ok.emit(pcd, mesh)

        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))

    def _video_to_image(self, video_path):
        """从视频提取帧"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        mid = total // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid)

        ret, frame = cap.read()
        cap.release()

        if not ret:
            return None

        # BGR转RGB
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def _estimate_depth(self, image, sigma):
        """
        改进的深度估计
        使用结构张量分析 + 多尺度边缘融合
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        gray = gray.astype(np.float64)

        # 高斯平滑
        gray = gaussian_filter(gray, sigma=sigma)

        # Sobel梯度
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=5)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=5)

        # 梯度幅度
        magnitude = np.sqrt(sobelx**2 + sobely**2)

        # 梯度方向
        direction = np.arctan2(sobely, sobelx)

        # 结构张量分析 (simplified Harris)
        Ixx = gaussian_filter(sobelx**2, sigma=sigma)
        Iyy = gaussian_filter(sobely**2, sigma=sigma)
        Ixy = gaussian_filter(sobelx * sobely, sigma=sigma)

        # 特征值（简化为响应函数）
        det = Ixx * Iyy - Ixy**2
        trace = Ixx + Iyy
        corner_response = det / (trace + 1e-10)

        # 融合边缘和角点响应
        depth = magnitude + 0.3 * np.abs(corner_response) * 50

        # 多尺度融合
        for s in [1.5, 2.0]:
            g = gaussian_filter(gray, sigma=s * sigma)
            sx = cv2.Sobel(g, cv2.CV_64F, 1, 0, ksize=5)
            sy = cv2.Sobel(g, cv2.CV_64F, 0, 1, ksize=5)
            mag = np.sqrt(sx**2 + sy**2)
            depth = depth + 0.5 * gaussian_filter(mag, sigma=s * sigma)

        # 归一化
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)

        # 平滑
        depth = gaussian_filter(depth, sigma=sigma * 0.5)

        return depth

    def _create_point_cloud(self, image, depth, scale):
        """创建点云"""
        h, w = image.shape[:2]

        # 网格坐标
        x = np.arange(w)
        y = np.arange(h)
        xx, yy = np.meshgrid(x, y)

        # 归一化坐标
        xx = (xx - w / 2) * scale / w
        yy = (yy - h / 2) * scale / h
        zz = depth * scale * 2

        # 展平
        points = np.stack([xx.flatten(), -yy.flatten(), zz.flatten()], axis=1)
        colors = image.reshape(-1, 3) / 255.0

        # 创建Open3D点云
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd.colors = o3d.utility.Vector3dVector(colors)

        return pcd

    def _ball_pivoting(self, pcd, voxel_size):
        """Ball Pivoting网格重建"""
        distances = pcd.compute_nearest_neighbor_distance()
        avg_dist = np.mean(np.asarray(distances))
        radii = [avg_dist * 1.5, avg_dist * 3, avg_dist * 6]

        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd, o3d.utility.DoubleVector(radii))

        # 移除孤立顶点
        mesh.remove_degenerate_triangles()
        mesh.remove_duplicated_triangles()
        mesh.remove_unreferenced_vertices()

        return mesh

    def _poisson_reconstruction(self, pcd):
        """Poisson网格重建"""
        try:
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd, depth=8, width=0, scale=1.1, linear_fit=False)

            # 移除低密度顶点（清理噪声）
            densities = np.asarray(densities)
            density_threshold = np.quantile(densities, 0.05)
            vertices_to_remove = densities < density_threshold
            mesh.remove_vertices_by_mask(vertices_to_remove)

            mesh.remove_degenerate_triangles()
            mesh.remove_duplicated_triangles()

            return mesh
        except:
            return self._ball_pivoting(pcd, 0.01)


class ViewerThread(QThread):
    """查看线程"""
    error = pyqtSignal(str)

    def __init__(self, mesh, pcd):
        super().__init__()
        self.mesh = mesh
        self.pcd = pcd

    def run(self):
        try:
            vis = o3d.visualization.Visualizer()
            vis.create_window()
            if self.mesh is not None:
                vis.add_geometry(self.mesh)
            elif self.pcd is not None:
                vis.add_geometry(self.pcd)
            vis.run()
            vis.destroy_window()
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VideoToModel - 图片/视频转3D")
        self.setGeometry(100, 100, 800, 700)
        self._setup_ui()
        self.conversion_thread = None
        self.last_mesh = None
        self.last_pcd = None

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 标题
        title = QLabel("📷 VideoToModel - 图片/视频转3D")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 输入文件
        input_grp = QGroupBox("输入文件")
        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择图片或视频...")
        self.input_edit.setStyleSheet("padding: 6px; font-size: 13px;")
        input_layout.addWidget(self.input_edit)

        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._select_file)
        browse_btn.setStyleSheet("padding: 6px 16px;")
        input_layout.addWidget(browse_btn)
        input_grp.setLayout(input_layout)
        layout.addWidget(input_grp)

        # 参数设置
        params_grp = QGroupBox("参数设置")
        params_layout = QFormLayout()
        params_layout.setSpacing(12)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.01, 5.0)
        self.scale_spin.setSingleStep(0.05)
        self.scale_spin.setValue(0.15)
        self.scale_spin.setStyleSheet("padding: 5px;")
        params_layout.addRow("深度缩放:", self.scale_spin)

        self.sigma_spin = QDoubleSpinBox()
        self.sigma_spin.setRange(0.5, 20.0)
        self.sigma_spin.setSingleStep(0.5)
        self.sigma_spin.setValue(3.0)
        self.sigma_spin.setStyleSheet("padding: 5px;")
        params_layout.addRow("平滑 sigma:", self.sigma_spin)

        self.voxel_spin = QDoubleSpinBox()
        self.voxel_spin.setRange(0.001, 0.1)
        self.voxel_spin.setSingleStep(0.005)
        self.voxel_spin.setValue(0.015)
        self.voxel_spin.setStyleSheet("padding: 5px;")
        params_layout.addRow("体素大小:", self.voxel_spin)

        self.mesh_combo = QComboBox()
        self.mesh_combo.addItems(["Ball Pivoting", "Poisson"])
        self.mesh_combo.setStyleSheet("padding: 5px;")
        params_layout.addRow("重建方法:", self.mesh_combo)

        self.output_edit = QLineEdit("model.ply")
        self.output_edit.setStyleSheet("padding: 5px;")
        params_layout.addRow("输出文件:", self.output_edit)

        params_grp.setLayout(params_layout)
        layout.addWidget(params_grp)

        # 按钮
        btn_layout = QHBoxLayout()

        self.convert_btn = QPushButton("🚀 开始转换")
        self.convert_btn.clicked.connect(self._start_convert)
        self.convert_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        btn_layout.addWidget(self.convert_btn)

        self.view_btn = QPushButton("👁 查看模型")
        self.view_btn.clicked.connect(self._view_model)
        self.view_btn.setEnabled(False)
        self.view_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        btn_layout.addWidget(self.view_btn)

        layout.addLayout(btn_layout)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setStyleSheet("QProgressBar { height: 25px; }")
        layout.addWidget(self.progress)

        # 日志
        log_grp = QGroupBox("日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas; font-size: 12px;")
        log_layout.addWidget(self.log_text)
        log_grp.setLayout(log_layout)
        layout.addWidget(log_grp)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件",
            "", "媒体文件 (*.png *.jpg *.jpeg *.bmp *.mp4 *.avi *.mov *.mkv *.webm);;所有 (*.*)")
        if path:
            self.input_edit.setText(path)

    def _start_convert(self):
        path = self.input_edit.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "错误", "请选择有效文件！")
            return

        params = {
            'depth_scale': self.scale_spin.value(),
            'sigma': self.sigma_spin.value(),
            'voxel_size': self.voxel_spin.value(),
            'mesh_mode': 'ball' if self.mesh_combo.currentIndex() == 0 else 'poisson',
            'output_name': self.output_edit.text().strip() or 'model.ply'
        }

        if not params['output_name'].endswith('.ply'):
            params['output_name'] += '.ply'

        self.convert_btn.setEnabled(False)
        self.progress.setValue(0)
        self.log_text.clear()

        self.conversion_thread = ConversionThread(path, params)
        self.conversion_thread.progress.connect(self._on_progress)
        self.conversion_thread.finished_ok.connect(self._on_finished)
        self.conversion_thread.error.connect(self._on_error)
        self.conversion_thread.start()

    def _on_progress(self, val, msg):
        self.progress.setValue(val)
        self.log_text.append(f"[{val}%] {msg}")

    def _on_finished(self, pcd, mesh):
        self.last_pcd = pcd
        self.last_mesh = mesh
        self.convert_btn.setEnabled(True)
        self.view_btn.setEnabled(True)
        self.progress.setValue(100)
        self.log_text.append("✓ 完成！")
        QMessageBox.information(self, "成功", "转换完成！")

    def _on_error(self, msg):
        self.convert_btn.setEnabled(True)
        self.log_text.append(f"✗ 错误: {msg}")
        QMessageBox.critical(self, "错误", msg)

    def _view_model(self):
        if self.last_mesh is None and self.last_pcd is None:
            return
        t = ViewerThread(self.last_mesh, self.last_pcd)
        t.error.connect(lambda m: QMessageBox.critical(self, "错误", m))
        t.start()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
