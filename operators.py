import bpy
import numpy as np
from . import algo
from . import presets

class THREEBODY_OT_bake_simulation(bpy.types.Operator):
    """Bake the preset simulation to keyframes"""
    bl_idname = "three_body.bake_simulation"
    bl_label = "Bake Simulation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.three_body_props
        scene = context.scene
        
        # 1. Prepare Data (Initial State)
        preset_key = props.simulation_model
        p = presets.PRESETS.get(preset_key)
        
        # Gather initial state from UI properties (this supports custom edits)
        masses = np.array([props.body1.mass, props.body2.mass, props.body3.mass])
        curr_p = np.array([
            list(props.body1.initial_location),
            list(props.body2.initial_location),
            list(props.body3.initial_location)
        ])
        curr_v = np.array([
            list(props.body1.velocity),
            list(props.body2.velocity),
            list(props.body3.velocity)
        ])
        
        # Base physics parameters
        if p:
            G_base = p.G
            soft_base = p.softening
        else:
            # Fallback if in CUSTOM mode
            G_base = 1.0
            soft_base = 0.02

        G = G_base * (props.simulation_scale ** 3)
        softening = soft_base * props.simulation_scale * props.softening_multiplier
        
        # 2. Collision Logic & Individual Radius Calculation
        collision_radii = None
        if props.use_collision:
            radii_list = []
            for b_id in range(1, 4):
                body_prop = getattr(props, f"body{b_id}")
                obj = body_prop.obj
                
                r = 0.0
                if props.auto_collision_radius and obj and obj.type == 'MESH':
                    verts = [v.co.length for v in obj.data.vertices]
                    if verts:
                        max_r = max(verts)
                        avg_r = sum(verts) / len(verts)
                        r = ((max_r + avg_r) / 2.0) * obj.scale[0]
                else:
                    r = props.manual_collision_radius / 2.0 
                
                r += (props.radius_offset / 2.0)
                radii_list.append(max(r, 0.001))
            
            collision_radii = np.array(radii_list)
        
        # 3. Get Target Objects
        bodies = []
        for i in range(1, 4):
            b = getattr(props, f"body{i}")
            if not b.obj:
                self.report({'ERROR'}, f"Body {i} object not set!")
                return {'CANCELLED'}
            bodies.append(b.obj)

        # Time step logic
        fps = scene.render.fps if props.use_scene_fps else props.fps_override
        dt_frame = (1.0 / fps) * props.time_scale
        
        # 3. Bake process
        start_f = props.frame_start
        end_f = props.frame_end
        
        for frame in range(start_f, end_f + 1):
            # Record current pos
            for i, obj in enumerate(bodies):
                obj.location = curr_p[i]
                obj.keyframe_insert(data_path="location", frame=frame)
            
            # Use adaptive step for high stability (especially for chaotic/close encounters)
            curr_p, curr_v = algo.rk45_adaptive_step(curr_p, curr_v, masses, dt_frame, G, softening, collision_radii)

        self.report({'INFO'}, f"Bake completed using {p.name if p else 'Custom'} preset")
        return {'FINISHED'}

class THREEBODY_OT_setup_objects(bpy.types.Operator):
    """Create three UV spheres and assign them to the simulation slots"""
    bl_idname = "three_body.setup_objects"
    bl_label = "Setup Objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.three_body_props
        
        # Positions for the spheres (slight offset to avoid overlapping)
        offsets = [(-5.0, 0.0, 0.0), (0.0, 0.0, 0.0), (5.0, 0.0, 0.0)]
        names = ["Body_1", "Body_2", "Body_3"]
        
        for i in range(3):
            # Create UV Sphere
            bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=offsets[i])
            obj = context.active_object
            obj.name = names[i]
            
            # Assign to the property
            body_prop = getattr(props, f"body{i+1}")
            body_prop.obj = obj
            
            # Sync the initial location property to the new object location
            body_prop.initial_location = obj.location
            
        self.report({'INFO'}, "Three spheres created and assigned.")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(THREEBODY_OT_bake_simulation)
    bpy.utils.register_class(THREEBODY_OT_setup_objects)

def unregister():
    bpy.utils.unregister_class(THREEBODY_OT_bake_simulation)
    bpy.utils.unregister_class(THREEBODY_OT_setup_objects)
