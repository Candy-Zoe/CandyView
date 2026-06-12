"""
GLTF/GLB模型加载器
支持带纹理的GLTF/GLB文件
"""

import os
import struct
import json
import base64
import numpy as np
from typing import Optional, List
from core.base_loader import BaseModelLoader, ModelData


class GLTFLoader(BaseModelLoader):
    """GLTF/GLB格式模型加载器 - 增强版"""

    def supports_format(self, extension: str) -> bool:
        return extension.lower() in ['.gltf', '.glb']

    def get_supported_formats(self) -> List[str]:
        return ['.gltf', '.glb']

    def load(self, file_path: str) -> Optional[ModelData]:
        if not os.path.exists(file_path):
            return None

        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.glb':
            return self._parse_glb(file_path)
        else:
            return self._parse_gltf(file_path)

    def _parse_glb(self, file_path: str) -> Optional[ModelData]:
        """解析GLB二进制格式"""
        try:
            with open(file_path, 'rb') as f:
                magic = f.read(4)
                if magic != b'glTF':
                    print("[GLTF] Invalid GLB magic")
                    return None

                version = struct.unpack('<I', f.read(4))[0]
                length = struct.unpack('<I', f.read(4))[0]

                json_chunk_length = struct.unpack('<I', f.read(4))[0]
                json_chunk_type = struct.unpack('<I', f.read(4))[0]
                json_chunk_data = f.read(json_chunk_length)

                gltf_data = json.loads(json_chunk_data.decode('utf-8'))
                
                binary_data = b''
                while f.tell() < length:
                    chunk_length = struct.unpack('<I', f.read(4))[0]
                    chunk_type = struct.unpack('<I', f.read(4))[0]
                    if chunk_type == 0x46546C67:
                        binary_data = f.read(chunk_length)
                    else:
                        f.read(chunk_length)

                return self._extract_model(gltf_data, file_path, binary_data)

        except Exception as e:
            print(f"GLB parse error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_gltf(self, file_path: str) -> Optional[ModelData]:
        """解析GLTF JSON格式"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                gltf_data = json.load(f)

            base_dir = os.path.dirname(file_path) or '.'
            binary_data = b''

            for buffer_info in gltf_data.get('buffers', []):
                if 'uri' in buffer_info:
                    uri = buffer_info['uri']
                    if uri.startswith('data:'):
                        bin_data = uri.split(',')[1]
                        binary_data = base64.b64decode(bin_data)
                    else:
                        bin_path = os.path.join(base_dir, uri)
                        if os.path.exists(bin_path):
                            with open(bin_path, 'rb') as bf:
                                binary_data = bf.read()

            return self._extract_model(gltf_data, file_path, binary_data)

        except Exception as e:
            print(f"GLTF parse error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_model(self, gltf_data, file_path: str, binary_data: bytes) -> Optional[ModelData]:
        """从GLTF数据提取模型"""
        model = ModelData()
        model.format = "GLTF"
        model.name = os.path.basename(file_path)

        vertices = []
        normals = []
        texcoords = []
        colors = []
        triangles = []

        base_dir = os.path.dirname(file_path) or '.'

        try:
            meshes = gltf_data.get('meshes', [])
            accessors = gltf_data.get('accessors', [])
            buffer_views = gltf_data.get('bufferViews', [])
            buffers = gltf_data.get('buffers', [])
            materials = gltf_data.get('materials', [])
            images = gltf_data.get('images', [])

            for image in images:
                if 'uri' in image:
                    uri = image['uri']
                    if not uri.startswith('data:'):
                        tex_path = os.path.join(base_dir, uri)
                        if os.path.exists(tex_path):
                            model.texture_path = tex_path
                            break

            default_scene = gltf_data.get('scene', 0)
            scenes = gltf_data.get('scenes', [{}])
            if scenes and default_scene < len(scenes):
                scene = scenes[default_scene]
                for node_idx in scene.get('nodes', []):
                    nodes = gltf_data.get('nodes', [])
                    if node_idx < len(nodes):
                        node = nodes[node_idx]
                        if 'mesh' in node:
                            mesh_idx = node['mesh']
                            if mesh_idx < len(meshes):
                                mesh = meshes[mesh_idx]
                                self._process_mesh(mesh, accessors, buffer_views, buffers, binary_data,
                                                  vertices, normals, texcoords, colors, triangles)

        except Exception as e:
            print(f"GLTF extract error: {e}")
            import traceback
            traceback.print_exc()

        model.vertices = vertices
        model.normals = normals
        model.texcoords = texcoords if texcoords else None
        model.colors = colors if colors else None
        model.triangles = triangles

        return model if vertices else None

    def _process_mesh(self, mesh, accessors, buffer_views, buffers, binary_data,
                       vertices, normals, texcoords, colors, triangles):
        """处理单个网格"""
        primitives = mesh.get('primitives', [])

        for prim in primitives:
            prim_verts_start = len(vertices)
            prim_triangles_start = len(triangles)

            attributes = prim.get('attributes', {})
            indices_data = None
            index_offset = 0

            if 'POSITION' in attributes:
                acc_idx = attributes['POSITION']
                acc = accessors[acc_idx]
                bv_idx = acc.get('bufferView', 0)
                bv = buffer_views[bv_idx]
                buff_data = binary_data[bv['byteOffset']:bv['byteOffset'] + bv['byteLength']]
                
                count = acc['count']
                stride = bv.get('byteStride', 12)
                for i in range(count):
                    offset = i * stride
                    x = struct.unpack('<f', buff_data[offset:offset+4])[0]
                    y = struct.unpack('<f', buff_data[offset+4:offset+8])[0]
                    z = struct.unpack('<f', buff_data[offset+8:offset+12])[0]
                    vertices.append([x, y, z])

            if 'NORMAL' in attributes:
                acc_idx = attributes['NORMAL']
                acc = accessors[acc_idx]
                bv_idx = acc.get('bufferView', 0)
                bv = buffer_views[bv_idx]
                buff_data = binary_data[bv['byteOffset']:bv['byteOffset'] + bv['byteLength']]
                
                count = acc['count']
                stride = bv.get('byteStride', 12)
                for i in range(count):
                    offset = i * stride
                    nx = struct.unpack('<f', buff_data[offset:offset+4])[0]
                    ny = struct.unpack('<f', buff_data[offset+4:offset+8])[0]
                    nz = struct.unpack('<f', buff_data[offset+8:offset+12])[0]
                    normals.append([nx, ny, nz])

            if 'TEXCOORD_0' in attributes:
                acc_idx = attributes['TEXCOORD_0']
                acc = accessors[acc_idx]
                bv_idx = acc.get('bufferView', 0)
                bv = buffer_views[bv_idx]
                buff_data = binary_data[bv['byteOffset']:bv['byteOffset'] + bv['byteLength']]
                
                count = acc['count']
                component_type = acc.get('componentType', 5126)
                stride = bv.get('byteStride', 8)
                for i in range(count):
                    offset = i * stride
                    s = struct.unpack('<f', buff_data[offset:offset+4])[0]
                    t = struct.unpack('<f', buff_data[offset+4:offset+8])[0]
                    texcoords.append([s, t])

            if 'COLOR_0' in attributes:
                acc_idx = attributes['COLOR_0']
                acc = accessors[acc_idx]
                bv_idx = acc.get('bufferView', 0)
                bv = buffer_views[bv_idx]
                buff_data = binary_data[bv['byteOffset']:bv['byteOffset'] + bv['byteLength']]
                
                count = acc['count']
                component_type = acc.get('componentType', 5126)
                is_normalized = acc.get('normalized', False)
                
                if component_type == 5126:
                    stride = 12 if bv.get('byteStride', 0) == 0 else bv.get('byteStride', 12)
                    for i in range(count):
                        offset = i * stride
                        r = struct.unpack('<f', buff_data[offset:offset+4])[0]
                        g = struct.unpack('<f', buff_data[offset+4:offset+8])[0]
                        b = struct.unpack('<f', buff_data[offset+8:offset+12])[0]
                        colors.append([r, g, b])

            if 'indices' in prim:
                acc_idx = prim['indices']
                acc = accessors[acc_idx]
                bv_idx = acc.get('bufferView', 0)
                bv = buffer_views[bv_idx]
                buff_data = binary_data[bv['byteOffset']:bv['byteOffset'] + bv['byteLength']]
                
                count = acc['count']
                component_type = acc.get('componentType', 5123)
                
                indices = []
                if component_type == 5121:
                    stride = 1
                    for i in range(count):
                        indices.append(buff_data[i])
                elif component_type == 5123:
                    stride = 2
                    for i in range(count):
                        indices.append(struct.unpack('<H', buff_data[i*2:(i+1)*2])[0])
                elif component_type == 5125:
                    stride = 4
                    for i in range(count):
                        indices.append(struct.unpack('<I', buff_data[i*4:(i+1)*4])[0])

                mode = prim.get('mode', 4)
                if mode == 4:
                    for i in range(0, len(indices), 3):
                        if i+2 < len(indices):
                            triangles.append([
                                prim_verts_start + indices[i],
                                prim_verts_start + indices[i+1],
                                prim_verts_start + indices[i+2]
                            ])
                elif mode == 5:
                    for i in range(1, len(indices) - 1):
                        triangles.append([
                            prim_verts_start + indices[0],
                            prim_verts_start + indices[i],
                            prim_verts_start + indices[i+1]
                        ])
