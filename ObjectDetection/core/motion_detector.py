"""
移动目标检测器 - 基于背景建模、帧差法、轮廓检测等多种算法
从视频中检测移动的物体并生成矩形检测框
"""

import cv2
import numpy as np
import time
from collections import deque


class MotionDetector:
    """移动目标检测器"""

    ALGORITHMS = {
        'mog2': 'MOG2 背景减法',
        'knn': 'KNN 背景减法',
        'frame_diff': '帧差法',
        'multi_diff': '多帧差法',
    }

    def __init__(self, algorithm='mog2', min_area=500, max_area=50000,
                 blur_kernel=5, threshold_value=25, morphology_kernel=5):
        self.algorithm = algorithm
        self.min_area = min_area
        self.max_area = max_area
        self.blur_kernel = blur_kernel
        self.threshold_value = threshold_value
        self.morphology_kernel = morphology_kernel

        # 初始化背景减法器
        self.bg_subtractor = None
        if algorithm == 'mog2':
            self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=500, varThreshold=50, detectShadows=True)
        elif algorithm == 'knn':
            self.bg_subtractor = cv2.createBackgroundSubtractorKNN(
                history=500, dist2Threshold=400.0, detectShadows=True)

        # 帧差法使用的历史帧
        self.prev_gray = None
        self.prev_gray_2 = None  # 用于多帧差法
        self.frame_history = deque(maxlen=10)

        # 检测统计
        self.detection_count = 0

    def detect(self, frame):
        """
        检测帧中的移动物体

        参数:
            frame: numpy.ndarray BGR 格式

        返回:
            list[(x, y, w, h)]: 检测到的物体边界框列表
            np.ndarray: 前景掩膜（用于调试）
        """
        if frame is None or frame.size == 0:
            return [], None

        if self.algorithm == 'frame_diff':
            return self._detect_frame_diff(frame)
        elif self.algorithm == 'multi_diff':
            return self._detect_multi_diff(frame)
        elif self.algorithm in ('mog2', 'knn'):
            return self._detect_bg_subtraction(frame)
        else:
            return self._detect_bg_subtraction(frame)

    def _detect_bg_subtraction(self, frame):
        """背景减法（MOG2 / KNN）"""
        if self.bg_subtractor is None:
            return [], None

        # 高斯模糊去噪
        blurred = cv2.GaussianBlur(frame, (self.blur_kernel, self.blur_kernel), 0)

        # 应用背景减法
        fg_mask = self.bg_subtractor.apply(blurred)

        # 去除阴影（阴影区域被标记为127）
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        # 形态学操作：填充空洞 + 去噪
        kernel = np.ones((self.morphology_kernel, self.morphology_kernel), np.uint8)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

        return self._extract_boxes(fg_mask, frame)

    def _detect_frame_diff(self, frame):
        """简单帧差法：当前帧 - 前一帧"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0)

        if self.prev_gray is None:
            self.prev_gray = gray
            return [], None

        # 帧差
        diff = cv2.absdiff(gray, self.prev_gray)
        self.prev_gray = gray.copy()

        # 二值化
        _, fg_mask = cv2.threshold(diff, self.threshold_value, 255, cv2.THRESH_BINARY)

        # 形态学
        kernel = np.ones((self.morphology_kernel, self.morphology_kernel), np.uint8)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

        return self._extract_boxes(fg_mask, frame)

    def _detect_multi_diff(self, frame):
        """多帧差法：利用三帧差提高鲁棒性"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0)

        if self.prev_gray is None:
            self.prev_gray = gray
            return [], None
        if self.prev_gray_2 is None:
            self.prev_gray_2 = self.prev_gray.copy()
            self.prev_gray = gray.copy()
            return [], None

        # 两帧差相与（d1 AND d2）
        d1 = cv2.absdiff(gray, self.prev_gray)
        d2 = cv2.absdiff(self.prev_gray, self.prev_gray_2)
        diff = cv2.bitwise_and(d1, d2)

        self.prev_gray_2 = self.prev_gray.copy()
        self.prev_gray = gray.copy()

        # 二值化
        _, fg_mask = cv2.threshold(diff, self.threshold_value, 255, cv2.THRESH_BINARY)

        # 形态学
        kernel = np.ones((self.morphology_kernel, self.morphology_kernel), np.uint8)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

        return self._extract_boxes(fg_mask, frame)

    def _extract_boxes(self, fg_mask, frame):
        """从前景掩膜中提取边界框"""
        if fg_mask is None:
            return [], None

        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes = []
        h, w = frame.shape[:2]
        frame_area = h * w

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_area:
                continue
            if self.max_area > 0 and area > self.max_area:
                continue
            # 不允许过大的框（超过画面60%）
            if area > frame_area * 0.6:
                continue
            x, y, w_box, h_box = cv2.boundingRect(contour)
            boxes.append((int(x), int(y), int(w_box), int(h_box)))

        self.detection_count += len(boxes)
        return boxes, fg_mask

    @staticmethod
    def draw_boxes(frame, boxes, color=(0, 255, 0), thickness=2, labels=None):
        """
        在帧上绘制检测框

        参数:
            frame: numpy.ndarray BGR
            boxes: list[(x, y, w, h)]
            color: BGR 颜色元组
            thickness: 线条粗细
            labels: 可选的标签列表
        """
        if frame is None:
            return frame
        result = frame.copy()
        for i, (x, y, w, h) in enumerate(boxes):
            cv2.rectangle(result, (x, y), (x + w, y + h), color, thickness)
            if labels and i < len(labels):
                label = labels[i]
                cv2.putText(result, label, (x, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            else:
                cv2.putText(result, "#" + str(i + 1), (x, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return result

    def reset(self):
        """重置检测器状态"""
        if self.algorithm == 'mog2':
            self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=500, varThreshold=50, detectShadows=True)
        elif self.algorithm == 'knn':
            self.bg_subtractor = cv2.createBackgroundSubtractorKNN(
                history=500, dist2Threshold=400.0, detectShadows=True)
        self.prev_gray = None
        self.prev_gray_2 = None
        self.detection_count = 0


def merge_overlapping_boxes(boxes, overlap_threshold=0.3):
    """
    合并重叠的检测框

    参数:
        boxes: list[(x, y, w, h)]
        overlap_threshold: 重叠面积阈值 (0~1)
    """
    if len(boxes) <= 1:
        return boxes

    # 按面积从大到小排序
    boxes_sorted = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
    result = []
    used = [False] * len(boxes_sorted)

    for i, box in enumerate(boxes_sorted):
        if used[i]:
            continue
        x1, y1, w1, h1 = box
        merged_x1, merged_y1 = x1, y1
        merged_x2, merged_y2 = x1 + w1, y1 + h1
        used[i] = True

        for j in range(i + 1, len(boxes_sorted)):
            if used[j]:
                continue
            x2, y2, w2, h2 = boxes_sorted[j]
            bx2, by2 = x2 + w2, y2 + h2

            # 计算重叠
            ix1 = max(merged_x1, x2)
            iy1 = max(merged_y1, y2)
            ix2 = min(merged_x2, bx2)
            iy2 = min(merged_y2, by2)
            if ix2 <= ix1 or iy2 <= iy1:
                continue
            overlap_area = (ix2 - ix1) * (iy2 - iy1)
            area_small = w2 * h2
            if overlap_area / max(area_small, 1) > overlap_threshold:
                used[j] = True
                merged_x1 = min(merged_x1, x2)
                merged_y1 = min(merged_y1, y2)
                merged_x2 = max(merged_x2, bx2)
                merged_y2 = max(merged_y2, by2)

        result.append((int(merged_x1), int(merged_y1),
                       int(merged_x2 - merged_x1), int(merged_y2 - merged_y1)))

    return result
