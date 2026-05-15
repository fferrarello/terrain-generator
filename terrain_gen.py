import maya.cmds as cmds
import maya.api.OpenMaya as om
import random
import math
import json

# Determine PySide version
PYSIDE_VER = 0
try:
    from PySide6 import QtWidgets, QtCore, QtGui
    PYSIDE_VER = 6
except ImportError:
    try:
        from PySide2 import QtWidgets, QtCore, QtGui
        PYSIDE_VER = 2
    except ImportError:
        PYSIDE_VER = 0
        QtWidgets = None

BaseDialog = QtWidgets.QDialog if PYSIDE_VER > 0 else object

# =========================
# IMPROVED NOISE GENERATION
# =========================
class ImprovedNoise:
    def __init__(self, seed=42):
        self.p = list(range(256))
        random.seed(seed)
        random.shuffle(self.p)
        self.p += self.p

    def fade(self, t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    def lerp(self, t, a, b):
        return a + t * (b - a)

    def grad(self, hash, x, y, z):
        h = hash & 15
        u = x if h < 8 else y
        v = y if h < 4 else (x if h == 12 or h == 14 else z)
        return (u if h & 1 == 0 else -u) + (v if h & 2 == 0 else -v)

    def noise(self, x, y, z):
        X = int(math.floor(x)) & 255
        Y = int(math.floor(y)) & 255
        Z = int(math.floor(z)) & 255

        x -= math.floor(x)
        y -= math.floor(y)
        z -= math.floor(z)

        u = self.fade(x)
        v = self.fade(y)
        w = self.fade(z)

        A = self.p[X] + Y
        AA = self.p[A] + Z
        AB = self.p[A + 1] + Z
        B = self.p[X + 1] + Y
        BA = self.p[B] + Z
        BB = self.p[B + 1] + Z

        return self.lerp(w, self.lerp(v, self.lerp(u, self.grad(self.p[AA], x, y, z),
                                                   self.grad(self.p[BA], x - 1, y, z)),
                                      self.lerp(u, self.grad(self.p[AB], x, y - 1, z),
                                                self.grad(self.p[BB], x - 1, y - 1, z))),
                         self.lerp(v, self.lerp(u, self.grad(self.p[AA + 1], x, y, z - 1),
                                                self.grad(self.p[BA + 1], x - 1, y, z - 1)),
                                   self.lerp(u, self.grad(self.p[AB + 1], x, y - 1, z - 1),
                                             self.grad(self.p[BB + 1], x - 1, y - 1, z - 1))))

# =========================
# FRACTAL BROWNIAN MOTION
# =========================
def fbm(x, y, z, noise_gen, octaves=4, persistence=0.5, lacunarity=2.0):
    total = 0
    frequency = 1
    amplitude = 1
    max_value = 0
    for _ in range(octaves):
        total += noise_gen.noise(x * frequency, y * frequency, z * frequency) * amplitude
        max_value += amplitude
        amplitude *= persistence
        frequency *= lacunarity
    return total / max_value

# =========================
# RIDGED MULTIFRACTAL
# =========================
def ridged_multifractal(x, y, z, noise_gen, octaves=4, persistence=0.5, lacunarity=2.0):
    total = 0
    frequency = 1
    amplitude = 1
    weight = 1.0
    for _ in range(octaves):
        n = noise_gen.noise(x * frequency, y * frequency, z * frequency)
        n = 1.0 - abs(n)
        n *= n
        n *= weight
        weight = max(0.0, min(n * 2.0, 1.0))
        total += n * amplitude
        amplitude *= persistence
        frequency *= lacunarity
    return total

# =========================
# UI APPLICATION
# =========================
class AITerrainGeneratorUI(BaseDialog):
    def __init__(self, parent=None):
        if PYSIDE_VER == 0:
            cmds.error("PySide is required for the AI Terrain Generator UI.")
            return
            
        super().__init__(parent)
        self.setWindowTitle("AI Terrain & Environment Generator - Pro")
        self.setMinimumWidth(400)
        
        # Apply dark theme stylesheet
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            QGroupBox {
                border: 1px solid #333333;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                color: #4fc3f7;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QLabel {
                color: #cccccc;
            }
            QSlider::groove:horizontal {
                border: 1px solid #333333;
                height: 6px;
                background: #2d2d2d;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #4fc3f7;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QPushButton {
                background-color: #2b2b2b;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 8px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3b3b3b;
                border: 1px solid #4fc3f7;
            }
            QPushButton#generateBtn {
                background-color: #0277bd;
                border: none;
                font-size: 14px;
            }
            QPushButton#generateBtn:hover {
                background-color: #0288d1;
            }
            QPushButton#aiBtn {
                background-color: #5e35b1;
                border: none;
            }
            QPushButton#aiBtn:hover {
                background-color: #673ab7;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #2d2d2d;
                border: 1px solid #444444;
                border-radius: 3px;
                padding: 4px;
                color: #ffffff;
            }
            QTextEdit {
                background-color: #2d2d2d;
                border: 1px solid #444444;
                border-radius: 4px;
                color: #ffffff;
                padding: 4px;
            }
        """)
        
        self.setup_ui()

    def setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # --- AI Integration Section ---
        ai_group = QtWidgets.QGroupBox("AI Assistant (Maya 2027 API)")
        ai_layout = QtWidgets.QVBoxLayout(ai_group)
        
        self.ai_prompt = QtWidgets.QTextEdit()
        self.ai_prompt.setPlaceholderText("Describe the environment (e.g., 'A rugged mountainous region with scattered pine trees')")
        self.ai_prompt.setMaximumHeight(60)
        ai_layout.addWidget(self.ai_prompt)
        
        self.ai_btn = QtWidgets.QPushButton("✨ Generate Settings via AI")
        self.ai_btn.setObjectName("aiBtn")
        self.ai_btn.clicked.connect(self.simulate_ai_api)
        ai_layout.addWidget(self.ai_btn)
        
        main_layout.addWidget(ai_group)
        
        # --- Terrain Parameters ---
        terrain_group = QtWidgets.QGroupBox("Terrain Generation")
        t_layout = QtWidgets.QFormLayout(terrain_group)
        
        self.size_spin = QtWidgets.QSpinBox()
        self.size_spin.setRange(10, 1000)
        self.size_spin.setValue(100)
        t_layout.addRow("Size (Units):", self.size_spin)
        
        self.res_spin = QtWidgets.QSpinBox()
        self.res_spin.setRange(10, 500)
        self.res_spin.setValue(150)
        t_layout.addRow("Resolution:", self.res_spin)
        
        self.height_spin = QtWidgets.QDoubleSpinBox()
        self.height_spin.setRange(1, 500)
        self.height_spin.setValue(30.0)
        t_layout.addRow("Max Height:", self.height_spin)
        
        self.noise_type = QtWidgets.QComboBox()
        self.noise_type.addItems(["fBm (Smooth/Hills)", "Ridged Multifractal (Mountains)"])
        t_layout.addRow("Noise Algorithm:", self.noise_type)
        
        # Sliders layout helper
        def add_slider(label, min_val, max_val, default, multiplier=100.0):
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(int(min_val * multiplier), int(max_val * multiplier))
            slider.setValue(int(default * multiplier))
            val_label = QtWidgets.QLabel(str(default))
            
            def update_label(val):
                val_label.setText(f"{val / multiplier:.2f}")
                
            slider.valueChanged.connect(update_label)
            
            row = QtWidgets.QHBoxLayout()
            row.addWidget(slider)
            row.addWidget(val_label)
            t_layout.addRow(label, row)
            return slider, multiplier

        self.scale_slider, self.scale_mult = add_slider("Scale:", 0.01, 10.0, 2.0)
        self.octaves_spin = QtWidgets.QSpinBox()
        self.octaves_spin.setRange(1, 8)
        self.octaves_spin.setValue(5)
        t_layout.addRow("Octaves (Detail):", self.octaves_spin)
        
        self.seed_spin = QtWidgets.QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(42)
        t_layout.addRow("Seed:", self.seed_spin)
        
        main_layout.addWidget(terrain_group)
        
        # --- Objects / Scatter Section ---
        scatter_group = QtWidgets.QGroupBox("Environment Population")
        s_layout = QtWidgets.QFormLayout(scatter_group)
        
        self.obj_type = QtWidgets.QComboBox()
        self.obj_type.addItems(["Cylinders (Trees)", "Cubes (Rocks/Buildings)", "Spheres (Boulders)"])
        s_layout.addRow("Object Type:", self.obj_type)
        
        self.obj_count = QtWidgets.QSpinBox()
        self.obj_count.setRange(0, 5000)
        self.obj_count.setValue(50)
        s_layout.addRow("Density (Count):", self.obj_count)
        
        main_layout.addWidget(scatter_group)
        
        # --- Generate Button ---
        self.gen_btn = QtWidgets.QPushButton("Generate Terrain & Environment")
        self.gen_btn.setObjectName("generateBtn")
        self.gen_btn.setMinimumHeight(40)
        self.gen_btn.clicked.connect(self.generate_terrain)
        main_layout.addWidget(self.gen_btn)

    def simulate_ai_api(self):
        """Simulate an AI API interpreting the prompt and adjusting sliders."""
        prompt = self.ai_prompt.toPlainText().lower()
        if not prompt:
            QtWidgets.QMessageBox.warning(self, "AI Assistant", "Please enter a prompt first.")
            return
            
        cmds.inViewMessage(amg="AI is analyzing prompt...", pos='midCenter', fade=True)
        
        # Mock logic based on keywords
        if "mountain" in prompt or "rugged" in prompt:
            self.noise_type.setCurrentIndex(1)  # Ridged
            self.height_spin.setValue(60.0)
            self.scale_slider.setValue(int(3.0 * self.scale_mult))
            self.octaves_spin.setValue(6)
            self.obj_type.setCurrentIndex(0)
            self.obj_count.setValue(200 if "tree" in prompt else 20)
        elif "plain" in prompt or "flat" in prompt:
            self.noise_type.setCurrentIndex(0)  # fBm
            self.height_spin.setValue(10.0)
            self.scale_slider.setValue(int(1.0 * self.scale_mult))
            self.octaves_spin.setValue(3)
        
        self.seed_spin.setValue(random.randint(1, 9999))
        cmds.inViewMessage(amg="AI configured parameters successfully!", pos='midCenter', fade=True)

    def generate_terrain(self):
        size = self.size_spin.value()
        res = self.res_spin.value()
        max_height = self.height_spin.value()
        scale = self.scale_slider.value() / self.scale_mult
        octaves = self.octaves_spin.value()
        seed = self.seed_spin.value()
        algo = self.noise_type.currentIndex()
        
        noise_gen = ImprovedNoise(seed)
        
        # Delete old terrain if exists
        if cmds.objExists("AITerrain_Mesh"):
            cmds.delete("AITerrain_Mesh")
            
        # Create Plane
        plane = cmds.polyPlane(w=size, h=size, sx=res, sy=res, name="AITerrain_Mesh")[0]
        
        # OpenMaya 2.0 Fast Vertex Modification
        selection_list = om.MSelectionList()
        selection_list.add(plane)
        dag_path = selection_list.getDagPath(0)
        
        mesh_fn = om.MFnMesh(dag_path)
        points = mesh_fn.getPoints(om.MSpace.kObject)
        
        for i in range(len(points)):
            x = points[i].x
            z = points[i].z
            
            # Map coordinates to noise space
            nx = (x / size) * scale
            nz = (z / size) * scale
            
            if algo == 0:
                h = fbm(nx, 0.0, nz, noise_gen, octaves=octaves)
            else:
                h = ridged_multifractal(nx, 0.0, nz, noise_gen, octaves=octaves)
                
            points[i].y = h * max_height
            
        mesh_fn.setPoints(points, om.MSpace.kObject)
        
        # Smooth and update normals
        cmds.polySoftEdge(plane, angle=180)
        cmds.polyNormal(plane, normalMode=2) # Update normals
        
        # Populate objects
        self.populate_objects(plane, size, max_height)
        
        cmds.select(clear=True)
        cmds.inViewMessage(amg="High-Fidelity Terrain Generated!", pos='midCenter', fade=True)

    def populate_objects(self, terrain_mesh, size, max_height):
        # Clean up old objects
        if cmds.objExists("AI_Environment_Grp"):
            cmds.delete("AI_Environment_Grp")
            
        count = self.obj_count.value()
        if count <= 0:
            return
            
        grp = cmds.group(em=True, name="AI_Environment_Grp")
        obj_idx = self.obj_type.currentIndex()
        
        # Get terrain geometry for snapping
        selection_list = om.MSelectionList()
        selection_list.add(terrain_mesh)
        dag_path = selection_list.getDagPath(0)
        mesh_intersector = om.MMeshIntersector()
        mesh_intersector.create(dag_path.node(), om.MMatrix())
        
        # Batch create
        for i in range(count):
            x = random.uniform(-size/2, size/2)
            z = random.uniform(-size/2, size/2)
            
            # Create object based on type
            if obj_idx == 0:
                obj = cmds.polyCylinder(r=0.5, h=3, name=f"Tree_{i}")[0]
                cmds.move(0, 1.5, 0, f"{obj}.vtx[*]", relative=True) # Move pivot to base
            elif obj_idx == 1:
                obj = cmds.polyCube(w=random.uniform(1, 3), h=random.uniform(1, 4), d=random.uniform(1, 3), name=f"Rock_{i}")[0]
            else:
                obj = cmds.polySphere(r=random.uniform(0.5, 2.5), name=f"Boulder_{i}")[0]
                
            # Find Y position using OpenMaya Raycast
            ray_source = om.MFloatPoint(x, max_height + 100, z)
            ray_direction = om.MFloatVector(0, -1, 0)
            
            # Simple intersection check
            try:
                # Fallback to closest point since true raycast requires MFnMesh.closestIntersection which is complex in Python
                pt = om.MPoint(x, max_height, z)
                point_on_mesh = mesh_intersector.getClosestPoint(pt)
                intersect_y = point_on_mesh.point.y
                
                cmds.move(x, intersect_y, z, obj, absolute=True)
                cmds.parent(obj, grp)
                
                # Random rotation
                cmds.rotate(0, random.uniform(0, 360), 0, obj)
            except Exception as e:
                print(f"Failed to place object: {e}")
                cmds.delete(obj)

def run_tool():
    # Attempt to close existing window
    top_widgets = QtWidgets.QApplication.topLevelWidgets()
    maya_window = None
    for widget in top_widgets:
        if widget.objectName() == 'MayaWindow':
            maya_window = widget
        if widget.windowTitle() == "AI Terrain & Environment Generator - Pro":
            widget.close()
            widget.deleteLater()
            
    # Launch new window
    global ai_terrain_ui
    ai_terrain_ui = AITerrainGeneratorUI(parent=maya_window)
    ai_terrain_ui.show()

if __name__ == "__main__":
    run_tool()