"""
VideoToPPT - 视频转PPT演示文稿
基于opencv-video2ppt等开源项目优化，增加去重、OCR、模板等功能
"""

import sys
from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
