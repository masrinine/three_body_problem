import bpy
import numpy as np
from . import algo

class THREEBODY_OT_set_initial_state(bpy.types.Operator):
    """Set the current object locations as start positions"""
    bl_idname = "three_body.set_initial_state"
    bl_label = "Set Current as Initial"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.three_body_props
        for i in range(1, 4):
            body_prop = getattr(props, f"body{i}")
            if body_prop.obj:
                body_prop.initial_location = body_prop.obj.location
        return {'FINISHED'}

class THREEBODY_OT_reset_to_initial(bpy.types.Operator):
    """Reset objects to their initial positions and clear keyframes"""
    bl_idname = "three_body.reset_to_initial"
    bl_label = "Reset to Initial State"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.three_body_props
        for i in range(1, 4):
            body_prop = getattr(props, f"body{i}")
            if body_prop.obj:
                body_prop.obj.location = body_prop.initial_location
                # Clear existing keyframes in the simulation range
                if body_prop.obj.animation_data and body_prop.obj.animation_data.action:
                    fcurves = body_prop.obj.animation_data.action.fcurves
                    for fcu in fcurves:
                        if fcu.data_path == "location":
                            # Keyframes are removed by index, so we iterate backwards
                            keys = fcu.keyframe_points
                            for ki in range(len(keys)-1, -1, -1):
                                if props.frame_start <= keys[ki].co[0] <= props.frame_end:
                                    keys.remove(keys[ki])
        return {'FINISHED'}

class THREEBODY_OT_bake_simulation(bpy.types.Operator):
    """Bake the three-body simulation to keyframes"""
    bl_idname = "three_body.bake_simulation"
    bl_label = "Bake Simulation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.three_body_props
        scene = context.scene
        
        # Sync current object locations to initial_location before calculation
        for i in range(1, 4):
            body_prop = getattr(props, f"body{i}")
            if body_prop.obj:
                body_prop.initial_location = body_prop.obj.location

        # 1. Prepare data
        bodies = []
        for i in range(1, 4):
            b = getattr(props, f"body{i}")
            if not b.obj:
                self.report({'ERROR'}, f"Body {i} object not set!")
                return {'CANCELLED'}
            bodies.append(b)
            
        masses = np.array([b.mass for b in bodies])
        positions = np.array([b.initial_location for b in bodies])
        velocities = np.array([b.velocity for b in bodies])
        G = props.gravitational_constant
        
        # Determine time step
        fps = scene.render.fps if props.use_scene_fps else props.fps_override
        dt_frame = (1.0 / fps) * props.time_scale
        
        # 2. Run simulation and set keyframes
        curr_p = positions.copy()
        curr_v = velocities.copy()
        
        start_f = props.frame_start
        end_f = props.frame_end
        
        for frame in range(start_f, end_f + 1):
            # Set location
            for i, b in enumerate(bodies):
                b.obj.location = curr_p[i]
                b.obj.keyframe_insert(data_path="location", frame=frame)
            
            # Progress simulation one frame step
            if props.simulation_model == 'RK4':
                curr_p, curr_v = algo.rk4_step(curr_p, curr_v, masses, dt_frame, G)
            elif props.simulation_model == 'VERLET':
                curr_p, curr_v = algo.velocity_verlet_step(curr_p, curr_v, masses, dt_frame, G)
            elif props.simulation_model == 'RK45':
                # Custom adaptive logic inside algo.py would need to return result
                # For now let's ensure algo.py rk45 returns values
                curr_p, curr_v = algo.rk45_adaptive_step(curr_p, curr_v, masses, dt_frame, G)

        self.report({'INFO'}, f"Bake completed from frame {start_f} to {end_f}")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(THREEBODY_OT_set_initial_state)
    bpy.utils.register_class(THREEBODY_OT_reset_to_initial)
    bpy.utils.register_class(THREEBODY_OT_bake_simulation)

def unregister():
    bpy.utils.unregister_class(THREEBODY_OT_bake_simulation)
    bpy.utils.unregister_class(THREEBODY_OT_reset_to_initial)
    bpy.utils.unregister_class(THREEBODY_OT_set_initial_state)
