"""
视频处理器 - 从视频中检测移动物体并输出处理结果
支持：
1. 生成带检测框的新视频
2. 生成带检测框的截图
"""

import os
import cv2
import numpy as np
from PIL import Image

from core.motion_detector import MotionDetector, merge_overlapping_boxes


class VideoProcessor:
    """视频处理引擎：检测 + 输出带检测框的视频"""

    def __init__(self, video_path, algorithm='mog2', min_area=500, max_area=50000,
                 blur_kernel=5, threshold_value=25, morphology_kernel=5,
                 box_color=(0, 255, 0), box_thickness=2):
        self.video_path = video_path
        self.cap = None
        self.fps = 0
        self.width = 0
        self.height = 0
        self.total_frames = 0
        self.detector = MotionDetector(
            algorithm=algorithm,
            min_area=min_area,
            max_area=max_area,
            blur_kernel=blur_kernel,
            threshold_value=threshold_value,
            morphology_kernel=morphology_kernel,
        )
        self.box_color = box_color
        self.box_thickness = box_thickness

    def open(self):
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            raise RuntimeError("无法打开视频: " + str(self.video_path))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return True

    def close(self):
        if self.cap is not None:
            self.cap.release()
        self.detector.reset()

    def get_info(self):
        return {
            'path': self.video_path,
            'fps': self.fps,
            'width': self.width,
            'height': self.height,
            'total_frames': self.total_frames,
            'duration_sec': self.total_frames / max(self.fps, 0.1),
        }

    def _create_video_writer(self, output_path):
        """创建视频写入器，尝试多种编码格式"""
        fourcc_list = [
            cv2.VideoWriter_fourcc(*'mp4v'),
            cv2.VideoWriter_fourcc(*'XVID'),
            cv2.VideoWriter_fourcc(*'MJPG'),
            cv2.VideoWriter_fourcc(*'avc1'),
        ]
        output_fps = max(self.fps, 1.0)
        for fourcc in fourcc_list:
            writer = cv2.VideoWriter(output_path, fourcc, output_fps,
                                      (self.width, self.height))
            if writer.isOpened():
                return writer
            writer.release()
        raise RuntimeError("无法创建输出视频文件，所有编码器都失败了")

    def process_video(self, output_path, progress_callback=None,
                      skip_frames=1, merge_boxes=True, merge_threshold=0.3,
                      draw_info=True):
        """处理整个视频，输出带检测框的新视频"""
        if self.cap is None:
            self.open()

        if not os.path.exists(os.path.dirname(output_path)):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

        out = self._create_video_writer(output_path)

        processed = 0
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        for frame_idx in range(0, self.total_frames, skip_frames):
            ret, frame = self.cap.read()
            if not ret:
                break

            boxes, _ = self.detector.detect(frame)
            if merge_boxes:
                boxes = merge_overlapping_boxes(boxes, merge_threshold)

            result = MotionDetector.draw_boxes(
                frame, boxes, color=self.box_color,
                thickness=self.box_thickness)

            if draw_info:
                timestamp = frame_idx / max(self.fps, 0.1)
                cv2.putText(result, "t=" + str(round(timestamp, 1)) + "s",
                            (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (255, 255, 255), 2)
                if len(boxes) > 0:
                    cv2.putText(result, "objects: " + str(len(boxes)),
                                (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                                self.box_color, 2)

            out.write(result)
            processed += 1

            if progress_callback and processed % 15 == 0:
                percent = int(100 * processed / max(self.total_frames, 1))
                progress_callback(
                    percent,
                    "处理第 " + str(processed) + "/" + str(self.total_frames) +
                    " 帧, 检测 " + str(len(boxes)) + " 个物体")

        out.release()
        if progress_callback:
            progress_callback(100, "完成！共处理 " + str(processed) + " 帧")
        return output_path, processed

    def extract_snapshots(self, output_dir, min_interval_sec=1.0,
                           max_snapshots=50, progress_callback=None,
                           merge_boxes=True, merge_threshold=0.3):
        """提取包含移动物体的关键帧截图"""
        if self.cap is None:
            self.open()

        os.makedirs(output_dir, exist_ok=True)
        saved_snapshots = []
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        last_saved_frame = -1

        min_frame_gap = int(self.fps * min_interval_sec)
        if min_frame_gap < 1:
            min_frame_gap = 1

        processed = 0

        for frame_idx in range(0, self.total_frames):
            ret, frame = self.cap.read()
            if not ret:
                break
            processed += 1

            boxes, _ = self.detector.detect(frame)
            if merge_boxes:
                boxes = merge_overlapping_boxes(boxes, merge_threshold)

            if len(boxes) > 0 and (frame_idx - last_saved_frame) >= min_frame_gap:
                timestamp = frame_idx / max(self.fps, 0.1)
                result = MotionDetector.draw_boxes(
                    frame, boxes, color=self.box_color,
                    thickness=self.box_thickness)

                filename = ("snapshot_" + str(len(saved_snapshots)).zfill(4) +
                            "_t" + str(round(timestamp, 1)) + "s.png")
                output_path = os.path.join(output_dir, filename)
                cv2.imwrite(output_path, result)

                saved_snapshots.append({
                    'file': output_path,
                    'timestamp': timestamp,
                    'frame_index': frame_idx,
                    'object_count': len(boxes),
                    'boxes': boxes,
                })
                last_saved_frame = frame_idx
                if len(saved_snapshots) >= max_snapshots:
                    break

            if progress_callback and processed % 30 == 0:
                progress_callback(
                    int(100 * processed / max(self.total_frames, 1)),
                    "分析中... 已检测 " + str(len(saved_snapshots)) + " 张")

        if progress_callback:
            progress_callback(100, "完成！共保存 " + str(len(saved_snapshots)) + " 张截图")
        return saved_snapshots

    def process_and_extract(self, video_output_path, snapshot_output_dir,
                          progress_callback=None, skip_frames=1,
                          snapshot_interval_sec=2.0, max_snapshots=50,
                          merge_boxes=True, merge_threshold=0.3):
        """一次性处理：同时生成带检测框的视频+截图"""
        if self.cap is None:
            self.open()

        os.makedirs(snapshot_output_dir, exist_ok=True)
        video_out = self._create_video_writer(video_output_path)

        saved_snapshots = []
        last_saved_frame = -1
        min_frame_gap = int(self.fps * snapshot_interval_sec)
        if min_frame_gap < 1:
            min_frame_gap = 1

        processed = 0

        for frame_idx in range(0, self.total_frames, skip_frames):
            ret, frame = self.cap.read()
            if not ret:
                break

            boxes, _ = self.detector.detect(frame)
            if merge_boxes:
                boxes = merge_overlapping_boxes(boxes, merge_threshold)

            result = MotionDetector.draw_boxes(
                frame, boxes, color=self.box_color,
                thickness=self.box_thickness)

            timestamp = frame_idx / max(self.fps, 0.1)
            cv2.putText(result, "t=" + str(round(timestamp, 1)) + "s",
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (255, 255, 255), 2)
            if len(boxes) > 0:
                cv2.putText(result, "objects: " + str(len(boxes)),
                            (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            self.box_color, 2)

            video_out.write(result)
            processed += 1

            if len(boxes) > 0 and (frame_idx - last_saved_frame) >= min_frame_gap:
                snap_file = os.path.join(
                    snapshot_output_dir,
                    "snapshot_" + str(len(saved_snapshots)).zfill(4) +
                    "_t" + str(round(timestamp, 1)) + "s.png")
                cv2.imwrite(snap_file, result)
                saved_snapshots.append({
                    'file': snap_file,
                    'timestamp': timestamp,
                    'frame_index': frame_idx,
                    'object_count': len(boxes),
                    'boxes': boxes,
                })
                last_saved_frame = frame_idx
                if len(saved_snapshots) >= max_snapshots:
                    break

            if progress_callback and processed % 20 == 0:
                progress_callback(
                    int(100 * processed / max(self.total_frames, 1)),
                    "处理 " + str(processed) + " 帧, 已保存 " +
                    str(len(saved_snapshots)) + " 张截图")

        video_out.release()

        if progress_callback:
            progress_callback(100, "完成！共处理 " + str(processed) + " 帧, 保存 " +
                              str(len(saved_snapshots)) + " 张截图")

        return {
            'video': video_output_path,
            'snapshots': saved_snapshots,
        }
