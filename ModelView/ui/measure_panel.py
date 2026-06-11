"""
测量面板
提供距离测量功能
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QLabel, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPalette


class MeasurePanel(QWidget):
    """测量面板"""

    # 信号定义
    measure_mode_toggled = pyqtSignal(bool)
    clear_all_clicked = pyqtSignal()
    delete_selected_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._measure_mode = False
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 测量模式切换按钮
        self.measure_btn = QPushButton("Measure Mode")
        self.measure_btn.setMinimumHeight(45)
        self.measure_btn.setCheckable(True)
        self.measure_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e68a00;
            }
            QPushButton:checked {
                background-color: #f44336;
            }
        """)
        self.measure_btn.toggled.connect(self._on_measure_toggled)
        layout.addWidget(self.measure_btn)

        # 清除按钮
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setMinimumHeight(35)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        layout.addWidget(self.clear_btn)

        # 分隔线
        layout.addWidget(self._create_separator())

        # 测量列表
        layout.addWidget(QLabel("<b>Measurements:</b>"))

        self.measure_list = QListWidget()
        self.measure_list.setAlternatingRowColors(True)
        self.measure_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 3px;
                background: white;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
        """)
        layout.addWidget(self.measure_list)

        # 删除选中按钮
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setMinimumHeight(35)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #757575;
            }
        """)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.delete_btn)

        layout.addStretch()

    def _create_separator(self) -> QFrame:
        """创建分隔线"""
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("QFrame { border: 1px solid #ddd; }")
        return sep

    def _on_measure_toggled(self, checked: bool):
        """测量模式切换"""
        self._measure_mode = checked
        self.measure_btn.setText("Exit Measure" if checked else "Measure Mode")
        self.measure_mode_toggled.emit(checked)

    def _on_clear_clicked(self):
        """清除所有测量"""
        self.measure_list.clear()
        self.clear_all_clicked.emit()

    def _on_delete_clicked(self):
        """删除选中的测量"""
        current_row = self.measure_list.currentRow()
        if current_row >= 0:
            self.measure_list.takeItem(current_row)
            self.delete_selected_clicked.emit(current_row)

    def add_measurement(self, index: int, distance: float) -> None:
        """
        添加一条测量到列表

        Args:
            index: 测量索引
            distance: 距离值
        """
        item_text = f"Line {index + 1}: {distance:.4f} units"
        self.measure_list.addItem(item_text)

    def clear_measurements(self) -> None:
        """清空测量列表"""
        self.measure_list.clear()

    def is_measure_mode(self) -> bool:
        """是否处于测量模式"""
        return self._measure_mode

    def get_selected_index(self) -> int:
        """获取选中的索引"""
        return self.measure_list.currentRow()

    def show_message(self, title: str, message: str, icon=QMessageBox.Information) -> None:
        """显示消息对话框"""
        msg_box = QMessageBox()
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec_()
