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
        # F = G*m1*m2/R^2. If R -> R*S, then F -> F/S^2.
        # But we want the same acceleration 'a' relative to the new scale.
        # If we want the same orbital period, a must scale with S (a -> a*S).
        # So G must scale by S^3. G_scaled = G * S^3.
        G = p.G * (props.simulation_scale ** 3)
        
        softening = p.softening * props.simulation_scale
        steps_per_frame = p.steps_per_frame
        
        # 2. Get Target Objects
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
        dt_substep = dt_frame / steps_per_frame
        
        # 3. Bake process
        start_f = props.frame_start
        end_f = props.frame_end
        
        for frame in range(start_f, end_f + 1):
            # Record current pos
            for i, obj in enumerate(bodies):
                obj.location = curr_p[i]
                obj.keyframe_insert(data_path="location", frame=frame)
            
            # Progress with optimized steps for this preset
            for _ in range(steps_per_frame):
                curr_p, curr_v = algo.rk4_step(curr_p, curr_v, masses, dt_substep, G, softening)

        self.report({'INFO'}, f"Bake completed using {p.name} preset")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(THREEBODY_OT_bake_simulation)

def unregister():
    bpy.utils.unregister_class(THREEBODY_OT_bake_simulation)
