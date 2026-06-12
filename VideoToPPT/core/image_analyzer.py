"""
图像分析器 - 从提取的关键帧中提取文本内容和图像特征
支持：Tesseract OCR（可选），图像色彩分析，自动生成标题
"""

import cv2
import numpy as np
import re


class ImageAnalyzer:
    def __init__(self, tesseract_cmd=None):
        """
        tesseract_cmd: 可选 - 指定 tesseract 可执行文件路径
                       例如: 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
        """
        self.ocr_available = False
        self.ocr_engine = None

        try:
            import pytesseract
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            # 简单测试
            _ = pytesseract.image_to_string
            self.ocr_engine = pytesseract
            self.ocr_available = True
        except Exception:
            self.ocr_available = False

    @staticmethod
    def _clean_text(text):
        """清理OCR文本：去除多余空白、非法字符等"""
        if not text:
            return ""
        text = text.strip()
        # 去除控制字符但保留换行
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        # 合并多个空行为一个
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines)

    @staticmethod
    def _preprocess_for_ocr(img_rgb):
        """对图像做预处理以提升OCR效果"""
        if len(img_rgb.shape) == 2:
            gray = img_rgb
        else:
            gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

        # 自适应阈值 - 对幻灯片效果好
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 如果是深色背景浅色文字，反转
        if binary.mean() < 127:
            binary = 255 - binary

        # 轻微去噪
        denoised = cv2.medianBlur(binary, 3)
        return denoised

    def extract_text(self, img_rgb, lang='eng+chi_sim'):
        """
        从图像中提取文字
        返回: 文本字符串 (失败时返回空字符串)
        """
        if not self.ocr_available or self.ocr_engine is None:
            return ""
        try:
            preprocessed = self._preprocess_for_ocr(img_rgb)
            raw = self.ocr_engine.image_to_string(preprocessed, lang=lang, config='--psm 6')
            return self._clean_text(raw)
        except Exception:
            # 如果中文+英文识别失败，退回英文
            try:
                preprocessed = self._preprocess_for_ocr(img_rgb)
                raw = self.ocr_engine.image_to_string(preprocessed, lang='eng', config='--psm 6')
                return self._clean_text(raw)
            except Exception:
                return ""

    @staticmethod
    def dominant_colors(img_rgb, k=3):
        """提取图像的k个主色，返回[(rgb_tuple, percent), ...]"""
        try:
            pixels = img_rgb.reshape(-1, 3).astype(np.float32)
            # 使用K-means聚类（简单实现）
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
            centers = centers.astype(int)

            counts = np.bincount(labels.flatten(), minlength=k)
            total = counts.sum()

            results = []
            for i in range(k):
                percent = counts[i] / total if total > 0 else 0
                color = tuple(int(c) for c in centers[i])
                results.append((color, percent))
            results.sort(key=lambda x: x[1], reverse=True)
            return results
        except Exception:
            return [((255, 255, 255), 1.0)]

    @staticmethod
    def auto_title(img_rgb, index=0, timestamp=0):
        """当无OCR可用时，生成一个简单的标题"""
        return f"幻灯片 {index + 1} - {int(timestamp)}s"

    def analyze(self, img_rgb, index=0, timestamp=0, enable_ocr=True, lang='eng+chi_sim'):
        """
        分析一张图像，返回结构化内容：
        {
            'title': '标题',
            'content': '要点文本',
            'ocr_text': 'OCR原始文本',
            'dominant_colors': [...],
            'has_text': bool
        }
        """
        colors = self.dominant_colors(img_rgb)
        ocr_text = ""
        if enable_ocr:
            ocr_text = self.extract_text(img_rgb, lang=lang)

        # 根据OCR内容生成标题和要点
        title, bullet_points = self._summarize_text(ocr_text, index, timestamp)

        return {
            'title': title,
            'content': "\n".join(bullet_points) if bullet_points else "",
            'bullet_points': bullet_points,
            'ocr_text': ocr_text,
            'dominant_colors': colors,
            'has_text': len(ocr_text.strip()) > 0,
            'auto_title': self.auto_title(img_rgb, index, timestamp),
        }

    def _summarize_text(self, text, index=0, timestamp=0):
        """
        将OCR文本转换为 标题 + 要点列表
        简单策略：
            - 第一行非空且较短的作为标题
            - 其余按行分割作为要点
            - 过滤掉过短/过长的行
        """
        if not text.strip():
            return self.auto_title(None, index, timestamp) if False else (f"关键帧 {index + 1}", [])

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return f"关键帧 {index + 1}", []

        # 选择标题：最短且合理的第一行
        title = lines[0]
        if len(title) > 80:
            title = title[:80] + "..."

        # 其余作为要点，过滤掉过短（可能是噪声）和过长的
        bullets = []
        for line in lines[1:]:
            if 3 <= len(line) <= 200:
                bullets.append(line)
                if len(bullets) >= 6:  # 每个幻灯片最多6个要点
                    break

        return title, bullets
