"""
ObjectDetection - 视频移动物体检测
从视频中检测移动的物体，可生成带矩形检测框的新视频或截图
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
