"""
变换控制面板
提供模型的旋转、缩放、平移控制
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QPushButton, QFrame, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class TransformPanel(QWidget):
    """变换控制面板"""

    # 信号定义
    scale_changed = pyqtSignal(float)
    rotate_x_changed = pyqtSignal(float)
    rotate_y_changed = pyqtSignal(float)
    rotate_z_changed = pyqtSignal(float)
    translate_x_changed = pyqtSignal(float)
    translate_y_changed = pyqtSignal(float)
    translate_z_changed = pyqtSignal(float)
    reset_clicked = pyqtSignal()
    load_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 按钮区域
        btn_layout = QHBoxLayout()
        self.load_btn = QPushButton("Load Model")
        self.load_btn.setMinimumHeight(40)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.load_btn.clicked.connect(self.load_clicked.emit)
        btn_layout.addWidget(self.load_btn)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setMinimumHeight(40)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.reset_btn.clicked.connect(self._on_reset_clicked)
        btn_layout.addWidget(self.reset_btn)
        layout.addLayout(btn_layout)

        # 分隔线
        layout.addWidget(self._create_separator())

        # 缩放控制
        layout.addWidget(QLabel("<b>Scale</b>"))
        self.scale_slider = self._create_hslider(0.1, 5.0, 1.0, 0.1)
        self.scale_slider.valueChanged.connect(self._on_scale_changed)
        layout.addWidget(self.scale_slider)

        layout.addWidget(self._create_separator())

        # 旋转控制
        rotate_group = QGroupBox("Rotation")
        rotate_layout = QGridLayout(rotate_group)

        self.rotate_x_slider = self._create_hslider(-180, 180, 0, 1)
        self.rotate_y_slider = self._create_hslider(-180, 180, 0, 1)
        self.rotate_z_slider = self._create_hslider(-180, 180, 0, 1)

        self.rotate_x_slider.valueChanged.connect(lambda v: self.rotate_x_changed.emit(v))
        self.rotate_y_slider.valueChanged.connect(lambda v: self.rotate_y_changed.emit(v))
        self.rotate_z_slider.valueChanged.connect(lambda v: self.rotate_z_changed.emit(v))

        rotate_layout.addWidget(QLabel("X:"), 0, 0)
        rotate_layout.addWidget(self.rotate_x_slider, 0, 1)
        rotate_layout.addWidget(QLabel("Y:"), 1, 0)
        rotate_layout.addWidget(self.rotate_y_slider, 1, 1)
        rotate_layout.addWidget(QLabel("Z:"), 2, 0)
        rotate_layout.addWidget(self.rotate_z_slider, 2, 1)

        layout.addWidget(rotate_group)

        layout.addWidget(self._create_separator())

        # 平移控制
        translate_group = QGroupBox("Translation")
        translate_layout = QGridLayout(translate_group)

        self.translate_x_slider = self._create_hslider(-10, 10, 0, 0.1)
        self.translate_y_slider = self._create_hslider(-10, 10, 0, 0.1)
        self.translate_z_slider = self._create_hslider(-10, 10, 0, 0.1)

        self.translate_x_slider.valueChanged.connect(lambda v: self.translate_x_changed.emit(v))
        self.translate_y_slider.valueChanged.connect(lambda v: self.translate_y_changed.emit(v))
        self.translate_z_slider.valueChanged.connect(lambda v: self.translate_z_changed.emit(v))

        translate_layout.addWidget(QLabel("X:"), 0, 0)
        translate_layout.addWidget(self.translate_x_slider, 0, 1)
        translate_layout.addWidget(QLabel("Y:"), 1, 0)
        translate_layout.addWidget(self.translate_y_slider, 1, 1)
        translate_layout.addWidget(QLabel("Z:"), 2, 0)
        translate_layout.addWidget(self.translate_z_slider, 2, 1)

        layout.addWidget(translate_group)

        layout.addStretch()

    def _create_hslider(self, min_val: float, max_val: float, default: float, step: float) -> QSlider:
        """创建水平滑块"""
        slider = QSlider(Qt.Horizontal)
        if step >= 1:
            slider.setRange(int(min_val), int(max_val))
            slider.setSingleStep(int(step))
        else:
            # 对于小数步长，使用整数范围然后转换
            multiplier = int(1 / step)
            slider.setRange(int(min_val * multiplier), int(max_val * multiplier))
            slider.setSingleStep(1)
            slider.setValue(int(default * multiplier))
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(int((max_val - min_val) / 10))
        return slider

    def _create_separator(self) -> QFrame:
        """创建分隔线"""
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("QFrame { border: 1px solid #ddd; }")
        return sep

    def _on_scale_changed(self, value: float):
        """缩放值改变"""
        # 处理小数步长
        actual_value = value / 10.0 if isinstance(value, int) and value > 100 else value
        self.scale_changed.emit(actual_value)
        # 重置滑块
        self.scale_slider.setValue(10)

    def _on_reset_clicked(self):
        """重置按钮点击"""
        self.reset_all_sliders()
        self.reset_clicked.emit()

    def reset_all_sliders(self):
        """重置所有滑块到默认值"""
        self.scale_slider.setValue(10)
        self.rotate_x_slider.setValue(0)
        self.rotate_y_slider.setValue(0)
        self.rotate_z_slider.setValue(0)
        self.translate_x_slider.setValue(0)
        self.translate_y_slider.setValue(0)
        self.translate_z_slider.setValue(0)

    def get_value_from_slider(self, slider: QSlider, is_float: bool = False) -> float:
        """从滑块获取值"""
        value = slider.value()
        if is_float:
            # 检测是否是浮点滑块
            if slider.maximum() > 100:
                return value / 10.0
        return value
