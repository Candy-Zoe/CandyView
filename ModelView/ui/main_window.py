"""
主窗口模块
整合所有UI组件
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QMenuBar, QMenu, QAction, QFileDialog, QMessageBox,
    QTabWidget, QLabel, QStatusBar, QToolBar,
    QSplitter, QFrame, QPushButton, QProgressBar
)
from PyQt5.QtCore import Qt, pyqtSlot, QSize, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QKeySequence, QFont

from ui.transform_panel import TransformPanel
from ui.measure_panel import MeasurePanel
from ui.info_panel import InfoPanel
from core.model_loader import ModelLoader


class LoadThread(QThread):
    """模型加载线程"""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit(10, "Loading model...")
            
            loader = ModelLoader()
            model = loader.load(self.file_path)
            
            if model is None:
                self.error.emit("Failed to load model")
                return
            
            self.progress.emit(50, "Processing model...")
            
            if model.vertices:
                self.progress.emit(80, "Computing normals...")
                if not model.normals:
                    model.compute_normals()
            
            self.progress.emit(100, "Complete")
            self.finished.emit(model)
            
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()
        self.current_file_path = None
        self.current_model = None
        self._wireframe_enabled = False
        self._axes_enabled = True
        self._model_loaded = False
        self._load_thread = None
        self._setup_ui()
        self._create_menu()
        self._create_toolbar()
        self._create_statusbar()

    def _setup_ui(self):
        """设置UI布局"""
        self.setWindowTitle("3D Model Viewer")
        self.setGeometry(100, 100, 1400, 900)

        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局 - 水平分割
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧面板容器
        left_panel = QWidget()
        left_panel.setFixedWidth(320)
        left_panel.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-right: 1px solid #ddd;
            }
        """)

        # 左侧面板布局
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 创建标签页控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #f5f5f5;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 10px 20px;
                margin-right: 2px;
                border-radius: 3px 3px 0 0;
            }
            QTabBar::tab:selected {
                background-color: #f5f5f5;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #d0d0d0;
            }
        """)

        # 创建各个面板
        self.transform_panel = TransformPanel()
        self.measure_panel = MeasurePanel()
        self.info_panel = InfoPanel()

        # 添加标签页
        self.tab_widget.addTab(self.transform_panel, "Transform")
        self.tab_widget.addTab(self.measure_panel, "Measure")
        self.tab_widget.addTab(self.info_panel, "Info")

        left_layout.addWidget(self.tab_widget)

        # 右侧查看区域
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: #ffffff;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 查看器容器
        self.viewer_container = QWidget()
        self.viewer_container.setStyleSheet("""
            QWidget {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin: 5px;
            }
        """)
        viewer_layout = QVBoxLayout(self.viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)

        # 查看器占位标签
        self.viewer_placeholder = QLabel()
        self.viewer_placeholder.setAlignment(Qt.AlignCenter)
        self.viewer_placeholder.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 16px;
            }
        """)
        self.viewer_placeholder.setText(
            "<html><center>"
            "<h2>3D Model Viewer</h2>"
            "<p style='margin-top: 20px;'>Click <b>Load Model</b> to open a 3D model file</p>"
            "<p style='margin-top: 10px; color: #aaa;'>Supported formats: PLY, OBJ, STL, GLB, GLTF</p>"
            "</center></html>"
        )
        viewer_layout.addWidget(self.viewer_placeholder)

        # 加载进度条
        self.load_progress = QProgressBar()
        self.load_progress.setStyleSheet("""
            QProgressBar {
                height: 25px;
                margin: 10px;
            }
        """)
        self.load_progress.hide()
        viewer_layout.addWidget(self.load_progress)

        # 底部控制栏
        self.bottom_bar = QFrame()
        self.bottom_bar.setStyleSheet("background-color: #f0f0f0; border-top: 1px solid #ddd;")
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(10, 5, 10, 5)
        bottom_layout.setSpacing(10)

        # 文件信息显示
        self.file_info_label = QLabel("No model loaded")
        self.file_info_label.setStyleSheet("color: #666; font-size: 12px;")
        bottom_layout.addWidget(self.file_info_label)

        bottom_layout.addStretch()

        # 控制按钮
        self.view_model_btn = QPushButton("View Model")
        self.view_model_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.view_model_btn.clicked.connect(self._on_view_model)
        self.view_model_btn.setEnabled(False)
        bottom_layout.addWidget(self.view_model_btn)

        self.clear_model_btn = QPushButton("Clear Model")
        self.clear_model_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.clear_model_btn.clicked.connect(self._on_clear_model)
        self.clear_model_btn.setEnabled(False)
        bottom_layout.addWidget(self.clear_model_btn)

        right_layout.addWidget(self.viewer_container, 1)
        right_layout.addWidget(self.bottom_bar, 0)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)

    def _create_menu(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("File")

        self.open_action = QAction("Open...", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self._on_open_triggered)
        file_menu.addAction(self.open_action)

        self.reload_action = QAction("Reload", self)
        self.reload_action.setShortcut(QKeySequence.Refresh)
        self.reload_action.triggered.connect(self._on_reload_triggered)
        self.reload_action.setEnabled(False)
        file_menu.addAction(self.reload_action)

        file_menu.addSeparator()

        self.clear_action = QAction("Clear Model", self)
        self.clear_action.setShortcut("Del")
        self.clear_action.triggered.connect(self._on_clear_model)
        self.clear_action.setEnabled(False)
        file_menu.addAction(self.clear_action)

        file_menu.addSeparator()

        self.exit_action = QAction("Exit", self)
        self.exit_action.setShortcut(QKeySequence.Quit)
        self.exit_action.triggered.connect(self.close)
        file_menu.addAction(self.exit_action)

        # 视图菜单
        view_menu = menubar.addMenu("View")

        self.wireframe_action = QAction("Wireframe", self)
        self.wireframe_action.setCheckable(True)
        self.wireframe_action.setShortcut("W")
        self.wireframe_action.triggered.connect(self._on_wireframe_triggered)
        self.wireframe_action.setEnabled(False)
        view_menu.addAction(self.wireframe_action)

        self.axes_action = QAction("Show Axes", self)
        self.axes_action.setCheckable(True)
        self.axes_action.setChecked(True)
        self.axes_action.setShortcut("A")
        self.axes_action.triggered.connect(self._on_axes_triggered)
        self.axes_action.setEnabled(False)
        view_menu.addAction(self.axes_action)

        view_menu.addSeparator()

        self.reset_action = QAction("Reset View", self)
        self.reset_action.setShortcut("R")
        self.reset_action.triggered.connect(self._on_reset_triggered)
        self.reset_action.setEnabled(False)
        view_menu.addAction(self.reset_action)

        # 帮助菜单
        help_menu = menubar.addMenu("Help")

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self._on_about_triggered)
        help_menu.addAction(self.about_action)

        self.controls_action = QAction("Controls", self)
        self.controls_action.triggered.connect(self._on_controls_triggered)
        help_menu.addAction(self.controls_action)

    def _create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #f5f5f5;
                border-bottom: 1px solid #ddd;
            }
            QToolButton {
                padding: 5px 10px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
                border-radius: 3px;
            }
        """)
        self.addToolBar(toolbar)

        # 添加工具栏按钮
        toolbar.addAction(self.open_action)
        toolbar.addSeparator()
        toolbar.addAction(self.wireframe_action)
        toolbar.addAction(self.axes_action)
        toolbar.addSeparator()
        toolbar.addAction(self.reset_action)
        toolbar.addSeparator()
        toolbar.addAction(self.clear_action)

    def _create_statusbar(self):
        """创建状态栏"""
        self.statusbar = QStatusBar()
        self.statusbar.setStyleSheet("""
            QStatusBar {
                background-color: #f0f0f0;
                border-top: 1px solid #ddd;
                font-size: 12px;
            }
        """)
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready")

    @pyqtSlot()
    def _on_open_triggered(self):
        """打开文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open 3D Model",
            "",
            ";;".join(ModelLoader.get_format_filters())
        )
        if file_path:
            self.open_file(file_path)

    @pyqtSlot()
    def _on_reload_triggered(self):
        """重新加载"""
        if self.current_file_path:
            self.open_file(self.current_file_path)

    @pyqtSlot()
    def _on_clear_model(self):
        """清除模型"""
        # 取消正在加载的线程
        if self._load_thread and self._load_thread.isRunning():
            self._load_thread.quit()
            self._load_thread.wait()

        self.current_file_path = None
        self.current_model = None
        self._model_loaded = False
        self.viewer_placeholder.show()
        self.load_progress.hide()
        self.file_info_label.setText("No model loaded")
        self.info_panel.set_placeholder()
        
        # 重置控件状态
        self.transform_panel.reset_all_sliders()
        self.measure_panel.clear_measurements()
        
        # 更新按钮状态
        self.update_ui_states(False)
        
        self.statusbar.showMessage("Model cleared")

    @pyqtSlot()
    def _on_wireframe_triggered(self, checked: bool):
        """切换线框模式"""
        self._wireframe_enabled = checked
        self.statusbar.showMessage(f"Wireframe: {'On' if checked else 'Off'}")

    @pyqtSlot()
    def _on_axes_triggered(self, checked: bool):
        """切换坐标轴"""
        self._axes_enabled = checked
        self.statusbar.showMessage(f"Axes: {'Visible' if checked else 'Hidden'}")

    @pyqtSlot()
    def _on_reset_triggered(self):
        """重置视图"""
        self.transform_panel.reset_all_sliders()
        self.measure_panel.clear_measurements()
        self.statusbar.showMessage("View reset")

    @pyqtSlot()
    def _on_about_triggered(self):
        """关于"""
        QMessageBox.about(
            self,
            "About 3D Model Viewer",
            "<b>3D Model Viewer</b><br><br>"
            "A powerful 3D model viewer with support for PLY, OBJ, STL, GLB, GLTF formats.<br><br>"
            "Features:<br>"
            "- Model loading with texture support<br>"
            "- Transform controls (rotate, scale, translate)<br>"
            "- Distance measurement<br>"
            "- Wireframe and axes display"
        )

    @pyqtSlot()
    def _on_controls_triggered(self):
        """控制说明"""
        QMessageBox.information(
            self,
            "Controls",
            "<b>Keyboard Controls:</b><br><br>"
            "- Arrow Keys: Rotate model<br>"
            "- W: Toggle wireframe<br>"
            "- A: Toggle axes<br>"
            "- R: Reset view<br>"
            "- Del: Clear model<br>"
            "- Ctrl+O: Open file<br>"
            "- Ctrl+R: Reload file<br><br>"
            "<b>Mouse Controls:</b><br><br>"
            "- Left drag: Rotate view<br>"
            "- Right drag: Pan view<br>"
            "- Scroll: Zoom in/out"
        )

    def open_file(self, file_path: str):
        """
        异步打开模型文件

        Args:
            file_path: 文件路径
        """
        # 取消正在加载的线程
        if self._load_thread and self._load_thread.isRunning():
            self._load_thread.quit()
            self._load_thread.wait()

        # 显示加载进度
        self.viewer_placeholder.hide()
        self.load_progress.show()
        self.load_progress.setValue(0)

        # 创建并启动加载线程
        self._load_thread = LoadThread(file_path)
        self._load_thread.finished.connect(self._on_load_finished)
        self._load_thread.error.connect(self._on_load_error)
        self._load_thread.progress.connect(self._on_load_progress)
        self._load_thread.start()

        # 更新UI状态
        self.current_file_path = file_path
        self.statusbar.showMessage(f"Loading: {file_path}")

    def _on_load_progress(self, value: int, message: str):
        """加载进度回调"""
        self.load_progress.setValue(value)
        self.statusbar.showMessage(f"{message} ({value}%)")

    def _on_load_finished(self, model):
        """加载完成回调"""
        self.load_progress.hide()
        self.current_model = model
        self._model_loaded = True

        # 更新UI状态
        self.update_ui_states(True)

        # 更新文件信息
        file_name = self.current_file_path.split('/')[-1] if '/' in self.current_file_path else self.current_file_path.split('\\')[-1]
        self.file_info_label.setText(f"Loaded: {file_name}")

        # 更新信息面板
        self.info_panel.update_info(model)

        self.statusbar.showMessage(f"Loaded: {file_name}")

    def _on_load_error(self, error_msg: str):
        """加载错误回调"""
        self.load_progress.hide()
        self.viewer_placeholder.show()
        
        QMessageBox.critical(
            self,
            "Load Error",
            f"Failed to load model:\n{error_msg}"
        )
        
        self.statusbar.showMessage("Load failed")
        self.update_ui_states(False)

    def _on_view_model(self):
        """查看模型"""
        if self.current_model is None:
            return
        
        import threading
        from core.viewer_3d import Viewer3D
        
        def run_viewer():
            viewer = Viewer3D()
            viewer.load_model(self.current_model)
            viewer.create_window()
            viewer.run()
        
        thread = threading.Thread(target=run_viewer)
        thread.daemon = True
        thread.start()

    def update_ui_states(self, model_loaded: bool):
        """更新UI控件状态"""
        self.reload_action.setEnabled(model_loaded)
        self.clear_action.setEnabled(model_loaded)
        self.wireframe_action.setEnabled(model_loaded)
        self.axes_action.setEnabled(model_loaded)
        self.reset_action.setEnabled(model_loaded)
        self.clear_model_btn.setEnabled(model_loaded)
        self.view_model_btn.setEnabled(model_loaded)

    def closeEvent(self, event):
        """关闭事件"""
        # 取消正在加载的线程
        if self._load_thread and self._load_thread.isRunning():
            self._load_thread.quit()
            self._load_thread.wait()

        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to exit?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()
