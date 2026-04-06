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
        
        # 1. Prepare Preset Data
        preset_key = props.simulation_model
        if preset_key not in presets.PRESETS:
            self.report({'ERROR'}, f"Preset {preset_key} not found!")
            return {'CANCELLED'}
            
        p = presets.PRESETS[preset_key]
        masses = p.masses
        # Apply Simulation Scale to positions
        curr_p = p.positions.copy() * props.simulation_scale
        curr_v = p.velocities.copy()
        
        # Note: In gravitational physics, if we scale distance R by 'S', 
        # to keep the orbit the same shape, we'd need to adjust G or V.
        # However, for visual purposes in Blender, we often just want
        # the whole movement to be "bigger" in the viewport.
        # To keep the curves identical but larger, we scale G appropriately:
        G = p.G * (props.simulation_scale ** 3)
        
        # Apply softening and the user's multiplier
        # (Softening also needs to scale with Simulation Scale)
        softening = p.softening * props.simulation_scale * props.softening_multiplier
        
        # 2. Collision Logic & Radius Calculation
        collision_dist = 0.0
        if props.use_collision:
            if props.auto_collision_radius:
                # Calculate average distance from origin for each mesh
                radii = []
                for b_id in range(1, 4):
                    obj = getattr(props, f"body{b_id}").obj
                    if obj and obj.type == 'MESH':
                        # Get vertex distances from object center
                        verts = [v.co.length for v in obj.data.vertices]
                        if verts:
                            avg_r = sum(verts) / len(verts)
                            radii.append(avg_r)
                
                if len(radii) >= 2:
                    # Sum of average radii of two bodies
                    # (Simplified: using the average of all bodies' radii * 2)
                    collision_dist = (sum(radii) / len(radii)) * 2
            else:
                collision_dist = props.manual_collision_radius
            
            # Apply fine-tuning offset
            collision_dist += props.radius_offset
        
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
            curr_p, curr_v = algo.rk45_adaptive_step(curr_p, curr_v, masses, dt_frame, G, softening, collision_dist)

        self.report({'INFO'}, f"Bake completed using {p.name} preset (Collision: {'ON' if props.use_collision else 'OFF'})")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(THREEBODY_OT_bake_simulation)

def unregister():
    bpy.utils.unregister_class(THREEBODY_OT_bake_simulation)
