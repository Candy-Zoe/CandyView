"""
PyOpenGL 3D查看器核心模块
简化版 - 专注于稳定性
"""

import numpy as np
import sys

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

from core.base_loader import ModelData


class Viewer3D:
    """基于PyOpenGL的3D查看器"""

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
        self._window = None
        self._initialized = False

    def load_model(self, model_data: ModelData):
        """加载模型数据"""
        self.model_data = model_data
        if model_data and model_data.vertices:
            vertices = np.array(model_data.vertices, dtype=np.float32)

            # 归一化到 [-1, 1]
            min_v = vertices.min(axis=0)
            max_v = vertices.max(axis=0)
            center = (min_v + max_v) / 2
            scale = 2.0 / np.max(max_v - min_v) if np.max(max_v - min_v) > 0 else 1.0
            vertices = (vertices - center) * scale

            self.vertices = vertices

            if model_data.triangles:
                self.triangles = np.array(model_data.triangles, dtype=np.int32)
            else:
                self.triangles = None

            if model_data.colors:
                self.colors = np.array(model_data.colors, dtype=np.float32)
            else:
                self.colors = None

            if model_data.normals:
                self.normals = np.array(model_data.normals, dtype=np.float32)
            else:
                self.normals = None

    def create_window(self, width=800, height=600):
        """创建OpenGL窗口"""
        try:
            glutInit()
        except:
            pass
        glutInitDisplayMode(GLUT_RGB | GLUT_DOUBLE | GLUT_DEPTH)
        glutInitWindowSize(width, height)
        glutInitWindowPosition(100, 100)
        self._window = glutCreateWindow(b"3D Model Viewer")

        # 设置回调
        glutDisplayFunc(self._on_display)
        glutReshapeFunc(self._on_reshape)
        glutMouseFunc(self._on_mouse)
        glutMotionFunc(self._on_motion)
        glutKeyboardFunc(self._on_keyboard)
        glutSpecialFunc(self._on_special)

        # 初始化OpenGL
        self._init_gl()
        self._initialized = True

    def _init_gl(self):
        """初始化OpenGL"""
        glClearColor(0.12, 0.12, 0.15, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glShadeModel(GL_SMOOTH)

        # 光照
        glLightfv(GL_LIGHT0, GL_POSITION, [1.0, 1.0, 1.0, 0.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.4, 0.4, 0.4, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [0.3, 0.3, 0.3, 1.0])

        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

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

        # 绘制模型
        self._draw_model()

        glutSwapBuffers()

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
            self._last_mouse_x = x
            self._last_mouse_y = y
        elif button == 3:  # 滚轮上
            self.scale_factor = min(self.scale_factor * 1.1, 10.0)
            glutPostRedisplay()
        elif button == 4:  # 滚轮下
            self.scale_factor = max(self.scale_factor / 1.1, 0.01)
            glutPostRedisplay()

    def _on_motion(self, x, y):
        """鼠标拖拽"""
        if not self._mouse_down:
            return
        dx = x - self._last_mouse_x
        dy = y - self._last_mouse_y
        self.rot_y += dx * 0.5
        self.rot_x += dy * 0.5
        self._last_mouse_x = x
        self._last_mouse_y = y
        glutPostRedisplay()

    def _on_keyboard(self, key, x, y):
        """键盘事件"""
        key = key.decode() if isinstance(key, bytes) else key
        if key in ('w', 'W'):
            self._wireframe = not getattr(self, '_wireframe', False)
            if self._wireframe:
                glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            else:
                glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            glutPostRedisplay()
        elif key in ('a', 'A'):
            self._show_axes = not getattr(self, '_show_axes', True)
            glutPostRedisplay()
        elif key in ('r', 'R'):
            self.rot_x = self.rot_y = self.rot_z = 0
            self.scale_factor = 1.0
            self.translate_x = self.translate_y = self.translate_z = 0
            glutPostRedisplay()
        elif key == chr(27):  # ESC
            self.stop()

    def _on_special(self, key, x, y):
        """特殊键"""
        if key == GLUT_KEY_UP:
            self.rot_x -= 5
        elif key == GLUT_KEY_DOWN:
            self.rot_x += 5
        elif key == GLUT_KEY_LEFT:
            self.rot_y -= 5
        elif key == GLUT_KEY_RIGHT:
            self.rot_y += 5
        glutPostRedisplay()

    def _draw_axes(self):
        """绘制坐标轴"""
        if getattr(self, '_show_axes', True):
            glLineWidth(2.0)
            glDisable(GL_LIGHTING)
            # X轴红色
            glColor3f(1.0, 0.3, 0.3)
            glBegin(GL_LINES)
            glVertex3f(-2, 0, 0)
            glVertex3f(2, 0, 0)
            glEnd()
            # Y轴绿色
            glColor3f(0.3, 1.0, 0.3)
            glBegin(GL_LINES)
            glVertex3f(0, -2, 0)
            glVertex3f(0, 2, 0)
            glEnd()
            # Z轴蓝色
            glColor3f(0.3, 0.3, 1.0)
            glBegin(GL_LINES)
            glVertex3f(0, 0, -2)
            glVertex3f(0, 0, 2)
            glEnd()
            glEnable(GL_LIGHTING)
            glLineWidth(1.0)

    def _draw_model(self):
        """绘制模型"""
        if self.vertices is None or len(self.vertices) == 0:
            return

        if self.triangles is not None and len(self.triangles) > 0:
            # 有三角形
            if self.colors is not None and len(self.colors) == len(self.vertices):
                # 带顶点颜色
                glBegin(GL_TRIANGLES)
                for tri in self.triangles:
                    for idx in tri:
                        if idx < len(self.colors):
                            glColor3fv(self.colors[idx])
                        if idx < len(self.vertices):
                            glVertex3fv(self.vertices[idx])
                glEnd()
            else:
                # 无颜色
                glColor3f(0.75, 0.75, 0.8)
                glBegin(GL_TRIANGLES)
                for tri in self.triangles:
                    for idx in tri:
                        if idx < len(self.vertices):
                            glVertex3fv(self.vertices[idx])
                glEnd()
        else:
            # 只绘制点
            glPointSize(2.0)
            if self.colors is not None and len(self.colors) == len(self.vertices):
                glBegin(GL_POINTS)
                for i in range(len(self.vertices)):
                    glColor3fv(self.colors[i])
                    glVertex3fv(self.vertices[i])
                glEnd()
            else:
                glColor3f(0.75, 0.75, 0.8)
                glBegin(GL_POINTS)
                for v in self.vertices:
                    glVertex3fv(v)
                glEnd()
            glPointSize(1.0)

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
