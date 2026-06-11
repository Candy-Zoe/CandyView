"""
常量定义模块
"""

# 支持的文件格式
SUPPORTED_FORMATS = [
    "3D Model Files (*.ply *.obj *.stl *.glb *.gltf)",
    "PLY Files (*.ply)",
    "OBJ Files (*.obj)",
    "STL Files (*.stl)",
    "GLTF Files (*.gltf *.glb)",
    "All Files (*.*)"
]

SUPPORTED_EXTENSIONS = ['.ply', '.obj', '.stl', '.glb', '.gltf']

# 默认颜色
DEFAULT_MODEL_COLOR = [0.7, 0.7, 0.7]

# 背景颜色
BACKGROUND_COLOR = [0.95, 0.95, 0.95]

# 轴大小
AXIS_SIZE = 1.0

# 旋转角度步进（度）
ROTATION_STEP = 15

# 缩放范围
SCALE_MIN = 0.1
SCALE_MAX = 5.0
SCALE_STEP = 0.1

# 平移范围
TRANSLATE_MIN = -10.0
TRANSLATE_MAX = 10.0
TRANSLATE_STEP = 0.1

# 旋转范围
ROTATE_MIN = -180
ROTATE_MAX = 180

# 窗口默认大小
DEFAULT_WINDOW_WIDTH = 1400
DEFAULT_WINDOW_HEIGHT = 900

# 侧边栏宽度
SIDEBAR_WIDTH = 320
