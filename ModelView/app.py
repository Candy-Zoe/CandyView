import os
import numpy as np
import open3d as o3d
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk

class ModelViewer:
    def __init__(self):
        self.vis = None
        self.current_mesh = None
        self.current_pcd = None
        self.current_model = None
        self.is_measuring = False
        self.measurement_points = []
        self.measurement_lines = []
        self.measurement_distances = []
        self.window = None
        self.selected_point = None
        self.setup_gui()
    
    def setup_gui(self):
        self.window = tk.Tk()
        self.window.title("3D Model Viewer")
        self.window.geometry("1300x850")
        
        self.main_frame = tk.Frame(self.window)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.left_panel = tk.Frame(self.main_frame, width=300, bg='#f5f5f5')
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        
        self.canvas_frame = tk.Frame(self.main_frame)
        self.canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.create_menu()
        
        self.control_notebook = ttk.Notebook(self.left_panel)
        self.control_notebook.pack(pady=10, padx=10, fill=tk.X)
        
        self.transform_tab = ttk.Frame(self.control_notebook)
        self.control_notebook.add(self.transform_tab, text="Transform")
        
        self.measure_tab = ttk.Frame(self.control_notebook)
        self.control_notebook.add(self.measure_tab, text="Measurement")
        
        self.info_tab = ttk.Frame(self.control_notebook)
        self.control_notebook.add(self.info_tab, text="Info")
        
        self.setup_transform_panel()
        self.setup_measure_panel()
        self.setup_info_panel()
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def create_menu(self):
        menubar = tk.Menu(self.window)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open", command=self.load_model)
        filemenu.add_command(label="Reload", command=self.reload_model)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=filemenu)
        
        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_command(label="Reset View", command=self.reset_view)
        viewmenu.add_command(label="Show Axes", command=self.toggle_axes)
        viewmenu.add_command(label="Show Wireframe", command=self.toggle_wireframe)
        menubar.add_cascade(label="View", menu=viewmenu)
        
        self.window.config(menu=menubar)
    
    def setup_transform_panel(self):
        self.load_btn = tk.Button(self.transform_tab, text="Load Model", command=self.load_model, bg='#4CAF50', fg='white')
        self.load_btn.pack(pady=10, padx=10, fill=tk.X)
        
        self.reset_btn = tk.Button(self.transform_tab, text="Reset Transform", command=self.reset_view, bg='#2196F3', fg='white')
        self.reset_btn.pack(pady=5, padx=10, fill=tk.X)
        
        ttk.Separator(self.transform_tab, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)
        
        self.scale_label = ttk.Label(self.transform_tab, text="Scale")
        self.scale_label.pack(pady=5, padx=10, anchor=tk.W)
        self.scale_slider = tk.Scale(self.transform_tab, from_=0.1, to=5.0, resolution=0.1, orient=tk.HORIZONTAL, command=self.on_scale_change, length=260)
        self.scale_slider.set(1.0)
        self.scale_slider.pack(pady=5, padx=10, fill=tk.X)
        
        ttk.Separator(self.transform_tab, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)
        
        self.rotate_frame = tk.LabelFrame(self.transform_tab, text="Rotation", padx=5, pady=5)
        self.rotate_frame.pack(pady=5, padx=10, fill=tk.X)
        
        self.rotate_x_slider = tk.Scale(self.rotate_frame, from_=-180, to=180, resolution=1, orient=tk.HORIZONTAL, command=self.on_rotate_x_change, length=240, label="X")
        self.rotate_x_slider.set(0)
        self.rotate_x_slider.pack(pady=2, fill=tk.X)
        
        self.rotate_y_slider = tk.Scale(self.rotate_frame, from_=-180, to=180, resolution=1, orient=tk.HORIZONTAL, command=self.on_rotate_y_change, length=240, label="Y")
        self.rotate_y_slider.set(0)
        self.rotate_y_slider.pack(pady=2, fill=tk.X)
        
        self.rotate_z_slider = tk.Scale(self.rotate_frame, from_=-180, to=180, resolution=1, orient=tk.HORIZONTAL, command=self.on_rotate_z_change, length=240, label="Z")
        self.rotate_z_slider.set(0)
        self.rotate_z_slider.pack(pady=2, fill=tk.X)
        
        ttk.Separator(self.transform_tab, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)
        
        self.translate_frame = tk.LabelFrame(self.transform_tab, text="Translation", padx=5, pady=5)
        self.translate_frame.pack(pady=5, padx=10, fill=tk.X)
        
        self.translate_x_slider = tk.Scale(self.translate_frame, from_=-10, to=10, resolution=0.1, orient=tk.HORIZONTAL, command=self.on_translate_x_change, length=240, label="X")
        self.translate_x_slider.set(0)
        self.translate_x_slider.pack(pady=2, fill=tk.X)
        
        self.translate_y_slider = tk.Scale(self.translate_frame, from_=-10, to=10, resolution=0.1, orient=tk.HORIZONTAL, command=self.on_translate_y_change, length=240, label="Y")
        self.translate_y_slider.set(0)
        self.translate_y_slider.pack(pady=2, fill=tk.X)
        
        self.translate_z_slider = tk.Scale(self.translate_frame, from_=-10, to=10, resolution=0.1, orient=tk.HORIZONTAL, command=self.on_translate_z_change, length=240, label="Z")
        self.translate_z_slider.set(0)
        self.translate_z_slider.pack(pady=2, fill=tk.X)
    
    def setup_measure_panel(self):
        self.measure_btn = tk.Button(self.measure_tab, text="Toggle Measure Mode", command=self.toggle_measure_mode, bg='#ff9800', fg='white')
        self.measure_btn.pack(pady=10, padx=10, fill=tk.X)
        
        self.clear_measure_btn = tk.Button(self.measure_tab, text="Clear All Measurements", command=self.clear_measurements, bg='#f44336', fg='white')
        self.clear_measure_btn.pack(pady=5, padx=10, fill=tk.X)
        
        ttk.Separator(self.measure_tab, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)
        
        self.measurement_list_label = ttk.Label(self.measure_tab, text="Measurements:")
        self.measurement_list_label.pack(pady=5, padx=10, anchor=tk.W)
        
        self.measurement_list = tk.Listbox(self.measure_tab, height=10)
        self.measurement_list.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        
        self.delete_measure_btn = tk.Button(self.measure_tab, text="Delete Selected", command=self.delete_selected_measurement)
        self.delete_measure_btn.pack(pady=5, padx=10, fill=tk.X)
    
    def setup_info_panel(self):
        self.info_text = tk.Text(self.info_tab, height=20, wrap=tk.WORD)
        self.info_text.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.info_text.insert(tk.END, "Load a model to see information...")
        self.info_text.config(state=tk.DISABLED)
    
    def load_model(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("3D Models", "*.ply *.obj *.stl *.glb *.gltf"), ("All Files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            self.clear_measurements()
            
            ext = os.path.splitext(file_path)[1].lower()
            self.current_model_path = file_path
            
            if ext in ['.ply', '.obj', '.stl']:
                self.current_mesh = o3d.io.read_triangle_mesh(file_path)
                self.current_pcd = None
                self.current_model = self.current_mesh
            elif ext in ['.glb', '.gltf']:
                self.current_mesh = o3d.io.read_triangle_mesh(file_path)
                self.current_pcd = None
                self.current_model = self.current_mesh
            else:
                messagebox.showerror("Error", "Unsupported file format")
                return
            
            if self.current_mesh.has_vertices():
                self.apply_default_materials()
                self.update_info()
                self.show_model()
            else:
                messagebox.showerror("Error", "Failed to load model")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load model: {str(e)}")
    
    def reload_model(self):
        if hasattr(self, 'current_model_path') and self.current_model_path:
            self.load_model()
    
    def apply_default_materials(self):
        if self.current_mesh and not self.current_mesh.has_textures():
            self.current_mesh.compute_vertex_normals()
            self.current_mesh.paint_uniform_color([0.7, 0.7, 0.7])
    
    def update_info(self):
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        
        if self.current_mesh:
            vertices = len(self.current_mesh.vertices)
            triangles = len(self.current_mesh.triangles)
            has_texture = self.current_mesh.has_textures()
            has_normals = self.current_mesh.has_vertex_normals()
            
            info = f"Model Information\n"
            info += "="*30 + "\n\n"
            info += f"Vertices: {vertices:,}\n"
            info += f"Triangles: {triangles:,}\n"
            info += f"Textures: {'Yes' if has_texture else 'No'}\n"
            info += f"Normals: {'Yes' if has_normals else 'No'}\n\n"
            
            aabb = self.current_mesh.get_axis_aligned_bounding_box()
            min_bound = aabb.min_bound
            max_bound = aabb.max_bound
            size = max_bound - min_bound
            
            info += "Bounding Box\n"
            info += "-"*30 + "\n"
            info += f"Min: ({min_bound[0]:.3f}, {min_bound[1]:.3f}, {min_bound[2]:.3f})\n"
            info += f"Max: ({max_bound[0]:.3f}, {max_bound[1]:.3f}, {max_bound[2]:.3f})\n"
            info += f"Size: ({size[0]:.3f}, {size[1]:.3f}, {size[2]:.3f})\n\n"
            
            center = self.current_mesh.get_center()
            info += f"Center: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})\n"
            
            self.info_text.insert(tk.END, info)
        else:
            self.info_text.insert(tk.END, "No model loaded")
        
        self.info_text.config(state=tk.DISABLED)
    
    def show_model(self):
        if self.vis:
            self.vis.destroy_window()
        
        self.vis = o3d.visualization.VisualizerWithKeyCallback()
        self.vis.create_window(width=950, height=800, window_name="3D Viewer")
        
        if self.current_mesh:
            self.vis.add_geometry(self.current_mesh)
        
        self.axis_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=1.0)
        self.vis.add_geometry(self.axis_frame)
        
        self.vis.get_render_option().background_color = [1, 1, 1]
        self.vis.get_render_option().mesh_show_back_face = True
        
        self.vis.register_key_callback(262, self.on_key_right)
        self.vis.register_key_callback(263, self.on_key_left)
        self.vis.register_key_callback(264, self.on_key_down)
        self.vis.register_key_callback(265, self.on_key_up)
        
        self.vis.run()
    
    def on_key_right(self, vis):
        if self.current_model:
            self.current_model.rotate(o3d.geometry.get_rotation_matrix_from_xyz((0, np.radians(15), 0)), center=self.current_model.get_center())
            vis.update_geometry(self.current_model)
        return False
    
    def on_key_left(self, vis):
        if self.current_model:
            self.current_model.rotate(o3d.geometry.get_rotation_matrix_from_xyz((0, np.radians(-15), 0)), center=self.current_model.get_center())
            vis.update_geometry(self.current_model)
        return False
    
    def on_key_down(self, vis):
        if self.current_model:
            self.current_model.rotate(o3d.geometry.get_rotation_matrix_from_xyz((np.radians(15), 0, 0)), center=self.current_model.get_center())
            vis.update_geometry(self.current_model)
        return False
    
    def on_key_up(self, vis):
        if self.current_model:
            self.current_model.rotate(o3d.geometry.get_rotation_matrix_from_xyz((np.radians(-15), 0, 0)), center=self.current_model.get_center())
            vis.update_geometry(self.current_model)
        return False
    
    def on_scale_change(self, value):
        if self.current_model:
            scale = float(value)
            self.current_model.scale(scale, center=self.current_model.get_center())
            if self.vis:
                self.vis.update_geometry(self.current_model)
                self.vis.poll_events()
                self.vis.update_renderer()
            self.scale_slider.set(1.0)
    
    def on_rotate_x_change(self, value):
        if self.current_model:
            angle = np.radians(float(value))
            self.current_model.rotate(o3d.geometry.get_rotation_matrix_from_xyz((angle, 0, 0)), center=self.current_model.get_center())
            if self.vis:
                self.vis.update_geometry(self.current_model)
                self.vis.poll_events()
                self.vis.update_renderer()
            self.rotate_x_slider.set(0)
    
    def on_rotate_y_change(self, value):
        if self.current_model:
            angle = np.radians(float(value))
            self.current_model.rotate(o3d.geometry.get_rotation_matrix_from_xyz((0, angle, 0)), center=self.current_model.get_center())
            if self.vis:
                self.vis.update_geometry(self.current_model)
                self.vis.poll_events()
                self.vis.update_renderer()
            self.rotate_y_slider.set(0)
    
    def on_rotate_z_change(self, value):
        if self.current_model:
            angle = np.radians(float(value))
            self.current_model.rotate(o3d.geometry.get_rotation_matrix_from_xyz((0, 0, angle)), center=self.current_model.get_center())
            if self.vis:
                self.vis.update_geometry(self.current_model)
                self.vis.poll_events()
                self.vis.update_renderer()
            self.rotate_z_slider.set(0)
    
    def on_translate_x_change(self, value):
        if self.current_model:
            tx = float(value)
            self.current_model.translate((tx, 0, 0))
            if self.vis:
                self.vis.update_geometry(self.current_model)
                self.vis.poll_events()
                self.vis.update_renderer()
            self.translate_x_slider.set(0)
    
    def on_translate_y_change(self, value):
        if self.current_model:
            ty = float(value)
            self.current_model.translate((0, ty, 0))
            if self.vis:
                self.vis.update_geometry(self.current_model)
                self.vis.poll_events()
                self.vis.update_renderer()
            self.translate_y_slider.set(0)
    
    def on_translate_z_change(self, value):
        if self.current_model:
            tz = float(value)
            self.current_model.translate((0, 0, tz))
            if self.vis:
                self.vis.update_geometry(self.current_model)
                self.vis.poll_events()
                self.vis.update_renderer()
            self.translate_z_slider.set(0)
    
    def reset_view(self):
        self.scale_slider.set(1.0)
        self.rotate_x_slider.set(0)
        self.rotate_y_slider.set(0)
        self.rotate_z_slider.set(0)
        self.translate_x_slider.set(0)
        self.translate_y_slider.set(0)
        self.translate_z_slider.set(0)
        
        if self.current_model:
            self.current_model.transform(np.eye(4))
            if self.vis:
                self.vis.update_geometry(self.current_model)
                self.vis.poll_events()
                self.vis.update_renderer()
    
    def toggle_measure_mode(self):
        self.is_measuring = not self.is_measuring
        self.measure_btn.config(bg='#f44336' if self.is_measuring else '#ff9800')
        if self.is_measuring:
            self.measure_btn.config(text="Exit Measure Mode")
            messagebox.showinfo("Measure Mode", "Click on two points on the model to measure distance\n\nKeyboard controls:\n- Arrow keys: Rotate model")
        else:
            self.measure_btn.config(text="Toggle Measure Mode")
            self.measurement_points = []
    
    def clear_measurements(self):
        for line in self.measurement_lines:
            if self.vis:
                self.vis.remove_geometry(line)
        self.measurement_lines = []
        self.measurement_points = []
        self.measurement_distances = []
        self.measurement_list.delete(0, tk.END)
        if self.vis:
            self.vis.poll_events()
            self.vis.update_renderer()
    
    def delete_selected_measurement(self):
        selected = self.measurement_list.curselection()
        if selected:
            idx = selected[0]
            if idx < len(self.measurement_lines):
                if self.vis:
                    self.vis.remove_geometry(self.measurement_lines[idx])
                del self.measurement_lines[idx]
                del self.measurement_distances[idx]
                self.measurement_list.delete(idx)
                if self.vis:
                    self.vis.poll_events()
                    self.vis.update_renderer()
    
    def add_measurement(self, p1, p2):
        distance = np.linalg.norm(np.array(p2) - np.array(p1))
        
        line_points = o3d.utility.Vector3dVector([p1, p2])
        line = o3d.geometry.LineSet()
        line.points = line_points
        line.lines = o3d.utility.Vector2iVector([[0, 1]])
        line.colors = o3d.utility.Vector3dVector([[1, 0, 0]])
        
        self.measurement_lines.append(line)
        self.measurement_distances.append(distance)
        
        if self.vis:
            self.vis.add_geometry(line)
            self.vis.poll_events()
            self.vis.update_renderer()
        
        self.measurement_list.insert(tk.END, f"Distance: {distance:.4f} units")
    
    def toggle_axes(self):
        if self.axis_frame and self.vis:
            self.axis_frame.visible = not self.axis_frame.visible
            self.vis.update_geometry(self.axis_frame)
            self.vis.poll_events()
            self.vis.update_renderer()
    
    def toggle_wireframe(self):
        if self.vis:
            opt = self.vis.get_render_option()
            opt.mesh_show_wireframe = not opt.mesh_show_wireframe
            self.vis.update_renderer()
    
    def run(self):
        self.window.mainloop()
    
    def on_close(self):
        if self.vis:
            self.vis.destroy_window()
        self.window.destroy()

def main():
    viewer = ModelViewer()
    viewer.run()

if __name__ == "__main__":
    main()