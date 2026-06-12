"""
图像处理工具
"""

import cv2
import numpy as np


def load_image(path):
    """加载图像"""
    from PIL import Image
    img = Image.open(path)
    return np.array(img.convert('RGB'))


def load_video_frame(path):
    """从视频读取中间帧"""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    mid_frame = total_frames // 2
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        return None
    
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def resize_image(image, max_size=1024):
    """调整图像大小"""
    h, w = image.shape[:2]
    if max(h, w) <= max_size:
        return image
    
    scale = max_size / max(h, w)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)


def normalize_depth(depth):
    """归一化深度图"""
    min_val = depth.min()
    max_val = depth.max()
    return (depth - min_val) / (max_val - min_val + 1e-10)
