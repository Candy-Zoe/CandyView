"""
PLY模型加载器
支持所有类型的PLY格式（ASCII和二进制）
"""

import struct
import os
import re
from typing import Optional, List
from core.base_loader import BaseModelLoader, ModelData


class PLYLoader(BaseModelLoader):
    """PLY格式模型加载器 - 通用版"""

    def supports_format(self, extension: str) -> bool:
        return extension.lower() == '.ply'

    def get_supported_formats(self) -> List[str]:
        return ['.ply']

    def load(self, file_path: str) -> Optional[ModelData]:
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, 'rb') as f:
                header = self._read_header(f)
                if header is None:
                    return None

                model = ModelData()
                model.format = "PLY"
                model.name = os.path.basename(file_path)

                if header['is_binary']:
                    self._parse_binary(f, model, header)
                else:
                    self._parse_ascii(f, model, header)

                return model

        except Exception as e:
            print(f"PLY load error: {e}")
            return None

    def _read_header(self, file) -> dict:
        """读取并解析PLY头部"""
        header = {
            'is_binary': False,
            'vertex_count': 0,
            'face_count': 0,
            'properties': [],  # 每个属性的名称和类型
            'format': 'ascii'
        }

        while True:
            line = file.readline()
            if not line:
                return None

            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='ignore').strip()
            else:
                line = line.strip()

            if line.startswith('format'):
                parts = line.split()
                if len(parts) >= 3:
                    header['format'] = parts[1]
                    header['is_binary'] = 'binary' in parts[1].lower()
            elif line.startswith('element vertex'):
                parts = line.split()
                if len(parts) >= 3:
                    header['vertex_count'] = int(parts[2])
            elif line.startswith('element face'):
                parts = line.split()
                if len(parts) >= 3:
                    header['face_count'] = int(parts[2])
            elif line.startswith('property'):
                header['properties'].append(line)
            elif line == 'end_header':
                break

        return header

    def _parse_ascii(self, file, model, header):
        """解析ASCII格式PLY"""
        vertices = []
        colors = []
        normals = []
        texcoords = []
        triangles = []

        # 解析每个顶点的属性位置
        prop_map = {}
        for i, prop in enumerate(header['properties']):
            prop = prop.lower()
            parts = prop.split()
            if len(parts) >= 3:
                prop_name = parts[2]
                if 'x' == prop_name or 'y' == prop_name or 'z' == prop_name:
                    prop_map['vertex_xyz'] = i
                elif 'nx' == prop_name or 'ny' == prop_name or 'nz' == prop_name:
                    prop_map.setdefault('normals', []).append(i)
                elif prop_name in ('red', 'green', 'blue', 'alpha'):
                    prop_map.setdefault('colors', []).append(i)
                elif prop_name in ('s', 't', 'u', 'v'):
                    prop_map.setdefault('texcoords', []).append(i)

        vertex_xyz_idx = prop_map.get('vertex_xyz', -1)
        color_idx = prop_map.get('colors', [])
        normal_idx = prop_map.get('normals', [])

        # 读取顶点
        for _ in range(header['vertex_count']):
            line = file.readline()
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='ignore')
            parts = line.strip().split()

            if vertex_xyz_idx >= 0 and vertex_xyz_idx + 2 < len(parts):
                x = float(parts[vertex_xyz_idx])
                y = float(parts[vertex_xyz_idx + 1])
                z = float(parts[vertex_xyz_idx + 2])
                vertices.append([x, y, z])

                # 颜色
                if color_idx and len(color_idx) >= 3:
                    try:
                        r = float(parts[color_idx[0]]) / 255.0 if float(parts[color_idx[0]]) > 1 else float(parts[color_idx[0]])
                        g = float(parts[color_idx[1]]) / 255.0 if float(parts[color_idx[1]]) > 1 else float(parts[color_idx[1]])
                        b = float(parts[color_idx[2]]) / 255.0 if float(parts[color_idx[2]]) > 1 else float(parts[color_idx[2]])
                        colors.append([r, g, b])
                    except:
                        pass

        # 读取面
        for _ in range(header['face_count']):
            line = file.readline()
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='ignore')
            parts = line.strip().split()

            if parts:
                n = int(parts[0])
                if n >= 3 and len(parts) >= n + 1:
                    face = [int(parts[i + 1]) for i in range(n)]
                    if n == 3:
                        triangles.append(face)
                    else:
                        # 三角化
                        for i in range(1, n - 1):
                            triangles.append([face[0], face[i], face[i + 1]])

        model.vertices = vertices
        model.triangles = triangles
        model.colors = colors
        model.normals = normals if normals else self._compute_normals(vertices, triangles)
        model.texcoords = texcoords

    def _parse_binary(self, file, model, header):
        """解析二进制格式PLY"""
        vertices = []
        colors = []
        normals = []
        texcoords = []
        triangles = []

        # 计算每个顶点的字节大小
        vertex_size = 0
        prop_types = {}

        # 简化处理：假设标准属性顺序
        for prop in header['properties']:
            parts = prop.lower().split()
            if len(parts) >= 3:
                ptype = parts[1]
                pname = parts[2]
                size = self._get_type_size(ptype)
                if size > 0:
                    prop_types[pname] = (ptype, size)
                    vertex_size += size

        # 读取顶点
        for _ in range(header['vertex_count']):
            data = file.read(vertex_size)
            offset = 0

            x = y = z = 0.0
            has_xyz = False

            for pname, (ptype, size) in prop_types.items():
                value = self._read_value(data, offset, ptype)
                offset += size

                if pname == 'x':
                    x = value
                    has_xyz = True
                elif pname == 'y':
                    y = value
                elif pname == 'z':
                    z = value
                elif pname in ('nx', 'ny', 'nz'):
                    normals.append([value if pname == 'nx' else 0,
                                   value if pname == 'ny' else 0,
                                   value if pname == 'nz' else 0])
                elif pname in ('red', 'green', 'blue'):
                    # 延迟处理颜色
                    pass

            if has_xyz:
                vertices.append([x, y, z])

                # 尝试提取颜色
                r = g = b = 0.7
                if 'red' in prop_types and 'green' in prop_types and 'blue' in prop_types:
                    r_off, r_type = prop_types['red'][1], prop_types['red'][0]
                    g_off, g_type = prop_types['green'][1], prop_types['green'][0]
                    b_off, b_type = prop_types['blue'][1], prop_types['blue'][0]
                    r = self._read_value(data, r_off, r_type)
                    g = self._read_value(data, g_off, g_type)
                    b = self._read_value(data, b_off, b_type)
                    if r > 1 or g > 1 or b > 1:
                        r, g, b = r / 255.0, g / 255.0, b / 255.0
                colors.append([r, g, b])

        # 读取面
        for _ in range(header['face_count']):
            n_byte = file.read(1)
            if not n_byte:
                break
            n = struct.unpack('B', n_byte)[0]

            if header['format'] == 'binary_big_endian':
                face_data = file.read(n * 4)
                fmt = '>' + 'I' * n
                indices = struct.unpack(fmt, face_data)
            else:
                face_data = file.read(n * 4)
                fmt = '<' + 'I' * n
                indices = struct.unpack(fmt, face_data)

            if n >= 3:
                indices = list(indices)
                if n == 3:
                    triangles.append(indices)
                else:
                    for i in range(1, n - 1):
                        triangles.append([indices[0], indices[i], indices[i + 1]])

        model.vertices = vertices
        model.triangles = triangles
        model.colors = colors
        model.normals = normals if normals else self._compute_normals(vertices, triangles)
        model.texcoords = texcoords

    def _get_type_size(self, ptype):
        """获取PLY数据类型的字节大小"""
        type_sizes = {
            'char': 1, 'int8': 1,
            'uchar': 1, 'uint8': 1,
            'short': 2, 'int16': 2,
            'ushort': 2, 'uint16': 2,
            'int': 4, 'int32': 4,
            'uint': 4, 'uint32': 4,
            'float': 4, 'float32': 4,
            'double': 8, 'float64': 8
        }
        return type_sizes.get(ptype.lower(), 0)

    def _read_value(self, data, offset, ptype):
        """从二进制数据中读取值"""
        size = self._get_type_size(ptype)
        if size == 0 or offset + size > len(data):
            return 0.0

        chunk = data[offset:offset + size]
        ptype = ptype.lower()

        if ptype in ('char', 'int8', 'uchar', 'uint8'):
            return struct.unpack('B', chunk)[0]
        elif ptype in ('short', 'int16'):
            return struct.unpack('<h', chunk)[0]
        elif ptype in ('ushort', 'uint16'):
            return struct.unpack('<H', chunk)[0]
        elif ptype in ('int', 'int32'):
            return struct.unpack('<i', chunk)[0]
        elif ptype in ('uint', 'uint32'):
            return struct.unpack('<I', chunk)[0]
        elif ptype in ('float', 'float32'):
            return struct.unpack('<f', chunk)[0]
        elif ptype in ('double', 'float64'):
            return struct.unpack('<d', chunk)[0]

        return 0.0
