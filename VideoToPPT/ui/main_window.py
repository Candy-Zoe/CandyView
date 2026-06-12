"""
VideoToPPT 主窗口
"""

import os
import sys
import traceback
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QDoubleSpinBox,
    QProgressBar, QMessageBox, QTextEdit, QGroupBox, QFormLayout,
    QComboBox, QCheckBox, QSpinBox, QTabWidget, QListWidget, QListWidgetItem,
    QScrollArea, QSlider, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QImage, QFont

from core.video_frame_extractor import VideoFrameExtractor
from core.image_analyzer import ImageAnalyzer
from core.ppt_generator import PPTGenerator, TEMPLATES, build_presentation


class ConversionThread(QThread):
    """后台处理线程"""
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(str, list)  # (输出路径, 帧列表)
    error = pyqtSignal(str)

    def __init__(self, video_path, params):
        super().__init__()
        self.video_path = video_path
        self.params = params

    def run(self):
        try:
            video_path = self.video_path
            params = self.params

            # 1. 提取帧
            self.progress.emit(3, "打开视频...")
            extractor = VideoFrameExtractor(video_path)
            extractor.open()

            def cb_extract(percent, msg):
                self.progress.emit(int(5 + percent * 0.4), f"[抽帧] {msg}")

            frames = extractor.extract(
                sample_interval_sec=float(params['sample_interval_sec']),
                similarity_threshold=float(params['similarity_threshold']),
                min_sharpness=float(params['min_sharpness']),
                enable_dedup=params['enable_dedup'],
                enable_sharpness_filter=params['enable_sharpness_filter'],
                progress_callback=cb_extract,
            )

            if not frames:
                self.error.emit("未能从视频中提取到有效帧，请检查视频文件或降低采样间隔/清晰度阈值")
                return

            self.progress.emit(50, f"已提取 {len(frames)} 帧，开始分析...")

            # 2. 分析每一帧
            analyzer = ImageAnalyzer(tesseract_cmd=params.get('tesseract_cmd'))
            analyzed = []
            for i, frame in enumerate(frames):
                analysis = analyzer.analyze(
                    frame['image'],
                    index=i,
                    timestamp=frame['timestamp'],
                    enable_ocr=params['enable_ocr'],
                    lang=params.get('ocr_lang', 'eng'),
                )
                analyzed.append({
                    'image': frame['image'],
                    'analysis': analysis,
                    'frame_index': frame['frame_index'],
                    'timestamp': frame['timestamp'],
                    'sharpness': frame['sharpness'],
                })
                percent = int(50 + 30.0 * (i + 1) / len(frames))
                self.progress.emit(percent, f"分析第 {i + 1}/{len(frames)} 帧...")

            extractor.close()

            # 3. 生成 PPT
            output_dir = params.get('output_dir') or 'output'
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, params.get('output_name', 'presentation.pptx'))
            if not output_path.lower().endswith('.pptx'):
                output_path += '.pptx'

            def cb_ppt(percent, msg):
                self.progress.emit(percent, msg)

            build_presentation(
                frames_with_analysis=analyzed,
                output_path=output_path,
                template=params['template'],
                title=params['ppt_title'],
                subtitle=params['ppt_subtitle'],
                image_layout=params['image_layout'],
                include_ocr=params['enable_ocr'],
                progress_callback=cb_ppt,
            )

            self.progress.emit(100, "完成！")
            self.finished_ok.emit(output_path, analyzed)

        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))


