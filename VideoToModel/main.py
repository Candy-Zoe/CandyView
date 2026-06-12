"""
VideoToModel - 图片/视频转3D模型
智能融合版本 - 综合多种深度估计算法
"""

import sys
import os
import traceback
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QSpinBox, QDoubleSpinBox,
    QProgressBar, QMessageBox, QTextEdit, QGroupBox, QFormLayout,
    QCheckBox, QSlider, QComboBox, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, sobel
from scipy import ndimage
import open3d as o3d

try:
    import torch
    HAS_TORCH = True
    try:
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        HAS_MIDAS = True
    except:
        HAS_MIDAS = False
except:
    HAS_TORCH = False
    HAS_MIDAS = False


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
            mesh_mode = self.params['mesh_mode']
            output_name = self.params['output_name']
            fusion_strength = float(self.params['fusion_strength'])

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

            self.progress.emit(20, "智能融合深度估计...")
            depth = self._smart_fusion_depth(image, sigma, fusion_strength)

            self.progress.emit(50, "生成点云...")
            pcd = self._create_point_cloud(image, depth, depth_scale)

            self.progress.emit(65, "下采样...")
            pcd_down = pcd.voxel_down_sample(voxel_size=voxel_size)

            self.progress.emit(75, "估计法线...")
            pcd_down.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size * 5, max_nn=30))

            self.progress.emit(85, "生成网格...")
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
                mesh.remove_degenerate_triangles()
                mesh.remove_duplicated_triangles()
                mesh.remove_unreferenced_vertices()
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

        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def _smart_fusion_depth(self, image, sigma, fusion_strength=0.7):
        """
        智能融合深度估计
        综合多种算法生成最优深度图
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float64)
        gray_blur = gaussian_filter(gray, sigma=sigma)

        self.progress.emit(25, "计算梯度特征...")
        depth_grad = self._compute_gradient_depth(gray_blur, sigma)

        self.progress.emit(30, "计算拉普拉斯特征...")
        depth_lap = self._compute_laplacian_depth(gray_blur, sigma)

        self.progress.emit(35, "计算Canny特征...")
        depth_canny = self._compute_canny_depth(gray, sigma)

        self.progress.emit(40, "计算结构张量...")
        depth_struct = self._compute_structure_tensor_depth(gray_blur, sigma)

        depth_methods = [depth_grad, depth_lap, depth_canny, depth_struct]
        weights = [0.35, 0.25, 0.20, 0.20]

        midas_depth = None
        if HAS_MIDAS:
            try:
                self.progress.emit(45, "MiDaS推理...")
                midas_depth = self._estimate_depth_midas(image)
                depth_methods.append(midas_depth)
                weights.append(0.3)
            except Exception as e:
                print(f"MiDaS skipped: {e}")

        fused_depth = np.zeros_like(depth_grad)
        total_weight = sum(weights)

        for i, depth in enumerate(depth_methods):
            fused_depth += depth * weights[i]

        fused_depth /= total_weight

        fused_depth = gaussian_filter(fused_depth, sigma=sigma * 0.3)

        if midas_depth is not None and fusion_strength > 0:
            fused_depth = fused_depth * (1 - fusion_strength) + midas_depth * fusion_strength

        fused_depth = (fused_depth - fused_depth.min()) / (fused_depth.max() - fused_depth.min() + 1e-10)

        return 1.0 - fused_depth

    def _compute_gradient_depth(self, gray, sigma):
        """计算梯度深度"""
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=5)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=5)
        magnitude = np.sqrt(sobelx**2 + sobely**2)
        return gaussian_filter(magnitude, sigma=sigma * 0.5)

    def _compute_laplacian_depth(self, gray, sigma):
        """计算拉普拉斯深度"""
        laplacian = cv2.Laplacian(gray, cv2.CV_64F, ksize=5)
        return gaussian_filter(np.abs(laplacian), sigma=sigma * 0.5)

    def _compute_canny_depth(self, gray, sigma):
        """计算Canny边缘深度"""
        edges = cv2.Canny(gray.astype(np.uint8), 50, 150)
        return gaussian_filter(edges.astype(np.float64) / 255.0, sigma=sigma * 0.5)

    def _compute_structure_tensor_depth(self, gray, sigma):
        """计算结构张量深度"""
        Ix = sobel(gray, axis=1)
        Iy = sobel(gray, axis=0)
        Ixx = gaussian_filter(Ix**2, sigma=sigma)
        Iyy = gaussian_filter(Iy**2, sigma=sigma)
        Ixy = gaussian_filter(Ix * Iy, sigma=sigma)
        det = Ixx * Iyy - Ixy**2
        trace = Ixx + Iyy + 1e-10
        return det / trace

    def _estimate_depth_midas(self, image):
        """MiDaS深度学习深度估计"""
        processor = AutoImageProcessor.from_pretrained("depth-anything/Depth-Anything-V2-Small-hf")
        model = AutoModelForDepthEstimation.from_pretrained("depth-anything/Depth-Anything-V2-Small-hf")

        inputs = processor(images=image, return_tensors="pt")

        with torch.no_grad():
            outputs = model(**inputs)
            depth_pred = outputs.predicted_depth

        depth_pred = depth_pred.squeeze().cpu().numpy()
        depth_pred = cv2.resize(depth_pred, (image.shape[1], image.shape[0]))

        return (depth_pred - depth_pred.min()) / (depth_pred.max() - depth_pred.min() + 1e-10)

    def _create_point_cloud(self, image, depth, scale):
        """创建高质量点云"""
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

    def _ball_pivoting(self, pcd, voxel_size):
        """Ball Pivoting网格重建"""
        distances = pcd.compute_nearest_neighbor_distance()
        avg_dist = np.mean(np.asarray(distances))

        radii = [avg_dist * 1.5, avg_dist * 3, avg_dist * 6, avg_dist * 12]

        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd, o3d.utility.DoubleVector(radii))

        if mesh is not None:
            mesh.remove_degenerate_triangles()
            mesh.remove_duplicated_triangles()
            mesh.remove_unreferenced_vertices()

        return mesh

    def _poisson_reconstruction(self, pcd):
        """Poisson网格重建"""
        try:
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd, depth=9, width=0, scale=1.2, linear_fit=False)

            densities = np.asarray(densities)
            density_threshold = np.quantile(densities, 0.03)
            vertices_to_remove = densities < density_threshold
            mesh.remove_vertices_by_mask(vertices_to_remove)

            mesh.remove_degenerate_triangles()
            mesh.remove_duplicated_triangles()
            mesh.remove_unreferenced_vertices()

            return mesh
        except Exception as e:
            print(f"Poisson failed: {e}")
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

            vis.get_render_option().light_on = True
            vis.get_render_option().background_color = [0.9, 0.9, 0.9]

            vis.run()
            vis.destroy_window()
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VideoToModel - 智能融合深度估计")
        self.setGeometry(100, 100, 900, 850)
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

        title = QLabel("🎯 VideoToModel - 智能融合深度估计")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

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

        params_grp = QGroupBox("参数设置")
        params_layout = QFormLayout()
        params_layout.setSpacing(12)

        self.fusion_strength_spin = QDoubleSpinBox()
        self.fusion_strength_spin.setRange(0.0, 1.0)
        self.fusion_strength_spin.setSingleStep(0.05)
        self.fusion_strength_spin.setValue(0.7)
        self.fusion_strength_spin.setStyleSheet("padding: 5px;")
        params_layout.addRow("MiDaS融合强度:", self.fusion_strength_spin)

        self.midas_hint = QLabel()
        if HAS_MIDAS:
            self.midas_hint.setText("✓ MiDaS可用，将参与智能融合")
            self.midas_hint.setStyleSheet("color: green; font-size: 11px;")
        else:
            self.midas_hint.setText("⚠ MiDaS未安装，仅使用传统算法融合")
            self.midas_hint.setStyleSheet("color: orange; font-size: 11px;")
        params_layout.addRow("", self.midas_hint)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.01, 5.0)
        self.scale_spin.setSingleStep(0.05)
        self.scale_spin.setValue(0.2)
        self.scale_spin.setStyleSheet("padding: 5px;")
        params_layout.addRow("深度缩放:", self.scale_spin)

        self.sigma_spin = QDoubleSpinBox()
        self.sigma_spin.setRange(0.5, 20.0)
        self.sigma_spin.setSingleStep(0.5)
        self.sigma_spin.setValue(2.0)
        self.sigma_spin.setStyleSheet("padding: 5px;")
        params_layout.addRow("平滑 sigma:", self.sigma_spin)

        self.voxel_spin = QDoubleSpinBox()
        self.voxel_spin.setRange(0.001, 0.1)
        self.voxel_spin.setSingleStep(0.005)
        self.voxel_spin.setValue(0.01)
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

        # 算法融合说明
        fusion_info = QGroupBox("智能融合算法")
        fusion_layout = QVBoxLayout()
        fusion_text = QTextEdit()
        fusion_text.setReadOnly(True)
        fusion_text.setStyleSheet("font-size: 12px;")
        fusion_text.setText("""
融合算法权重分配：
├── 梯度算子 (35%)     - 检测边界轮廓
├── 拉普拉斯算子 (25%)  - 检测边缘细节
├── Canny边缘 (20%)    - 精确边缘提取
├── 结构张量 (20%)     - 检测角点和纹理
└── MiDaS (30%)        - 深度学习（可选）

MiDaS融合强度参数控制深度学习结果的影响程度：
- 0.0 = 仅使用传统算法
- 0.7 = 70%深度学习 + 30%传统算法（推荐）
- 1.0 = 完全使用深度学习

注：MiDaS需要安装 PyTorch 和 transformers
""")
        fusion_layout.addWidget(fusion_text)
        fusion_info.setLayout(fusion_layout)
        layout.addWidget(fusion_info)

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

        self.progress = QProgressBar()
        self.progress.setStyleSheet("QProgressBar { height: 25px; }")
        layout.addWidget(self.progress)

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
            'output_name': self.output_edit.text().strip() or 'model.ply',
            'fusion_strength': self.fusion_strength_spin.value()
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
