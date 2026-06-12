"""
主窗口界面
"""

import os
import sys
import traceback
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QDoubleSpinBox,
    QProgressBar, QMessageBox, QTextEdit, QGroupBox, QFormLayout,
    QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from core.depth_estimator import DepthEstimator
from core.point_cloud_generator import PointCloudGenerator
from core.mesh_reconstructor import MeshReconstructor
from utils.image_utils import load_image, load_video_frame, resize_image


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
            depth_scale = float(self.params['depth_scale'])
            sigma = float(self.params['sigma'])
            voxel_size = float(self.params['voxel_size'])
            mesh_mode = self.params['mesh_mode']
            output_name = self.params['output_name']
            depth_algorithm = self.params['depth_algorithm']

            self.progress.emit(5, "加载输入...")
            ext = os.path.splitext(self.input_path)[1].lower()

            if ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                self.progress.emit(10, "读取视频帧...")
                image = load_video_frame(self.input_path)
            else:
                self.progress.emit(10, "加载图片...")
                image = load_image(self.input_path)

            if image is None or image.size == 0:
                self.error.emit("图像加载失败")
                return

            image = resize_image(image, max_size=1024)

            self.progress.emit(20, "初始化深度估计器...")
            estimator = DepthEstimator()

            if estimator.has_midas() and depth_algorithm == 'auto':
                self.progress.emit(25, "使用MiDaS深度学习...")
            else:
                self.progress.emit(25, f"使用{depth_algorithm}算法...")

            self.progress.emit(30, "深度估计中...")
            depth = estimator.estimate(image, method=depth_algorithm, sigma=sigma)

            self.progress.emit(50, "生成点云...")
            pcd_gen = PointCloudGenerator()
            pcd = pcd_gen.create_from_depth(image, depth, scale=depth_scale)

            self.progress.emit(60, "下采样...")
            pcd_down = pcd_gen.downsample(pcd, voxel_size=voxel_size)

            self.progress.emit(65, "移除离群点...")
            pcd_down = pcd_gen.remove_outliers(pcd_down)

            self.progress.emit(70, "估计法线...")
            pcd_down = pcd_gen.estimate_normals(pcd_down, voxel_size=voxel_size)

            self.progress.emit(75, "生成网格...")
            reconstructor = MeshReconstructor()
            if mesh_mode == 'ball':
                mesh = reconstructor.ball_pivoting(pcd_down, voxel_size=voxel_size)
            else:
                mesh = reconstructor.poisson(pcd_down)

            self.progress.emit(90, "导出PLY...")
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_name)

            if not output_path.endswith('.ply'):
                output_path += '.ply'

            if mesh is not None:
                reconstructor.save(mesh, output_path)
            else:
                import open3d as o3d
                o3d.io.write_point_cloud(output_path, pcd)

            self.progress.emit(100, "完成!")
            self.finished_ok.emit(pcd, mesh)

        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VideoToModel - 图片转3D")
        self.setGeometry(100, 100, 850, 750)
        
        self._init_estimator()
        self._setup_ui()
        
        self.conversion_thread = None
        self.last_mesh = None
        self.last_pcd = None

    def _init_estimator(self):
        """初始化深度估计器"""
        self.estimator = DepthEstimator()

    def _setup_ui(self):
        """设置界面"""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("🎯 VideoToModel - 图片/视频转3D模型")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        input_grp = QGroupBox("输入文件")
        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择图片或视频...")
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self._select_file)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(browse_btn)
        input_grp.setLayout(input_layout)
        layout.addWidget(input_grp)

        params_grp = QGroupBox("参数设置")
        params_layout = QFormLayout()

        self.algorithm_combo = QComboBox()
        algorithms = [
            "auto (自动选择)",
            "fusion (智能融合)",
            "midas (深度学习)",
            "laplacian (拉普拉斯)",
            "gradient (梯度算子)",
            "canny (Canny边缘)",
            "harris (Harris角点)",
            "sift (SIFT特征)",
            "bilateral (双边滤波)",
            "guided (导向滤波)",
            "multiscale (多尺度)"
        ]
        self.algorithm_combo.addItems(algorithms)
        params_layout.addRow("深度算法:", self.algorithm_combo)

        self.midas_status = QLabel()
        self.midas_status.setText("ℹ 点击转换时会自动检测深度学习支持")
        self.midas_status.setStyleSheet("color: gray; font-size: 11px;")
        params_layout.addRow("", self.midas_status)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.01, 5.0)
        self.scale_spin.setValue(0.2)
        params_layout.addRow("深度缩放:", self.scale_spin)

        self.sigma_spin = QDoubleSpinBox()
        self.sigma_spin.setRange(0.5, 20.0)
        self.sigma_spin.setValue(2.0)
        params_layout.addRow("平滑 sigma:", self.sigma_spin)

        self.voxel_spin = QDoubleSpinBox()
        self.voxel_spin.setRange(0.001, 0.1)
        self.voxel_spin.setValue(0.01)
        params_layout.addRow("体素大小:", self.voxel_spin)

        self.mesh_combo = QComboBox()
        self.mesh_combo.addItems(["Ball Pivoting", "Poisson"])
        params_layout.addRow("重建方法:", self.mesh_combo)

        self.output_edit = QLineEdit("model.ply")
        params_layout.addRow("输出文件:", self.output_edit)

        params_grp.setLayout(params_layout)
        layout.addWidget(params_grp)

        btn_layout = QHBoxLayout()
        self.convert_btn = QPushButton("🚀 开始转换")
        self.convert_btn.clicked.connect(self._start_convert)
        self.convert_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; padding: 12px 24px; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        btn_layout.addWidget(self.convert_btn)

        self.view_btn = QPushButton("👁 查看模型")
        self.view_btn.clicked.connect(self._view_model)
        self.view_btn.setEnabled(False)
        self.view_btn.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; padding: 12px 24px; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        btn_layout.addWidget(self.view_btn)
        layout.addLayout(btn_layout)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        log_grp = QGroupBox("日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas; font-size: 12px;")
        log_layout.addWidget(self.log_text)
        log_grp.setLayout(log_layout)
        layout.addWidget(log_grp)

        tips_grp = QGroupBox("💡 提示")
        tips_layout = QVBoxLayout()
        tips = QLabel("""
        <ul>
        <li><b>深度算法选择:</b> auto模式会自动使用MiDaS深度学习（如果可用）</li>
        <li><b>深度缩放:</b> 值越大，模型深度越明显</li>
        <li><b>体素大小:</b> 值越小，模型越精细，但文件越大</li>
        <li><b>重建方法:</b> Poisson适合光滑表面，Ball Pivoting适合复杂结构</li>
        </ul>
        """)
        tips.setStyleSheet("font-size: 12px;")
        tips_layout.addWidget(tips)
        tips_grp.setLayout(tips_layout)
        layout.addWidget(tips_grp)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "",
            "媒体文件 (*.png *.jpg *.jpeg *.bmp *.mp4 *.avi *.mov *.mkv *.webm);;所有文件 (*.*)")
        if path:
            self.input_edit.setText(path)

    def _start_convert(self):
        path = self.input_edit.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "错误", "请选择有效文件！")
            return

        algorithms_map = {
            0: 'auto',
            1: 'fusion',
            2: 'midas',
            3: 'laplacian',
            4: 'gradient',
            5: 'canny',
            6: 'harris',
            7: 'sift',
            8: 'bilateral',
            9: 'guided',
            10: 'multiscale'
        }

        params = {
            'depth_scale': self.scale_spin.value(),
            'sigma': self.sigma_spin.value(),
            'voxel_size': self.voxel_spin.value(),
            'mesh_mode': 'ball' if self.mesh_combo.currentIndex() == 0 else 'poisson',
            'output_name': self.output_edit.text().strip() or 'model.ply',
            'depth_algorithm': algorithms_map.get(self.algorithm_combo.currentIndex(), 'auto')
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
        QMessageBox.information(self, "成功", "转换完成！模型已保存到 output 目录")

    def _on_error(self, msg):
        self.convert_btn.setEnabled(True)
        self.log_text.append(f"✗ 错误: {msg}")
        QMessageBox.critical(self, "错误", msg)

    def _view_model(self):
        if self.last_mesh is None and self.last_pcd is None:
            return
        
        import threading
        def run_viewer():
            import open3d as o3d
            vis = o3d.visualization.Visualizer()
            vis.create_window(window_name="模型查看器")
            
            if self.last_mesh is not None:
                vis.add_geometry(self.last_mesh)
            elif self.last_pcd is not None:
                vis.add_geometry(self.last_pcd)
            
            vis.get_render_option().light_on = True
            vis.get_render_option().background_color = [0.9, 0.9, 0.9]
            vis.run()
            vis.destroy_window()
        
        t = threading.Thread(target=run_viewer)
        t.daemon = True
        t.start()
