"""
PyOpenGL 3D查看器核心模块
高性能版本 - 使用VBO加速渲染
"""

import numpy as np
import sys
import threading
import time

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

from core.base_loader import ModelData


class Viewer3D:
    """基于PyOpenGL的高性能3D查看器"""

    def __init__(self):
        self.model_data = None
        self.vertices = None
        self.triangles = None
        self.colors = None
        self.normals = None
        self.is_running = False

        # 变换参数
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0
        self.scale_factor = 1.0
        self.translate_x = 0.0
        self.translate_y = 0.0
        self.translate_z = 0.0

        # 鼠标状态
        self._mouse_down = False
        self._last_mouse_x = 0
        self._last_mouse_y = 0
        self._mouse_button = 0  # 0=左键, 1=右键

        # 显示状态
        self._wireframe = False
        self._show_axes = True
        self._show_vertices = False

        # VBO IDs
        self._vbo_vertices = None
        self._vbo_colors = None
        self._vbo_normals = None
        self._vbo_indices = None
        self._vbo_initialized = False

        # 窗口
        self._window = None
        self._initialized = False

        # 测量数据
        self._measure_points = []
        self._measure_enabled = False

        # 帧率
        self._frame_count = 0
        self._fps_time = time.time()
        self._fps = 0

    def load_model(self, model_data: ModelData):
        """加载模型数据"""
        self.model_data = model_data
        if model_data and model_data.vertices:
            vertices = np.array(model_data.vertices, dtype=np.float32)

            # 归一化到 [-1, 1]
            min_v = vertices.min(axis=0)
            max_v = vertices.max(axis=0)
            center = (min_v + max_v) / 2
            size = np.max(max_v - min_v)
            scale = 2.0 / size if size > 0 else 1.0
            vertices = (vertices - center) * scale

            self.vertices = vertices

            if model_data.triangles:
                triangles = np.array(model_data.triangles, dtype=np.int32)
                self.triangles = triangles.flatten()
            else:
                self.triangles = None

            if model_data.colors:
                colors = np.array(model_data.colors, dtype=np.float32)
                # 如果颜色值大于1，归一化
                if colors.max() > 1.5:
                    colors = colors / 255.0
                self.colors = colors
            else:
                self.colors = None

            if model_data.normals:
                self.normals = np.array(model_data.normals, dtype=np.float32)
            else:
                self.normals = None

            # 初始化VBO
            if self._initialized:
                self._init_vbo()

    def create_window(self, width=1024, height=768):
        """创建OpenGL窗口"""
        try:
            glutInit(sys.argv)
        except:
            pass

        glutInitDisplayMode(GLUT_RGB | GLUT_DOUBLE | GLUT_DEPTH)
        glutInitWindowSize(width, height)
        glutInitWindowPosition(100, 100)
        self._window = glutCreateWindow(b"3D Model Viewer")

        glutDisplayFunc(self._on_display)
        glutReshapeFunc(self._on_reshape)
        glutMouseFunc(self._on_mouse)
        glutMotionFunc(self._on_motion)
        glutKeyboardFunc(self._on_keyboard)
        glutSpecialFunc(self._on_special)
        glutIdleFunc(self._on_idle)

        self._init_gl()
        self._initialized = True

    def _init_gl(self):
        """初始化OpenGL"""
        glClearColor(0.12, 0.12, 0.15, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glEnable(GL_NORMALIZE)
        glShadeModel(GL_SMOOTH)
        glEnable(GL_CULL_FACE)

        glLightfv(GL_LIGHT0, GL_POSITION, [2.0, 2.0, 2.0, 0.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.4, 0.4, 0.4, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.9, 0.9, 0.9, 1.0])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [0.4, 0.4, 0.4, 1.0])

        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    def _init_vbo(self):
        """初始化顶点缓冲对象"""
        if self._vbo_initialized:
            self._delete_vbo()

        if self.vertices is None:
            return

        # 创建顶点VBO
        self._vbo_vertices = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo_vertices)
        glBufferData(GL_ARRAY_BUFFER, self.vertices.nbytes, self.vertices, GL_STATIC_DRAW)

        # 创建颜色VBO
        if self.colors is not None:
            self._vbo_colors = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo_colors)
            glBufferData(GL_ARRAY_BUFFER, self.colors.nbytes, self.colors, GL_STATIC_DRAW)

        # 创建法线VBO
        if self.normals is not None:
            self._vbo_normals = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo_normals)
            glBufferData(GL_ARRAY_BUFFER, self.normals.nbytes, self.normals, GL_STATIC_DRAW)

        # 创建索引VBO
        if self.triangles is not None:
            self._vbo_indices = glGenBuffers(1)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._vbo_indices)
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.triangles.nbytes, self.triangles, GL_STATIC_DRAW)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

        self._vbo_initialized = True
        print(f"[Viewer] VBO initialized: {len(self.vertices)} vertices, {len(self.triangles)//3} triangles")

    def _delete_vbo(self):
        """删除VBO"""
        if self._vbo_vertices:
            glDeleteBuffers(1, [self._vbo_vertices])
            self._vbo_vertices = None
        if self._vbo_colors:
            glDeleteBuffers(1, [self._vbo_colors])
            self._vbo_colors = None
        if self._vbo_normals:
            glDeleteBuffers(1, [self._vbo_normals])
            self._vbo_normals = None
        if self._vbo_indices:
            glDeleteBuffers(1, [self._vbo_indices])
            self._vbo_indices = None
        self._vbo_initialized = False

    def _on_idle(self):
        """空闲回调 - 持续渲染"""
        glutPostRedisplay()

    def _on_display(self):
        """渲染回调"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        # 视角
        gluLookAt(0, 0, 3, 0, 0, 0, 0, 1, 0)

        # 变换
        glTranslatef(self.translate_x, self.translate_y, self.translate_z)
        glScalef(self.scale_factor, self.scale_factor, self.scale_factor)
        glRotatef(self.rot_x, 1, 0, 0)
        glRotatef(self.rot_y, 0, 1, 0)
        glRotatef(self.rot_z, 0, 0, 1)

        # 绘制坐标轴
        self._draw_axes()

        # 绘制测量线
        self._draw_measurements()

        # 绘制模型
        self._draw_model()

        # 绘制FPS
        self._draw_fps()

        glutSwapBuffers()

    def _draw_fps(self):
        """绘制帧率"""
        self._frame_count += 1
        current_time = time.time()
        if current_time - self._fps_time >= 1.0:
            self._fps = self._frame_count
            self._frame_count = 0
            self._fps_time = current_time

        glDisable(GL_LIGHTING)
        glColor3f(0.8, 0.8, 0.8)
        glRasterPos2f(-0.95, 0.9)
        fps_text = f"FPS: {self._fps}"
        for c in fps_text:
            glutBitmapCharacter(GLUT_BITMAP_8_BY_13, ord(c))
        glEnable(GL_LIGHTING)

    def _on_reshape(self, width, height):
        """窗口大小改变"""
        if height == 0:
            height = 1
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, width / height, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)

    def _on_mouse(self, button, state, x, y):
        """鼠标事件"""
        if button == GLUT_LEFT_BUTTON:
            self._mouse_down = (state == GLUT_DOWN)
            self._mouse_button = 0
            self._last_mouse_x = x
            self._last_mouse_y = y

            # 测量模式下添加点
            if self._measure_enabled and state == GLUT_DOWN:
                self._add_measure_point(x, y)

        elif button == GLUT_RIGHT_BUTTON:
            self._mouse_down = (state == GLUT_DOWN)
            self._mouse_button = 1
            self._last_mouse_x = x
            self._last_mouse_y = y

        elif button == 3:  # 滚轮上
            self.scale_factor = min(self.scale_factor * 1.05, 20.0)
        elif button == 4:  # 滚轮下
            self.scale_factor = max(self.scale_factor / 1.05, 0.01)

    def _on_motion(self, x, y):
        """鼠标拖拽"""
        if not self._mouse_down:
            return

        dx = x - self._last_mouse_x
        dy = y - self._last_mouse_y

        if self._mouse_button == 0:
            # 左键：旋转
            self.rot_y += dx * 0.5
            self.rot_x += dy * 0.5
        elif self._mouse_button == 1:
            # 右键：平移
            self.translate_x += dx * 0.005 * self.scale_factor
            self.translate_y -= dy * 0.005 * self.scale_factor

        self._last_mouse_x = x
        self._last_mouse_y = y

    def _on_keyboard(self, key, x, y):
        """键盘事件"""
        key = key.decode() if isinstance(key, bytes) else key

        if key in ('w', 'W'):
            self._wireframe = not self._wireframe
            if self._wireframe:
                glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            else:
                glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

        elif key in ('a', 'A'):
            self._show_axes = not self._show_axes

        elif key in ('v', 'V'):
            self._show_vertices = not self._show_vertices

        elif key in ('m', 'M'):
            self._measure_enabled = not self._measure_enabled
            if not self._measure_enabled:
                self._measure_points = []

        elif key in ('r', 'R'):
            self.rot_x = self.rot_y = self.rot_z = 0
            self.scale_factor = 1.0
            self.translate_x = self.translate_y = self.translate_z = 0

        elif key == 'c':
            self._measure_points = []

        elif key == 's':
            self._save_screenshot()

        elif key == chr(27):
            self.stop()

    def _on_special(self, key, x, y):
        """特殊键"""
        if key == GLUT_KEY_UP:
            self.rot_x -= 3
        elif key == GLUT_KEY_DOWN:
            self.rot_x += 3
        elif key == GLUT_KEY_LEFT:
            self.rot_y -= 3
        elif key == GLUT_KEY_RIGHT:
            self.rot_y += 3

    def _add_measure_point(self, x, y):
        """添加测量点"""
        if len(self._measure_points) >= 2:
            self._measure_points = []

        # 屏幕坐标转世界坐标
        model_view = glGetDoublev(GL_MODELVIEW_MATRIX)
        projection = glGetDoublev(GL_PROJECTION_MATRIX)
        viewport = glGetIntegerv(GL_VIEWPORT)

        win_y = viewport[3] - y
        world_coord = gluUnProject(x, win_y, 0.5, model_view, projection, viewport)

        self._measure_points.append(list(world_coord[:3]))

        if len(self._measure_points) == 2:
            p1 = np.array(self._measure_points[0])
            p2 = np.array(self._measure_points[1])
            distance = np.linalg.norm(p2 - p1)
            print(f"[Measure] Distance: {distance:.3f} units")

    def _draw_measurements(self):
        """绘制测量线"""
        if len(self._measure_points) < 2:
            return

        glDisable(GL_LIGHTING)
        glLineWidth(3.0)
        glColor3f(1.0, 0.5, 0.0)

        glBegin(GL_LINES)
        glVertex3fv(self._measure_points[0])
        glVertex3fv(self._measure_points[1])
        glEnd()

        # 绘制端点
        glPointSize(8.0)
        glBegin(GL_POINTS)
        for p in self._measure_points:
            glVertex3fv(p)
        glEnd()

        # 绘制距离文字
        mid_point = [(self._measure_points[0][i] + self._measure_points[1][i]) / 2 for i in range(3)]
        p1 = np.array(self._measure_points[0])
        p2 = np.array(self._measure_points[1])
        distance = np.linalg.norm(p2 - p1)

        glRasterPos3fv(mid_point)
        dist_text = f"{distance:.3f}"
        for c in dist_text:
            glutBitmapCharacter(GLUT_BITMAP_9_BY_15, ord(c))

        glEnable(GL_LIGHTING)
        glLineWidth(1.0)
        glPointSize(1.0)

    def _draw_axes(self):
        """绘制坐标轴"""
        if not self._show_axes:
            return

        glLineWidth(2.0)
        glDisable(GL_LIGHTING)

        glColor3f(1.0, 0.3, 0.3)
        glBegin(GL_LINES)
        glVertex3f(-2, 0, 0)
        glVertex3f(2, 0, 0)
        glEnd()

        glColor3f(0.3, 1.0, 0.3)
        glBegin(GL_LINES)
        glVertex3f(0, -2, 0)
        glVertex3f(0, 2, 0)
        glEnd()

        glColor3f(0.3, 0.3, 1.0)
        glBegin(GL_LINES)
        glVertex3f(0, 0, -2)
        glVertex3f(0, 0, 2)
        glEnd()

        glEnable(GL_LIGHTING)
        glLineWidth(1.0)

    def _draw_model(self):
        """绘制模型 - 使用VBO加速"""
        if self.vertices is None or len(self.vertices) == 0:
            return

        glEnableClientState(GL_VERTEX_ARRAY)

        if self._vbo_initialized and self.triangles is not None:
            # 使用VBO绘制
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo_vertices)
            glVertexPointer(3, GL_FLOAT, 0, None)

            if self._vbo_colors:
                glEnableClientState(GL_COLOR_ARRAY)
                glBindBuffer(GL_ARRAY_BUFFER, self._vbo_colors)
                glColorPointer(3, GL_FLOAT, 0, None)
            else:
                glColor3f(0.75, 0.75, 0.8)

            if self._vbo_normals:
                glEnableClientState(GL_NORMAL_ARRAY)
                glBindBuffer(GL_ARRAY_BUFFER, self._vbo_normals)
                glNormalPointer(GL_FLOAT, 0, None)

            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._vbo_indices)
            glDrawElements(GL_TRIANGLES, len(self.triangles), GL_UNSIGNED_INT, None)

            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

        else:
            # 回退到即时模式
            glVertexPointer(3, GL_FLOAT, 0, self.vertices)

            if self.colors is not None:
                glEnableClientState(GL_COLOR_ARRAY)
                glColorPointer(3, GL_FLOAT, 0, self.colors)
            else:
                glColor3f(0.75, 0.75, 0.8)

            if self.triangles is not None:
                glDrawElements(GL_TRIANGLES, len(self.triangles), GL_UNSIGNED_INT, self.triangles)
            else:
                glDrawArrays(GL_POINTS, 0, len(self.vertices))

        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_COLOR_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)

    def _save_screenshot(self):
        """保存截图"""
        width, height = glutGet(GLUT_WINDOW_WIDTH), glutGet(GLUT_WINDOW_HEIGHT)
        pixels = glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE)
        img = np.frombuffer(pixels, dtype=np.uint8).reshape(height, width, 3)
        img = np.flipud(img)

        from PIL import Image
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        Image.fromarray(img).save(filename)
        print(f"[Viewer] Screenshot saved: {filename}")

    def run(self):
        """运行查看器"""
        self.is_running = True
        try:
            glutMainLoop()
        except Exception as e:
            print(f"Viewer error: {e}")
            self.is_running = False

    def stop(self):
        """停止查看器"""
        self.is_running = False
        if self._window:
            try:
                glutDestroyWindow(self._window)
            except:
                pass
            self._window = None
        self._delete_vbo()
