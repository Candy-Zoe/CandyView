"""
GLTF/GLB模型加载器
使用pygltflib库，导入延迟处理
"""

import os
import struct
from typing import Optional, List
from core.base_loader import BaseModelLoader, ModelData


class GLTFLoader(BaseModelLoader):
    """GLTF/GLB格式模型加载器"""

    def supports_format(self, extension: str) -> bool:
        """检查是否支持GLTF/GLB格式"""
        return extension.lower() in ['.gltf', '.glb']

    def get_supported_formats(self) -> List[str]:
        """获取支持的格式列表"""
        return ['.gltf', '.glb']

    def load(self, file_path: str) -> Optional[ModelData]:
        """加载GLTF/GLB文件"""
        if not os.path.exists(file_path):
            return None

        # 延迟导入pygltflib
        try:
            import pygltflib
            return self._parse_with_pygltflib(file_path, pygltflib)
        except ImportError:
            # pygltflib不可用，尝试手动解析
            return self._parse_manual(file_path)
        except Exception as e:
            print(f"GLTF load error: {e}")
            return self._parse_manual(file_path)

    def _parse_with_pygltflib(self, file_path: str, pygltflib) -> Optional[ModelData]:
        """使用pygltflib解析"""
        try:
            gltf = pygltflib.GLTF2().load(file_path)
            return self._extract_from_gltf(gltf, file_path)
        except Exception as e:
            print(f"pygltflib parse failed: {e}")
            return None

    def _extract_from_gltf(self, gltf, file_path: str) -> Optional[ModelData]:
        """从GLTF对象提取顶点和三角形"""
        model = ModelData()
        model.format = "GLTF"
        model.name = os.path.basename(file_path)

        vertices = []
        triangles = []
        normals = []

        for scene in gltf.scenes:
            for node_id in scene.nodes:
                node = gltf.nodes[node_id]
                if hasattr(node, 'mesh') and node.mesh is not None:
                    mesh = gltf.meshes[node.mesh]
                    for primitive in mesh.primitives:
                        # 读取顶点
                        if hasattr(primitive.attributes, 'POSITION') and primitive.attributes.POSITION is not None:
                            acc_id = primitive.attributes.POSITION
                            accessor = gltf.accessors[acc_id]
                            bufferview = gltf.bufferViews[accessor.bufferView]
                            buffer = gltf.buffers[bufferview.buffer]

                            data = buffer.data[bufferview.byteOffset or 0: bufferview.byteOffset or 0 + bufferview.byteLength]
                            count = accessor.count
                            for i in range(count):
                                offset = i * 12
                                x = struct.unpack('<f', data[offset:offset+4])[0]
                                y = struct.unpack('<f', data[offset+4:offset+8])[0]
                                z = struct.unpack('<f', data[offset+8:offset+12])[0]
                                vertices.append([x, y, z])

                        # 读取索引
                        if hasattr(primitive, 'indices') and primitive.indices is not None:
                            acc_id = primitive.indices
                            accessor = gltf.accessors[acc_id]
                            bufferview = gltf.bufferViews[accessor.bufferView]
                            buffer = gltf.buffers[bufferview.buffer]

                            data = buffer.data[bufferview.byteOffset or 0: bufferview.byteOffset or 0 + bufferview.byteLength]
                            count = accessor.count

                            if accessor.componentType == 5123:  # UNSIGNED_SHORT
                                stride = 2
                                for i in range(0, count, 3):
                                    i0 = struct.unpack('<H', data[i*stride:(i+1)*stride])[0]
                                    i1 = struct.unpack('<H', data[(i+1)*stride:(i+2)*stride])[0]
                                    i2 = struct.unpack('<H', data[(i+2)*stride:(i+3)*stride])[0]
                                    triangles.append([i0, i1, i2])
                            else:  # UNSIGNED_INT
                                stride = 4
                                for i in range(0, count, 3):
                                    i0 = struct.unpack('<I', data[i*stride:(i+1)*stride])[0]
                                    i1 = struct.unpack('<I', data[(i+1)*stride:(i+2)*stride])[0]
                                    i2 = struct.unpack('<I', data[(i+2)*stride:(i+3)*stride])[0]
                                    triangles.append([i0, i1, i2])

        model.vertices = vertices
        model.triangles = triangles
        model.normals = normals

        return model

    def _parse_manual(self, file_path: str) -> Optional[ModelData]:
        """手动解析GLB格式（最简单的二进制解析）"""
        if not file_path.lower().endswith('.glb'):
            return None

        try:
            model = ModelData()
            model.format = "GLB"
            model.name = os.path.basename(file_path)

            with open(file_path, 'rb') as f:
                # GLB头部：magic(4) + version(4) + length(4)
                header = f.read(12)
                if len(header) < 12 or header[:4] != b'glTF':
                    return None

                # 简化：不做完整解析，返回空模型让Open3D保底
                return model

        except Exception as e:
            print(f"Manual GLB parse failed: {e}")
            return None