class ThumbnailList(QListWidget):
    """展示帧缩略图的列表"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(240, 135))
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Static)
        self.setSpacing(10)
        self.setUniformItemSizes(True)
        self.setWrapping(True)

    def add_frames(self, frames):
        self.clear()
        for i, item in enumerate(frames):
            img = item['image']
            h, w, ch = img.shape
            qimg = QImage(img.data, w, h, ch * w, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg).scaled(240, 135, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            analysis = item.get('analysis', {})
            title = analysis.get('title') or f"帧 {i + 1}"
            subtitle = f"t={item.get('timestamp', 0):.1f}s"
            display = f"{i + 1}. {title[:30]}\n  {subtitle}"

            list_item = QListWidgetItem(self)
            list_item.setIcon(pix)
            list_item.setText(display)
            list_item.setSizeHint(QSize(250, 180))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VideoToPPT - 视频转PPT")
        self.resize(1200, 800)

        self.thread = None
        self.last_frames = []
        self.last_output = ""

        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 标题
        title = QLabel("🎞️ VideoToPPT - 自动从视频中提取关键帧并生成PPT")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # 输入区域
        input_grp = QGroupBox("① 选择视频")
        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("选择视频文件 (mp4, avi, mov, mkv 等)")
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._select_video)
        input_layout.addWidget(self.input_edit, 1)
        input_layout.addWidget(browse_btn)
        input_grp.setLayout(input_layout)
        main_layout.addWidget(input_grp)

        # 参数区域 (Tab)
        tabs = QTabWidget()
        main_layout.addWidget(tabs, 1)

        # Tab1: 抽帧参数
        tab1 = QWidget()
        tab1_layout = QFormLayout(tab1)
        tab1_layout.setContentsMargins(20, 20, 20, 20)
        tab1_layout.setSpacing(12)

        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 30.0)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setSingleStep(0.1)
        self.interval_spin.setSuffix(" 秒")
        tab1_layout.addRow("采样间隔:", self.interval_spin)

        self.similarity_combo = QComboBox()
        self.similarity_combo.addItems([
            "严格去重 (90%)",
            "标准去重 (85%)",
            "宽松去重 (70%)",
            "不做去重",
        ])
        self.similarity_combo.setCurrentIndex(1)
        tab1_layout.addRow("去重强度:", self.similarity_combo)

        self.sharpness_spin = QDoubleSpinBox()
        self.sharpness_spin.setRange(0.0, 500.0)
        self.sharpness_spin.setValue(50.0)
        self.sharpness_spin.setSingleStep(5.0)
        tab1_layout.addRow("最低清晰度:", self.sharpness_spin)

        self.enable_dedup = QCheckBox("启用帧去重（推荐）")
        self.enable_dedup.setChecked(True)
        tab1_layout.addRow("", self.enable_dedup)

        self.enable_sharpness = QCheckBox("过滤模糊帧（推荐）")
        self.enable_sharpness.setChecked(True)
        tab1_layout.addRow("", self.enable_sharpness)

        tabs.addTab(tab1, "🎬 抽帧参数")

        # Tab2: OCR 和 内容
        tab2 = QWidget()
        tab2_layout = QFormLayout(tab2)
        tab2_layout.setContentsMargins(20, 20, 20, 20)
        tab2_layout.setSpacing(12)

        self.enable_ocr = QCheckBox("启用 OCR 文字识别（需安装 Tesseract）")
        self.enable_ocr.setChecked(False)
        tab2_layout.addRow("", self.enable_ocr)

        self.ocr_lang = QComboBox()
        self.ocr_lang.addItems(["eng (英文)", "chi_sim (简体中文)", "eng+chi_sim (中英混合)"])
        tab2_layout.addRow("OCR 语言:", self.ocr_lang)

        self.tesseract_path_edit = QLineEdit()
        self.tesseract_path_edit.setPlaceholderText("可选 - 指定 tesseract.exe 路径 (留空则用默认)")
        btn_ocr = QPushButton("浏览...")
        btn_ocr.clicked.connect(self._select_tesseract)
        ocr_path_row = QHBoxLayout()
        ocr_path_row.addWidget(self.tesseract_path_edit, 1)
        ocr_path_row.addWidget(btn_ocr)
        ocr_path_wrap = QWidget()
        ocr_path_wrap.setLayout(ocr_path_row)
        tab2_layout.addRow("Tesseract 路径:", ocr_path_wrap)

        tabs.addTab(tab2, "📝 内容识别")

        # Tab3: PPT 模板
        tab3 = QWidget()
        tab3_layout = QFormLayout(tab3)
        tab3_layout.setContentsMargins(20, 20, 20, 20)
        tab3_layout.setSpacing(12)

        self.template_combo = QComboBox()
        for key, info in TEMPLATES.items():
            self.template_combo.addItem(info['name'], key)
        tab3_layout.addRow("PPT 模板:", self.template_combo)

        self.layout_combo = QComboBox()
        self.layout_combo.addItem("图文并排 - 图片在右侧", "right")
        self.layout_combo.addItem("图文并排 - 图片在左侧", "left")
        self.layout_combo.addItem("图片在上，文字在下", "top")
        self.layout_combo.addItem("图片全屏", "full")
        tab3_layout.addRow("图片布局:", self.layout_combo)

        self.title_edit = QLineEdit("视频要点总结")
        tab3_layout.addRow("封面标题:", self.title_edit)

        self.subtitle_edit = QLineEdit("由 VideoToPPT 自动生成")
        tab3_layout.addRow("封面副标题:", self.subtitle_edit)

        self.output_name_edit = QLineEdit("presentation.pptx")
        tab3_layout.addRow("输出文件名:", self.output_name_edit)

        self.output_dir_edit = QLineEdit(os.path.abspath("output"))
        btn_dir = QPushButton("选择...")
        btn_dir.clicked.connect(self._select_output_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.output_dir_edit, 1)
        dir_row.addWidget(btn_dir)
        dir_wrap = QWidget()
        dir_wrap.setLayout(dir_row)
        tab3_layout.addRow("输出目录:", dir_wrap)

        tabs.addTab(tab3, "🎨 PPT 样式")

        # 按钮区域
        btn_layout = QHBoxLayout()
        self.convert_btn = QPushButton("🚀 开始生成 PPT")
        self.convert_btn.setMinimumHeight(48)
        self.convert_btn.clicked.connect(self._start_convert)
        self.convert_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; padding: 8px 20px;
                           font-weight: bold; font-size: 15px; border-radius: 6px; }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #bdbdbd; }
        """)
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

        # 日志 + 缩略图
        splitter = QSplitter(Qt.Vertical)

        log_grp = QGroupBox("📊 日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas; font-size: 12px;")
        self.log_text.setMinimumHeight(120)
        log_layout.addWidget(self.log_text)
        log_grp.setLayout(log_layout)
        splitter.addWidget(log_grp)

        thumb_grp = QGroupBox("🖼️ 提取的关键帧")
        thumb_layout = QVBoxLayout()
        self.thumb_list = ThumbnailList()
        self.thumb_list.setMinimumHeight(220)
        thumb_layout.addWidget(self.thumb_list)
        thumb_grp.setLayout(thumb_layout)
        splitter.addWidget(thumb_grp)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter, 3)

    # -------- 事件处理 --------
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

    def _select_tesseract(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 tesseract.exe", "", "可执行文件 (*.exe);;所有文件 (*.*)")
        if path:
            self.tesseract_path_edit.setText(path)

    def _start_convert(self):
        path = self.input_edit.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "错误", "请选择有效的视频文件！")
            return

        # 去重阈值映射
        sim_map = {0: 0.9, 1: 0.85, 2: 0.70, 3: 0.0}
        sim_threshold = sim_map.get(self.similarity_combo.currentIndex(), 0.85)

        ocr_lang_map = {0: 'eng', 1: 'chi_sim', 2: 'eng+chi_sim'}
        ocr_lang = ocr_lang_map.get(self.ocr_lang.currentIndex(), 'eng')

        template_key = self.template_combo.currentData() or 'modern'
        image_layout = self.layout_combo.currentData() or 'right'

        params = {
            'sample_interval_sec': self.interval_spin.value(),
            'similarity_threshold': sim_threshold,
            'min_sharpness': self.sharpness_spin.value(),
            'enable_dedup': self.enable_dedup.isChecked(),
            'enable_sharpness_filter': self.enable_sharpness.isChecked(),
            'enable_ocr': self.enable_ocr.isChecked(),
            'ocr_lang': ocr_lang,
            'tesseract_cmd': self.tesseract_path_edit.text().strip() or None,
            'template': template_key,
            'image_layout': image_layout,
            'ppt_title': self.title_edit.text().strip() or '视频要点',
            'ppt_subtitle': self.subtitle_edit.text().strip(),
            'output_name': self.output_name_edit.text().strip() or 'presentation.pptx',
            'output_dir': self.output_dir_edit.text().strip() or 'output',
        }

        self.convert_btn.setEnabled(False)
        self.progress.setValue(0)
        self.log_text.clear()
        self.thumb_list.clear()

        self.thread = ConversionThread(path, params)
        self.thread.progress.connect(self._on_progress)
        self.thread.finished_ok.connect(self._on_finished)
        self.thread.error.connect(self._on_error)
        self.thread.start()

    def _on_progress(self, val, msg):
        self.progress.setValue(val)
        self.log_text.append(f"[{val:>3}%] {msg}")

    def _on_finished(self, output_path, frames):
        self.last_output = output_path
        self.last_frames = frames
        self.convert_btn.setEnabled(True)
        self.open_btn.setEnabled(True)
        self.progress.setValue(100)
        self.log_text.append(f"✅ 完成！共提取 {len(frames)} 帧")
        self.log_text.append(f"📄 输出文件: {output_path}")
        self.thumb_list.add_frames(frames)
        QMessageBox.information(self, "成功", f"PPT 已生成！\n共 {len(frames)} 页\n\n{output_path}")

    def _on_error(self, msg):
        self.convert_btn.setEnabled(True)
        self.log_text.append(f"❌ 错误: {msg}")
        QMessageBox.critical(self, "错误", msg)

    def _open_output(self):
        if not self.last_output:
            return
        folder = os.path.dirname(os.path.abspath(self.last_output))
        if sys.platform.startswith('win'):
            os.startfile(folder)
        elif sys.platform == 'darwin':
            import subprocess
            subprocess.Popen(['open', folder])
        else:
            import subprocess
            subprocess.Popen(['xdg-open', folder])
