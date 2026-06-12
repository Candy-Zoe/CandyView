"""
ObjectDetection 主窗口 - 视频移动物体检测
"""

import os
import sys
import traceback
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QDoubleSpinBox,
    QProgressBar, QMessageBox, QTextEdit, QGroupBox, QFormLayout,
    QComboBox, QCheckBox, QSpinBox, QListWidget, QListWidgetItem,
    QSplitter, QColorDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QColor


class DetectionThread(QThread):
    """后台处理线程"""
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, video_path, output_mode, params):
        super().__init__()
        self.video_path = video_path
        self.output_mode = output_mode
        self.params = params

    def run(self):
        try:
            from core.video_processor import VideoProcessor

            box_color = self.params.get('box_color', (0, 255, 0))

            processor = VideoProcessor(
                video_path=self.video_path,
                algorithm=self.params.get('algorithm', 'mog2'),
                min_area=int(self.params.get('min_area', 500)),
                max_area=int(self.params.get('max_area', 50000)),
                blur_kernel=int(self.params.get('blur_kernel', 5)),
                threshold_value=int(self.params.get('threshold_value', 25)),
                morphology_kernel=int(self.params.get('morphology_kernel', 5)),
                box_color=box_color,
                box_thickness=int(self.params.get('box_thickness', 2)),
            )

            processor.open()

            output_dir = self.params.get('output_dir', 'output')
            os.makedirs(output_dir, exist_ok=True)

            result = {}

            if self.output_mode == 'video':
                video_name = self.params.get('video_name', 'detected.mp4')
                if not video_name.lower().endswith('.mp4'):
                    video_name += '.mp4'
                video_path = os.path.join(output_dir, video_name)
                out, processed = processor.process_video(
                    output_path=video_path,
                    progress_callback=lambda p, m: self.progress.emit(p, m),
                    skip_frames=int(self.params.get('skip_frames', 1)),
                    merge_boxes=self.params.get('merge_boxes', True),
                    merge_threshold=float(self.params.get('merge_threshold', 0.3)),
                    draw_info=self.params.get('draw_info', True),
                )
                result = {'type': 'video', 'video': out, 'frames_processed': processed}

            elif self.output_mode == 'snapshots':
                snap_dir = os.path.join(output_dir, self.params.get('snap_name', 'snapshots'))
                snapshots = processor.extract_snapshots(
                    output_dir=snap_dir,
                    min_interval_sec=float(self.params.get('snap_interval', 1.0)),
                    max_snapshots=int(self.params.get('max_snapshots', 50)),
                    progress_callback=lambda p, m: self.progress.emit(p, m),
                    merge_boxes=self.params.get('merge_boxes', True),
                    merge_threshold=float(self.params.get('merge_threshold', 0.3)),
                )
                result = {'type': 'snapshots', 'snapshot_dir': snap_dir,
                          'snapshots': snapshots, 'count': len(snapshots)}

            elif self.output_mode == 'both':
                video_name = self.params.get('video_name', 'detected.mp4')
                if not video_name.lower().endswith('.mp4'):
                    video_name += '.mp4'
                video_path = os.path.join(output_dir, video_name)
                snap_dir = os.path.join(output_dir, self.params.get('snap_name', 'snapshots'))

                combined = processor.process_and_extract(
                    video_output_path=video_path,
                    snapshot_output_dir=snap_dir,
                    progress_callback=lambda p, m: self.progress.emit(p, m),
                    skip_frames=int(self.params.get('skip_frames', 1)),
                    snapshot_interval_sec=float(self.params.get('snap_interval', 2.0)),
                    max_snapshots=int(self.params.get('max_snapshots', 50)),
                    merge_boxes=self.params.get('merge_boxes', True),
                    merge_threshold=float(self.params.get('merge_threshold', 0.3)),
                )
                result = {'type': 'both', 'video': combined['video'],
                          'snapshot_dir': snap_dir,
                          'snapshots': combined['snapshots'],
                          'snapshot_count': len(combined['snapshots'])}

            processor.close()
            self.progress.emit(100, "完成！")
            self.finished_ok.emit(result)

        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ObjectDetection - 视频移动物体检测")
        self.resize(1100, 750)

        self.thread = None
        self._current_box_color = (0, 255, 0)
        self._last_output_dir = None

        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 标题
        title = QLabel("🎥 视频移动物体检测")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # 视频选择
        input_grp = QGroupBox("① 选择视频文件")
        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择视频文件 (mp4, avi, mov, mkv 等)")
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._select_video)
        input_layout.addWidget(self.input_edit, 1)
        input_layout.addWidget(browse_btn)
        input_grp.setLayout(input_layout)
        main_layout.addWidget(input_grp)

        # 主内容区
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 2)

        # 左：参数面板
        params_panel = QWidget()
        params_layout = QVBoxLayout(params_panel)
        params_layout.setContentsMargins(0, 0, 0, 0)

        # 检测算法
        alg_grp = QGroupBox("② 检测算法")
        alg_form = QFormLayout()

        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItem("MOG2 背景减法 (推荐)", "mog2")
        self.algorithm_combo.addItem("KNN 背景减法", "knn")
        self.algorithm_combo.addItem("帧差法 (简单快速)", "frame_diff")
        self.algorithm_combo.addItem("多帧差法 (抗噪)", "multi_diff")
        alg_form.addRow("算法:", self.algorithm_combo)

        self.min_area_spin = QSpinBox()
        self.min_area_spin.setRange(10, 50000)
        self.min_area_spin.setValue(500)
        self.min_area_spin.setSuffix(" 像素")
        alg_form.addRow("最小物体面积:", self.min_area_spin)

        self.max_area_spin = QSpinBox()
        self.max_area_spin.setRange(0, 5000000)
        self.max_area_spin.setValue(50000)
        self.max_area_spin.setSuffix(" 像素")
        alg_form.addRow("最大物体面积 (0不限):", self.max_area_spin)

        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 100)
        self.threshold_spin.setValue(25)
        alg_form.addRow("差异阈值:", self.threshold_spin)

        self.blur_spin = QSpinBox()
        self.blur_spin.setRange(1, 31)
        self.blur_spin.setSingleStep(2)
        self.blur_spin.setValue(5)
        alg_form.addRow("模糊核大小:", self.blur_spin)

        self.morphology_spin = QSpinBox()
        self.morphology_spin.setRange(1, 21)
        self.morphology_spin.setSingleStep(2)
        self.morphology_spin.setValue(5)
        alg_form.addRow("形态学核大小:", self.morphology_spin)

        self.merge_boxes_check = QCheckBox("合并重叠检测框")
        self.merge_boxes_check.setChecked(True)
        alg_form.addRow("", self.merge_boxes_check)

        self.merge_threshold_spin = QDoubleSpinBox()
        self.merge_threshold_spin.setRange(0.0, 1.0)
        self.merge_threshold_spin.setValue(0.3)
        self.merge_threshold_spin.setSingleStep(0.05)
        alg_form.addRow("合并重叠阈值:", self.merge_threshold_spin)

        alg_grp.setLayout(alg_form)
        params_layout.addWidget(alg_grp)

        # 显示设置
        display_grp = QGroupBox("③ 显示设置")
        display_form = QFormLayout()

        self.box_thickness_spin = QSpinBox()
        self.box_thickness_spin.setRange(1, 10)
        self.box_thickness_spin.setValue(2)
        display_form.addRow("检测框粗细:", self.box_thickness_spin)

        self.color_btn = QPushButton("  选择颜色  ")
        self.color_btn.setStyleSheet("background-color: rgb(0, 255, 0); color: black; padding: 6px;")
        self.color_btn.clicked.connect(self._choose_color)
        display_form.addRow("检测框颜色:", self.color_btn)

        self.draw_info_check = QCheckBox("在视频中绘制时间/物体数信息")
        self.draw_info_check.setChecked(True)
        display_form.addRow("", self.draw_info_check)

        display_grp.setLayout(display_form)
        params_layout.addWidget(display_grp)

        # 输出设置
        output_grp = QGroupBox("④ 输出设置")
        output_form = QFormLayout()

        self.output_mode_combo = QComboBox()
        self.output_mode_combo.addItem("生成带检测框的视频", "video")
        self.output_mode_combo.addItem("提取带检测框的截图", "snapshots")
        self.output_mode_combo.addItem("同时生成视频和截图", "both")
        output_form.addRow("输出类型:", self.output_mode_combo)

        self.skip_frames_spin = QSpinBox()
        self.skip_frames_spin.setRange(1, 10)
        self.skip_frames_spin.setValue(1)
        self.skip_frames_spin.setSuffix(" 帧")
        output_form.addRow("视频处理跳帧 (1=每帧):", self.skip_frames_spin)

        self.snap_interval_spin = QDoubleSpinBox()
        self.snap_interval_spin.setRange(0.5, 30.0)
        self.snap_interval_spin.setValue(2.0)
        self.snap_interval_spin.setSingleStep(0.5)
        self.snap_interval_spin.setSuffix(" 秒")
        output_form.addRow("截图最小时间间隔:", self.snap_interval_spin)

        self.max_snapshots_spin = QSpinBox()
        self.max_snapshots_spin.setRange(1, 500)
        self.max_snapshots_spin.setValue(50)
        output_form.addRow("最大截图数量:", self.max_snapshots_spin)

        self.video_name_edit = QLineEdit("detected.mp4")
        output_form.addRow("视频文件名:", self.video_name_edit)

        self.snap_name_edit = QLineEdit("snapshots")
        output_form.addRow("截图子目录名:", self.snap_name_edit)

        self.output_dir_edit = QLineEdit(os.path.abspath("output"))
        dir_btn = QPushButton("选择...")
        dir_btn.clicked.connect(self._select_output_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.output_dir_edit, 1)
        dir_row.addWidget(dir_btn)
        dir_wrap = QWidget()
        dir_wrap.setLayout(dir_row)
        output_form.addRow("输出目录:", dir_wrap)

        output_grp.setLayout(output_form)
        params_layout.addWidget(output_grp)

        params_layout.addStretch(1)
        splitter.addWidget(params_panel)

        # 右：日志 + 截图列表
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        log_grp = QGroupBox("📊 处理日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas; font-size: 12px;")
        log_layout.addWidget(self.log_text)
        log_grp.setLayout(log_layout)
        right_layout.addWidget(log_grp, 1)

        snap_grp = QGroupBox("🖼️ 提取的截图")
        snap_layout = QVBoxLayout()
        self.snap_list = QListWidget()
        self.snap_list.setViewMode(QListWidget.IconMode)
        self.snap_list.setIconSize(QSize(200, 120))
        self.snap_list.setResizeMode(QListWidget.Adjust)
        self.snap_list.setSpacing(8)
        snap_layout.addWidget(self.snap_list)
        snap_grp.setLayout(snap_layout)
        right_layout.addWidget(snap_grp, 2)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        # 按钮
        btn_layout = QHBoxLayout()
        self.convert_btn = QPushButton("🚀 开始检测")
        self.convert_btn.setMinimumHeight(48)
        self.convert_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; padding: 8px 20px;
                           font-weight: bold; font-size: 15px; border-radius: 6px; }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #bdbdbd; }
        """)
        self.convert_btn.clicked.connect(self._start_detection)
        btn_layout.addWidget(self.convert_btn, 2)

        self.open_btn = QPushButton("📂 打开输出目录")
        self.open_btn.setMinimumHeight(48)
        self.open_btn.clicked.connect(self._open_output)
        self.open_btn.setEnabled(False)
        btn_layout.addWidget(self.open_btn, 1)
        main_layout.addLayout(btn_layout)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setMinimumHeight(24)
        main_layout.addWidget(self.progress)

    def _select_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频", "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.webm *.flv *.wmv);;所有文件 (*.*)")
        if path:
            self.input_edit.setText(path)

    def _select_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录", "output")
        if path:
            self.output_dir_edit.setText(path)

    def _choose_color(self):
        color = QColorDialog.getColor(
            QColor(self._current_box_color[2], self._current_box_color[1],
                   self._current_box_color[0]),
            self, "选择检测框颜色")
        if color.isValid():
            self._current_box_color = (color.blue(), color.green(), color.red())
            self.color_btn.setStyleSheet(
                "background-color: rgb(%d, %d, %d); color: black; padding: 6px;" %
                (color.red(), color.green(), color.blue()))

    def _start_detection(self):
        path = self.input_edit.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "错误", "请选择有效的视频文件！")
            return

        params = {
            'algorithm': self.algorithm_combo.currentData(),
            'min_area': self.min_area_spin.value(),
            'max_area': self.max_area_spin.value(),
            'blur_kernel': self.blur_spin.value(),
            'threshold_value': self.threshold_spin.value(),
            'morphology_kernel': self.morphology_spin.value(),
            'merge_boxes': self.merge_boxes_check.isChecked(),
            'merge_threshold': self.merge_threshold_spin.value(),
            'box_color': self._current_box_color,
            'box_thickness': self.box_thickness_spin.value(),
            'draw_info': self.draw_info_check.isChecked(),
            'skip_frames': self.skip_frames_spin.value(),
            'snap_interval': self.snap_interval_spin.value(),
            'max_snapshots': self.max_snapshots_spin.value(),
            'video_name': self.video_name_edit.text().strip() or 'detected.mp4',
            'snap_name': self.snap_name_edit.text().strip() or 'snapshots',
            'output_dir': self.output_dir_edit.text().strip() or 'output',
        }

        self.convert_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.progress.setValue(0)
        self.log_text.clear()
        self.snap_list.clear()

        output_mode = self.output_mode_combo.currentData()
        self.thread = DetectionThread(path, output_mode, params)
        self.thread.progress.connect(self._on_progress)
        self.thread.finished_ok.connect(self._on_finished)
        self.thread.error.connect(self._on_error)
        self.thread.start()

    def _on_progress(self, val, msg):
        self.progress.setValue(val)
        self.log_text.append("[%3d%%] %s" % (val, msg))

    def _on_finished(self, result):
        self.convert_btn.setEnabled(True)
        self.open_btn.setEnabled(True)
        self.progress.setValue(100)

        result_type = result.get('type', '')
        msg_lines = []

        if result_type == 'video':
            msg_lines.append("视频生成完成！")
            msg_lines.append("路径: " + str(result.get('video', '')))
            msg_lines.append("处理帧数: " + str(result.get('frames_processed', 0)))
        elif result_type == 'snapshots':
            msg_lines.append("截图提取完成！")
            msg_lines.append("目录: " + str(result.get('snapshot_dir', '')))
            msg_lines.append("数量: " + str(result.get('count', 0)) + " 张")
            self._load_snapshots(result.get('snapshots', []))
        elif result_type == 'both':
            msg_lines.append("视频和截图生成完成！")
            msg_lines.append("视频: " + str(result.get('video', '')))
            msg_lines.append("截图目录: " + str(result.get('snapshot_dir', '')))
            msg_lines.append("截图数量: " + str(result.get('snapshot_count', 0)) + " 张")
            self._load_snapshots(result.get('snapshots', []))

        self.log_text.append("✅ " + "\n   ".join(msg_lines))
        QMessageBox.information(self, "成功", "\n".join(msg_lines))

        self._last_output_dir = self.output_dir_edit.text().strip() or 'output'

    def _load_snapshots(self, snapshots):
        for snap in snapshots:
            file_path = snap.get('file', '')
            if not file_path or not os.path.exists(file_path):
                continue
            pix = QPixmap(file_path).scaled(200, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon = QPixmap()
            item = QListWidgetItem()
            item.setIcon(pix)
            timestamp = snap.get('timestamp', 0)
            obj_count = snap.get('object_count', 0)
            item.setText("t=" + str(round(timestamp, 1)) + "s, " + str(obj_count) + " obj")
            item.setSizeHint(QSize(220, 170))
            self.snap_list.addItem(item)

    def _on_error(self, msg):
        self.convert_btn.setEnabled(True)
        self.log_text.append("❌ 错误: " + msg)
        QMessageBox.critical(self, "错误", msg)

    def _open_output(self):
        folder = self._last_output_dir or self.output_dir_edit.text().strip() or 'output'
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        if sys.platform.startswith('win'):
            os.startfile(folder)
        elif sys.platform == 'darwin':
            import subprocess
            subprocess.Popen(['open', folder])
        else:
            import subprocess
            subprocess.Popen(['xdg-open', folder])
