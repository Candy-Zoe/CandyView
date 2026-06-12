"""
ModelView - 3D Model Viewer
主程序入口
"""

import sys
import traceback
import os
import threading
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox,
    QGroupBox, QFormLayout, QTextEdit, QSplitter, QFrame, QToolBar
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QKeySequence

from core.model_loader import ModelLoader


class ViewerThread(threading.Thread):
    """3D查看器线程"""

    def __init__(self, model_data):
        super().__init__()
        self.daemon = True
        self.model_data = model_data
        self.viewer = None

    def run(self):
        try:
            from core.viewer_3d import Viewer3D
            self.viewer = Viewer3D()
            self.viewer.load_model(self.model_data)
            self.viewer.create_window(width=1024, height=768)
            self.viewer.run()
        except Exception as e:
            print(f"Viewer error: {e}")
            traceback.print_exc()


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.model_loader = ModelLoader()
        self.current_model = None
        self.current_file_path = None
        self.viewer_thread = None
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("3D Model Viewer")
        self.setGeometry(100, 100, 1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        left = QWidget()
        left.setFixedWidth(340)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(15)

        load_group = QGroupBox("Load Model")
        load_layout = QVBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select a model file...")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        self.load_btn = QPushButton("Load Model")
        self.load_btn.clicked.connect(self._on_load)
        self.load_btn.setStyleSheet("QPushButton { padding: 8px; font-weight: bold; background-color: #2196F3; color: white; border-radius: 3px; } QPushButton:hover { background-color: #1976D2; }")
        self.view_btn = QPushButton("View Model")
        self.view_btn.clicked.connect(self._on_view)
        self.view_btn.setEnabled(False)
        self.view_btn.setStyleSheet("QPushButton { padding: 8px; font-weight: bold; background-color: #4CAF50; color: white; border-radius: 3px; } QPushButton:disabled { background-color: #ccc; color: #999; }")
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._on_clear)
        self.clear_btn.setEnabled(False)
        self.clear_btn.setStyleSheet("QPushButton { padding: 8px; background-color: #f44336; color: white; border-radius: 3px; } QPushButton:disabled { background-color: #ccc; }")

        load_layout.addWidget(self.file_edit)
        load_layout.addWidget(browse_btn)
        load_layout.addWidget(self.load_btn)
        load_layout.addWidget(self.view_btn)
        load_layout.addWidget(self.clear_btn)
        load_group.setLayout(load_layout)
        left_layout.addWidget(load_group)

        info_group = QGroupBox("Model Info")
        info_layout = QVBoxLayout()
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setStyleSheet("font-family: Consolas; font-size: 12px;")
        self.info_text.setHtml("<i style='color: #999;'>No model loaded...</i>")
        info_layout.addWidget(self.info_text)
        info_group.setLayout(info_layout)
        left_layout.addWidget(info_group)

        help_group = QGroupBox("Controls")
        help_layout = QVBoxLayout()
        help_label = QLabel(
            "<b>3D Viewer Controls:</b><br><br>"
            "Left Drag: Rotate<br>"
            "Right Drag: Pan<br>"
            "Mouse Wheel: Zoom<br>"
            "W: Toggle Wireframe<br>"
            "A: Toggle Axes<br>"
            "R: Reset View<br>"
            "M: Measurement Mode<br>"
            "C: Clear Measurement<br>"
            "ESC: Close Viewer"
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("font-size: 12px; color: #555;")
        help_layout.addWidget(help_label)
        help_group.setLayout(help_layout)
        left_layout.addWidget(help_group)

        left_layout.addStretch()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)

        viewer_box = QGroupBox("Viewer")
        viewer_layout = QVBoxLayout()
        placeholder = QLabel()
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(
            "QLabel { background-color: #f5f5f5; border: 2px dashed #ccc; "
            "border-radius: 5px; color: #888; font-size: 14px; }"
        )
        placeholder.setText(
            "<html><center><h3>3D Model Viewer</h3>"
            "<p>Load a model using the 'Load Model' button,<br>"
            "then click 'View Model' to open the viewer window.<br><br>"
            "<b>Supported formats:</b> PLY, OBJ, STL, GLTF, GLB</p></center></html>"
        )
        viewer_layout.addWidget(placeholder)
        viewer_box.setLayout(viewer_layout)
        right_layout.addWidget(viewer_box)

        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas; font-size: 12px; background-color: #fafafa;")
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([340, 860])
        layout.addWidget(splitter)

    def _on_browse(self):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open 3D Model", "",
            "All Supported (*.ply *.obj *.stl *.gltf *.glb);;PLY Files (*.ply);;OBJ Files (*.obj);;STL Files (*.stl);;GLTF Files (*.gltf *.glb)"
        )
        if file_path:
            self.file_edit.setText(file_path)

    def _on_load(self):
        """加载模型"""
        file_path = self.file_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, "No File", "Please select a model file first.")
            return
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "File Not Found", f"File not found:\n{file_path}")
            return

        self._log(f"Loading: {file_path}")
        try:
            model = self.model_loader.load(file_path)

            if model and model.vertices:
                self.current_model = model
                self.current_file_path = file_path
                self.view_btn.setEnabled(True)
                self.clear_btn.setEnabled(True)
                self._update_info()
                self._log(f"✓ Loaded: {len(model.vertices)} vertices, {len(model.triangles)} triangles")
            else:
                QMessageBox.warning(self, "Load Failed", "Failed to load model file.")
                self._log("✗ Failed to load model")
        except Exception as e:
            self._log(f"✗ Error: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to load:\n{e}")

    def _on_view(self):
        """打开查看器"""
        if self.current_model is None:
            return

        self.viewer_thread = ViewerThread(self.current_model)
        self.viewer_thread.start()
        self._log("Viewer window opened")

    def _on_clear(self):
        """清除模型"""
        self.current_model = None
        self.current_file_path = None
        self.view_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.file_edit.clear()
        self.info_text.setHtml("<i style='color: #999;'>No model loaded...</i>")
        self._log("Model cleared")

    def _update_info(self):
        """更新信息面板"""
        model = self.current_model
        if model is None:
            return

        vertices = getattr(model, 'vertices', [])
        triangles = getattr(model, 'triangles', [])
        normals = getattr(model, 'normals', [])
        colors = getattr(model, 'colors', None)
        texcoords = getattr(model, 'texcoords', None)
        texture_path = getattr(model, 'texture_path', '')
        fmt = getattr(model, 'format', 'Unknown')

        html_lines = []
        html_lines.append("<b>=== Basic ===</b>")
        html_lines.append(f"Format: {fmt}")
        html_lines.append(f"Vertices: {len(vertices):,}")
        html_lines.append(f"Triangles: {len(triangles):,}")
        html_lines.append(f"Normals: {'Yes' if normals and len(normals) > 0 else 'No'}")
        html_lines.append(f"Vertex Colors: {'Yes' if colors and len(colors) > 0 else 'No'}")
        html_lines.append(f"Tex Coords: {'Yes' if texcoords and len(texcoords) > 0 else 'No'}")
        html_lines.append(f"Texture: {os.path.basename(texture_path) if texture_path else 'None'}")

        html_lines.append("")
        html_lines.append("<b>=== Bounding Box ===</b>")
        if vertices:
            import numpy as np
            verts = np.array(vertices)
            bb_min = verts.min(axis=0)
            bb_max = verts.max(axis=0)
            bb_size = bb_max - bb_min
            center = (bb_min + bb_max) / 2
            html_lines.append(f"Min: ({bb_min[0]:.3f}, {bb_min[1]:.3f}, {bb_min[2]:.3f})")
            html_lines.append(f"Max: ({bb_max[0]:.3f}, {bb_max[1]:.3f}, {bb_max[2]:.3f})")
            html_lines.append(f"Size: ({bb_size[0]:.3f}, {bb_size[1]:.3f}, {bb_size[2]:.3f})")
            html_lines.append(f"Center: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")

        if self.current_file_path:
            html_lines.append("")
            html_lines.append("<b>=== File ===</b>")
            html_lines.append(self.current_file_path)

        html = "<html><body>"
        for line in html_lines:
            if line.startswith('<b>'):
                html += f"<p style='margin: 5px 0;'>{line}</p>"
            elif line == "":
                html += "<br>"
            else:
                html += f"<p style='margin: 2px 0; font-family: monospace;'>{line}</p>"
        html += "</body></html>"

        self.info_text.setHtml(html)

    def _log(self, message: str):
        """添加日志"""
        self.log_text.append(message)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("3D Model Viewer")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
