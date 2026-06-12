"""
视频帧提取器 - 从视频中提取关键帧
支持多种去重策略和关键帧检测
"""

import cv2
import numpy as np
from scipy import stats
import os


class VideoFrameExtractor:
    def __init__(self, video_path):
        self.video_path = video_path
        self.cap = None
        self.total_frames = 0
        self.fps = 0
        self.duration = 0
        self.width = 0
        self.height = 0

    def open(self):
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开视频: {self.video_path}")
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.duration = self.total_frames / self.fps if self.fps > 0 else 0
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return True

    def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None

    def get_info(self):
        return {
            'path': self.video_path,
            'total_frames': self.total_frames,
            'fps': self.fps,
            'duration_seconds': self.duration,
            'width': self.width,
            'height': self.height,
        }

    def _read_frame_at(self, frame_index):
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self.cap.read()
        if ret:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return None

    @staticmethod
    def _histogram_diff(img1, img2):
        """基于直方图计算图片差异 (0~1)"""
        h1 = cv2.calcHist([cv2.cvtColor(img1, cv2.COLOR_RGB2BGR)], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        h2 = cv2.calcHist([cv2.cvtColor(img2, cv2.COLOR_RGB2BGR)], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        cv2.normalize(h1, h1)
        cv2.normalize(h2, h2)
        diff = cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL)
        return max(0.0, 1.0 - diff)

    @staticmethod
    def _phash(img, hash_size=8):
        """感知哈希算法 - 用于近似图像匹配"""
        resized = cv2.resize(img, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY) if len(resized.shape) == 3 else resized
        diff = gray[:, 1:] > gray[:, :-1]
        bits = diff.flatten()
        # 返回整数哈希值
        value = 0
        for bit in bits:
            value = (value << 1) | (1 if bit else 0)
        return value

    @staticmethod
    def _hamming_distance(h1, h2):
        """计算两个哈希值的汉明距离"""
        x = h1 ^ h2
        distance = 0
        while x:
            distance += 1
            x &= x - 1
        return distance

    @staticmethod
    def _frame_sharpness(img):
        """计算图像清晰度 (拉普拉斯方差)"""
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    @staticmethod
    def _is_slide_transition(img, threshold=30):
        """基于边缘/颜色突变检测是否是幻灯片切换场景（简单启发式）"""
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        # 检测画面是否大部分内容是"文本/白色背景"
        mean_val = gray.mean()
        std_val = gray.std()
        # 幻灯片一般是浅色背景 + 有内容
        return mean_val > 120 and std_val > 30

    def extract(self,
                sample_interval_sec=1.0,
                min_frame_sec=0.5,
                similarity_threshold=0.85,
                enable_dedup=True,
                enable_sharpness_filter=True,
                min_sharpness=50.0,
                verbose=False,
                progress_callback=None):
        """
        从视频中提取关键帧

        参数:
            sample_interval_sec: 基础采样间隔（秒）
            min_frame_sec: 两帧最小间隔
            similarity_threshold: 相似度阈值，低于这个阈值视为新场景
            enable_dedup: 是否启用去重
            enable_sharpness_filter: 是否过滤模糊帧
            min_sharpness: 最小清晰度
            verbose: 输出详细日志
            progress_callback: 进度回调函数 (percent, message)

        返回:
            list[dict]: 每个元素包含 image(RGB), frame_index, timestamp, score, sharpness
        """
        if self.cap is None:
            self.open()

        results = []
        last_frame = None
        last_hash = None
        frames_seen = 0
        step = max(1, int(self.fps * sample_interval_sec)) if self.fps > 0 else 30

        if progress_callback:
            progress_callback(0, f"开始分析 {self.total_frames} 帧...")

        for i in range(0, self.total_frames, step):
            frame = self._read_frame_at(i)
            if frame is None:
                continue

            timestamp = i / self.fps if self.fps > 0 else 0
            frames_seen += 1

            # 过滤纯黑/纯白/模糊帧
            if enable_sharpness_filter:
                sharp = self._frame_sharpness(frame)
                if sharp < min_sharpness:
                    if verbose:
                        print(f"[skip] 帧#{i} t={timestamp:.1f}s 清晰度过低 sharp={sharp:.1f}")
                    continue
            else:
                sharp = 0.0

            # 去重
            if enable_dedup and last_frame is not None:
                diff = self._histogram_diff(frame, last_frame)
                phash_val = self._phash(frame)
                hd = self._hamming_distance(last_hash, phash_val) if last_hash is not None else 0

                if diff < (1.0 - similarity_threshold) and hd < 8:
                    # 太相似，跳过；但我们保留较清晰的那一帧
                    if results and sharp > results[-1]['sharpness']:
                        results[-1] = {
                            'image': frame,
                            'frame_index': i,
                            'timestamp': timestamp,
                            'diff_score': diff,
                            'sharpness': sharp,
                            'is_slide': self._is_slide_transition(frame),
                        }
                    continue

            current = {
                'image': frame,
                'frame_index': i,
                'timestamp': timestamp,
                'diff_score': 1.0,
                'sharpness': sharp,
                'is_slide': self._is_slide_transition(frame),
            }
            results.append(current)
            last_frame = frame
            last_hash = self._phash(frame)

            if progress_callback and frames_seen % 10 == 0:
                progress = int(100.0 * i / max(self.total_frames, 1))
                progress_callback(progress, f"已提取 {len(results)} 帧...")

        if progress_callback:
            progress_callback(100, f"提取完成，共 {len(results)} 帧")

        return results

    def extract_with_slide_detection(self,
                                     sample_interval_sec=1.0,
                                     similarity_threshold=0.85,
                                     min_sharpness=50.0,
                                     progress_callback=None):
        """
        面向幻灯片内容的智能提取：
        - 过滤掉完全黑的过渡帧
        - 对幻灯片/演示类视频效果最好
        """
        frames = self.extract(
            sample_interval_sec=sample_interval_sec,
            similarity_threshold=similarity_threshold,
            min_sharpness=min_sharpness,
            progress_callback=progress_callback,
        )

        # 过滤掉非幻灯片风格的帧（如果有足够多帧）
        slide_frames = [f for f in frames if f['is_slide']]
        if len(slide_frames) < 3:
            return frames  # 视频可能不是幻灯片，退回全部帧
        return slide_frames
