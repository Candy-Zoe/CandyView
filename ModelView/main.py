"""
ModelView - 3D Model Viewer
主程序入口
使用PyOpenGL进行3D渲染
"""

import sys
import traceback
from PyQt5.QtWidgets import QApplication, QMessageBox

from ui.main_window import MainWindow
from core.model_loader import ModelLoader


class ModelViewerApp:
    """3D模型查看器应用主类"""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self._setup_app_style()

        self.main_window = MainWindow()
        self.model_loader = ModelLoader()

        self.current_model_data = None
        self.current_info = None
        self.viewer_thread = None

        self._connect_signals()

    def _setup_app_style(self):
        """设置应用样式"""
        self.app.setApplicationName("3D Model Viewer")
        self.app.setApplicationVersion("1.0")
        self.app.setStyle("Fusion")

    def _connect_signals(self):
        """连接信号槽"""
        self.main_window.open_action.triggered.connect(self._on_open_file)
        self.main_window.reload_action.triggered.connect(self._on_reload_file)
        self.main_window.clear_action.triggered.connect(self._on_clear_model)
        self.main_window.wireframe_action.triggered.connect(self._on_toggle_wireframe)
        self.main_window.axes_action.triggered.connect(self._on_toggle_axes)
        self.main_window.reset_action.triggered.connect(self._on_reset_view)
        self.main_window.clear_model_btn.clicked.connect(self._on_clear_model)

        self.main_window.transform_panel.load_clicked.connect(self._on_open_file)
        self.main_window.transform_panel.reset_clicked.connect(self._on_reset_view)

    def _on_open_file(self):
        """打开文件对话框"""
        from PyQt5.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Open 3D Model",
            "",
            ";;".join(self.model_loader.get_format_filters())
        )

        if file_path:
            self.load_model(file_path)

    def load_model(self, file_path: str):
        """加载模型文件"""
        try:
            model_data, info = self.model_loader.load_model(file_path)

            if model_data is not None:
                self.current_model_data = model_data
                self.current_info = info

                self.main_window.info_panel.update_info({
                    'format': info.format,
                    'vertices': info.vertices,
                    'triangles': info.triangles,
                    'has_texture': info.has_texture,
                    'has_vertex_colors': info.has_vertex_colors,
                    'has_normals': info.has_normals,
                    'bounding_box_min': info.bounding_box_min,
                    'bounding_box_max': info.bounding_box_max,
                    'bounding_box_size': info.bounding_box_size,
                    'center': info.center,
                    'file_path': info.file_path
                })

                self.main_window.open_file(file_path)

                self._launch_viewer(model_data)

            else:
                QMessageBox.warning(self.main_window, "Load Failed", "Failed to load model file.")

        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to load model:\n{str(e)}")
            traceback.print_exc()

    def _launch_viewer(self, model_data):
        """启动3D查看器"""
        import threading
        
        def run_viewer():
            from core.viewer_3d import Viewer3D
            
            viewer = Viewer3D()
            viewer.load_model(model_data)
            viewer.create_window(width=950, height=720)
            viewer.run()
        
        self.viewer_thread = threading.Thread(target=run_viewer)
        self.viewer_thread.daemon = True
        self.viewer_thread.start()

    def _on_reload_file(self):
        """重新加载当前文件"""
        if self.main_window.current_file_path:
            self.load_model(self.main_window.current_file_path)

    def _on_clear_model(self):
        """清除模型"""
        self.current_model_data = None
        self.current_info = None
        self.viewer_thread = None
        self.main_window._on_clear_model()

    def _on_toggle_wireframe(self, checked: bool):
        """切换线框模式"""
        pass

    def _on_toggle_axes(self, checked: bool):
        """切换坐标轴显示"""
        pass

    def _on_reset_view(self):
        """重置视图"""
        self.main_window.transform_panel.reset_all_sliders()
        self.main_window.measure_panel.clear_measurements()

    def run(self):
        """运行应用"""
        self.main_window.show()
        return self.app.exec_()


def main():
    """主函数"""
    try:
        app = ModelViewerApp()
        sys.exit(app.run())
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
