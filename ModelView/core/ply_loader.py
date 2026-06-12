"""
PLY模型加载器
支持ASCII和二进制PLY格式，包括带纹理的PLY
"""

import struct
import os
import numpy as np
from typing import Optional, List
from core.base_loader import BaseModelLoader, ModelData


class PLYLoader(BaseModelLoader):
    """PLY格式模型加载器"""

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
                model.texture_path = header.get('texture_file', '')

                print(f"[PLY] format={header['format']}, vertices={header['vertex_count']}, faces={header['face_count']}")
                print(f"[PLY] vertex_props: {header['vertex_props']}")

                if header['is_binary']:
                    self._parse_binary(f, model, header)
                else:
                    self._parse_ascii(f, model, header)

                print(f"[PLY] loaded {len(model.vertices)} vertices, {len(model.triangles)} triangles")
                return model

        except Exception as e:
            print(f"PLY load error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _read_header(self, file) -> dict:
        """读取PLY头部"""
        header = {
            'format': 'ascii',
            'is_binary': False,
            'vertex_count': 0,
            'face_count': 0,
            'vertex_props': [],  # [(type, name), ...]
            'face_props': [],
            'texture_file': ''
        }

        current_element = None

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
                if len(parts) >= 2:
                    header['format'] = parts[1]
                    header['is_binary'] = 'binary' in parts[1].lower()

            elif line.startswith('comment TextureFile'):
                parts = line.split()
                if len(parts) >= 3:
                    header['texture_file'] = parts[2]

            elif line.startswith('element vertex'):
                parts = line.split()
                if len(parts) >= 3:
                    header['vertex_count'] = int(parts[2])
                    current_element = 'vertex'

            elif line.startswith('element face'):
                parts = line.split()
                if len(parts) >= 3:
                    header['face_count'] = int(parts[2])
                    current_element = 'face'

            elif line.startswith('property'):
                parts = line.split()
                if current_element == 'vertex' and len(parts) >= 3:
                    prop_type = parts[1]
                    prop_name = parts[2]
                    header['vertex_props'].append((prop_type, prop_name))
                elif current_element == 'face':
                    header['face_props'].append(line)

            elif line == 'end_header':
                break

        return header

    def _get_type_size(self, ptype: str) -> int:
        """获取PLY数据类型的字节大小"""
        type_map = {
            'char': 1, 'int8': 1,
            'uchar': 1, 'uint8': 1,
            'short': 2, 'int16': 2,
            'ushort': 2, 'uint16': 2,
            'int': 4, 'int32': 4,
            'uint': 4, 'uint32': 4,
            'float': 4, 'float32': 4,
            'double': 8, 'float64': 8
        }
        return type_map.get(ptype.lower(), 0)

    def _parse_ascii(self, file, model, header):
        """解析ASCII格式PLY"""
        vertices = []
        colors = []
        triangles = []
        texcoords = []

        vertex_count = header['vertex_count']
        face_count = header['face_count']
        vertex_props = header['vertex_props']

        x_idx = y_idx = z_idx = -1
        r_idx = g_idx = b_idx = -1
        s_idx = t_idx = -1

        for i, (ptype, pname) in enumerate(vertex_props):
            if pname == 'x': x_idx = i
            elif pname == 'y': y_idx = i
            elif pname == 'z': z_idx = i
            elif pname == 'red' or pname == 'r': r_idx = i
            elif pname == 'green' or pname == 'g': g_idx = i
            elif pname == 'blue' or pname == 'b': b_idx = i
            elif pname == 's' or pname == 'u': s_idx = i
            elif pname == 't' or pname == 'v': t_idx = i

        for i in range(vertex_count):
            line = file.readline()
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='ignore')
            parts = line.strip().split()

            if len(parts) >= 3:
                x = float(parts[x_idx]) if x_idx >= 0 and x_idx < len(parts) else 0.0
                y = float(parts[y_idx]) if y_idx >= 0 and y_idx < len(parts) else 0.0
                z = float(parts[z_idx]) if z_idx >= 0 and z_idx < len(parts) else 0.0
                vertices.append([x, y, z])

                if r_idx >= 0 and g_idx >= 0 and b_idx >= 0:
                    if r_idx < len(parts) and g_idx < len(parts) and b_idx < len(parts):
                        r = float(parts[r_idx])
                        g = float(parts[g_idx])
                        b = float(parts[b_idx])
                        if r > 1 or g > 1 or b > 1:
                            r, g, b = r/255.0, g/255.0, b/255.0
                        colors.append([r, g, b])

                if s_idx >= 0 and t_idx >= 0:
                    if s_idx < len(parts) and t_idx < len(parts):
                        s = float(parts[s_idx])
                        t = float(parts[t_idx])
                        texcoords.append([s, t])

        for i in range(face_count):
            line = file.readline()
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='ignore')
            parts = line.strip().split()

            if parts:
                n = int(parts[0])
                if n >= 3 and len(parts) >= n + 1:
                    face = [int(parts[j + 1]) for j in range(n)]
                    for j in range(1, n - 1):
                        triangles.append([face[0], face[j], face[j + 1]])

        model.vertices = vertices
        model.triangles = triangles
        model.colors = colors if colors else None
        model.texcoords = texcoords if texcoords else None
        if vertices:
            model.normals = self._compute_normals(vertices, triangles) if triangles else None

    def _parse_binary(self, file, model, header):
        """解析二进制格式PLY"""
        vertices = []
        colors = []
        texcoords = []
        triangles = []

        vertex_count = header['vertex_count']
        face_count = header['face_count']
        vertex_props = header['vertex_props']
        is_big_endian = header['format'] == 'binary_big_endian'
        endian = '>' if is_big_endian else '<'

        vertex_size = 0
        prop_info = []
        has_color = False
        has_texcoord = False

        for ptype, pname in vertex_props:
            size = self._get_type_size(ptype)
            prop_info.append((pname, vertex_size, ptype, size))
            vertex_size += size
            if pname in ('red', 'green', 'blue', 'r', 'g', 'b'):
                has_color = True
            if pname in ('s', 't', 'u', 'v'):
                has_texcoord = True

        print(f"[PLY] vertex_size={vertex_size}, has_color={has_color}, has_texcoord={has_texcoord}")

        for i in range(vertex_count):
            data = file.read(vertex_size)
            if len(data) < vertex_size:
                print(f"[PLY] vertex read incomplete at {i}")
                break

            x = y = z = 0.0
            r = g = b = 0.7
            s = t = 0.0
            current_rgb = []
            current_st = []

            for pname, offset, ptype, size in prop_info:
                chunk = data[offset:offset+size]
                if not chunk:
                    continue

                if ptype in ('float', 'float32'):
                    val = struct.unpack(endian + 'f', chunk)[0]
                elif ptype in ('double', 'float64'):
                    val = struct.unpack(endian + 'd', chunk)[0]
                elif ptype in ('uchar', 'uint8'):
                    val = struct.unpack('B', chunk)[0]
                elif ptype in ('uint', 'uint32'):
                    val = struct.unpack(endian + 'I', chunk)[0]
                elif ptype in ('int', 'int32'):
                    val = struct.unpack(endian + 'i', chunk)[0]
                else:
                    val = 0.0

                if pname == 'x': x = val
                elif pname == 'y': y = val
                elif pname == 'z': z = val
                elif pname in ('red', 'r'):
                    current_rgb.append(val)
                elif pname in ('green', 'g'):
                    current_rgb.append(val)
                elif pname in ('blue', 'b'):
                    current_rgb.append(val)
                elif pname in ('s', 'u'):
                    current_st.append(val)
                elif pname in ('t', 'v'):
                    current_st.append(val)

            vertices.append([x, y, z])

            if len(current_rgb) == 3:
                r, g, b = current_rgb
                if r > 1 or g > 1 or b > 1:
                    r, g, b = r/255.0, g/255.0, b/255.0
                colors.append([r, g, b])

            if len(current_st) == 2:
                texcoords.append(current_st)

        has_face_texcoord = any('texcoord' in p.lower() for p in header['face_props'])

        for i in range(face_count):
            n_byte = file.read(1)
            if len(n_byte) < 1:
                break
            n = struct.unpack('B', n_byte)[0]

            indices_data = file.read(n * 4)
            if len(indices_data) < n * 4:
                break

            fmt = endian + 'I' * n
            indices = list(struct.unpack(fmt, indices_data))

            if n >= 3:
                for j in range(1, n - 1):
                    triangles.append([indices[0], indices[j], indices[j + 1]])

            if has_face_texcoord:
                try:
                    tc_n_byte = file.read(1)
                    if len(tc_n_byte) == 1:
                        tc_n = struct.unpack('B', tc_n_byte)[0]
                        file.read(tc_n * 4)
                except:
                    pass

        model.vertices = vertices
        model.triangles = triangles
        model.colors = colors if colors else None
        model.texcoords = texcoords if texcoords else None
        if vertices:
            model.normals = self._compute_normals(vertices, triangles) if triangles else None
