"""
信息面板
显示模型详细信息
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QLabel, QFrame
)
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt


class InfoPanel(QWidget):
    """信息面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 标题
        title = QLabel("<b>Model Information</b>")
        title.setStyleSheet("font-size: 14px; color: #333;")
        layout.addWidget(title)

        # 分隔线
        layout.addWidget(self._create_separator())

        # 信息文本框
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: #fafafa;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.info_text)

        layout.addStretch()

    def _create_separator(self) -> QFrame:
        """创建分隔线"""
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("QFrame { border: 1px solid #ddd; }")
        return sep

    def update_info(self, info: dict) -> None:
        """
        更新模型信息显示

        Args:
            info: 包含模型信息的字典
        """
        text_lines = []

        # 基本信息
        text_lines.append("<b>=== Model Info ===</b>")
        text_lines.append(f"Format: {info.get('format', 'N/A')}")
        text_lines.append(f"Vertices: {info.get('vertices', 0):,}")
        text_lines.append(f"Triangles: {info.get('triangles', 0):,}")
        text_lines.append(f"Has Texture: {'Yes' if info.get('has_texture') else 'No'}")
        text_lines.append(f"Has Vertex Colors: {'Yes' if info.get('has_vertex_colors') else 'No'}")
        text_lines.append(f"Has Normals: {'Yes' if info.get('has_normals') else 'No'}")

        text_lines.append("")
        text_lines.append("<b>=== Bounding Box ===</b>")

        bb_min = info.get('bounding_box_min', (0, 0, 0))
        bb_max = info.get('bounding_box_max', (0, 0, 0))
        bb_size = info.get('bounding_box_size', (0, 0, 0))

        text_lines.append(f"Min: ({bb_min[0]:.4f}, {bb_min[1]:.4f}, {bb_min[2]:.4f})")
        text_lines.append(f"Max: ({bb_max[0]:.4f}, {bb_max[1]:.4f}, {bb_max[2]:.4f})")
        text_lines.append(f"Size: ({bb_size[0]:.4f}, {bb_size[1]:.4f}, {bb_size[2]:.4f})")

        text_lines.append("")
        text_lines.append("<b>=== Center ===</b>")
        center = info.get('center', (0, 0, 0))
        text_lines.append(f"({center[0]:.4f}, {center[1]:.4f}, {center[2]:.4f})")

        # 文件路径
        if info.get('file_path'):
            text_lines.append("")
            text_lines.append("<b>=== File ===</b>")
            text_lines.append(info.get('file_path', ''))

        # 组装HTML
        html = "<html><body>"
        for line in text_lines:
            if line.startswith('<b>'):
                html += f"<p style='margin: 5px 0;'>{line}</p>"
            else:
                html += f"<p style='margin: 2px 0; font-family: monospace;'>{line}</p>"
        html += "</body></html>"

        self.info_text.setHtml(html)

    def clear_info(self) -> None:
        """清空信息显示"""
        self.info_text.clear()
        self.info_text.setHtml("<html><body><i style='color: #999;'>No model loaded</i></body></html>")

    def set_placeholder(self) -> None:
        """显示占位文本"""
        self.info_text.setHtml("<html><body><i style='color: #999;'>Load a model to see information...</i></body></html>")
