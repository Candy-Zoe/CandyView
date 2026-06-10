import os
import cv2
import numpy as np
import open3d as o3d
from PIL import Image
from scipy.ndimage import gaussian_filter

class ImageTo3DConverter:
    def __init__(self):
        self.output_dir = "output"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def load_image(self, image_path):
        img = Image.open(image_path).convert('RGB')
        return np.array(img)
    
    def estimate_depth(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=5)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=5)
        depth = np.sqrt(sobelx**2 + sobely**2)
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-10)
        depth = gaussian_filter(depth, sigma=2)
        return depth
    
    def create_point_cloud(self, image, depth, scale=0.1):
        h, w = image.shape[:2]
        x, y = np.meshgrid(np.arange(w), np.arange(h))
        x = (x - w / 2) * scale / w
        y = (y - h / 2) * scale / h
        z = depth * scale * 2
        
        points = np.stack([x.flatten(), y.flatten(), z.flatten()], axis=1)
        colors = image.reshape(-1, 3) / 255.0
        
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd.colors = o3d.utility.Vector3dVector(colors)
        
        return pcd
    
    def reconstruct_mesh(self, pcd, voxel_size=0.01):
        pcd_down = pcd.voxel_down_sample(voxel_size=voxel_size)
        pcd_down.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
        
        distances = pcd_down.compute_nearest_neighbor_distance()
        avg_dist = np.mean(distances)
        radius = 3 * avg_dist
        
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd_down,
            o3d.utility.DoubleVector([radius, radius * 2])
        )
        
        return mesh
    
    def export_ply(self, mesh, output_path):
        o3d.io.write_triangle_mesh(output_path, mesh)
        print(f"Model exported to {output_path}")
    
    def convert(self, image_path, output_filename="model.ply", use_mesh=True):
        print(f"Loading image: {image_path}")
        image = self.load_image(image_path)
        
        print("Estimating depth...")
        depth = self.estimate_depth(image)
        
        print("Creating point cloud...")
        pcd = self.create_point_cloud(image, depth)
        
        if use_mesh:
            print("Reconstructing mesh...")
            mesh = self.reconstruct_mesh(pcd)
            mesh.compute_vertex_normals()
        else:
            mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(pcd, 0.03)
        
        output_path = os.path.join(self.output_dir, output_filename)
        self.export_ply(mesh, output_path)
        
        return output_path, pcd, mesh

def main():
    converter = ImageTo3DConverter()
    
    import argparse
    parser = argparse.ArgumentParser(description='Convert image to 3D model')
    parser.add_argument('input_image', help='Path to input image')
    parser.add_argument('--output', default='model.ply', help='Output PLY filename')
    parser.add_argument('--no-mesh', action='store_true', help='Use point cloud instead of mesh')
    args = parser.parse_args()
    
    if not os.path.exists(args.input_image):
        print(f"Error: Input image not found at {args.input_image}")
        return
    
    output_path, pcd, mesh = converter.convert(args.input_image, args.output, not args.no_mesh)
    
    vis = o3d.visualization.Visualizer()
    vis.create_window()
    vis.add_geometry(mesh)
    vis.get_render_option().load_from_json("render_option.json")
    vis.run()
    vis.destroy_window()

if __name__ == "__main__":
    main()