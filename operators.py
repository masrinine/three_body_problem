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
        
        # Prevent concurrent bakes
        if props.is_baking:
            self.report({'WARNING'}, "Simulation is already baking")
            return {'CANCELLED'}
        props.is_baking = True

        try:
            # 0. Check if there are any bodies
            if not props.bodies:
                self.report({'ERROR'}, "No bodies defined in the simulation!")
                return {'CANCELLED'}
                
            # 1. Prepare Data (Initial State)
            preset_key = props.simulation_model
            p = presets.PRESETS.get(preset_key)
            
            # Gather initial state from UI properties
            num_bodies = len(props.bodies)
            masses = np.array([b.mass for b in props.bodies])
            curr_p = np.array([list(b.initial_location) for b in props.bodies])
            curr_v = np.array([list(b.velocity) for b in props.bodies])
            
            # Base physics parameters
            if p and num_bodies >= 3:
                G_base = p.G
                soft_base = p.softening
                base_substeps = p.steps_per_frame
            else:
                # Fallback for CUSTOM mode or N-body (>3)
                G_base = 1.0
                soft_base = 0.02
                base_substeps = 10

            G = G_base * (props.simulation_scale ** 3) * props.gravity_strength
            softening = soft_base * props.simulation_scale * props.softening_multiplier
            
            # 2. Collision Logic & Individual Radius Calculation
            collision_radii = None
            if props.use_collision:
                radii_list = []
                for b_idx, body_prop in enumerate(props.bodies):
                    obj = body_prop.obj
                    
                    r = 0.0
                    if props.auto_collision_radius and obj and obj.type == 'MESH':
                        # Validating geometry existence
                        if hasattr(obj.data, "vertices") and len(obj.data.vertices) > 0:
                            verts = [v.co.length for v in obj.data.vertices]
                            max_r = max(verts)
                            avg_r = sum(verts) / len(verts)
                            r = ((max_r + avg_r) / 2.0) * obj.scale[0]
                        else:
                            r = 0.5 # Default radius for non-mesh or empty mesh
                    else:
                        r = props.manual_collision_radius / 2.0 
                    
                    r += (props.radius_offset / 2.0)
                    r = max(r, 0.001)
                    body_prop.collision_radius = r # Store for visualization
                    radii_list.append(r)
                
                collision_radii = np.array(radii_list)
            
            # 3. Get Target Objects (Validation)
            from .properties import is_valid_obj
            objs = []
            for i, b in enumerate(props.bodies):
                if not is_valid_obj(b.obj):
                    self.report({'ERROR'}, f"Body {i+1} object is invalid or missing!")
                    props.is_baking = False
                    return {'CANCELLED'}
                objs.append(b.obj)

            # Time step logic
            fps = scene.render.fps if props.use_scene_fps else props.fps_override
            dt_frame = (1.0 / fps) * props.time_scale
            
            # 4. Bake process
            start_f = props.frame_start
            end_f = props.frame_end
            
            # Statistics for report
            max_global_speed = 0.0
            min_global_dist = float('inf')
            
            for frame in range(start_f, end_f + 1):
                # Record current pos
                for i, obj in enumerate(objs):
                    obj.location = curr_p[i]
                    obj.keyframe_insert(data_path="location", frame=frame)
                
                # Stats calculation
                current_speeds = np.linalg.norm(curr_v, axis=1)
                max_global_speed = max(max_global_speed, np.max(current_speeds))
                
                if num_bodies > 1:
                    # Compute distance matrix
                    diff = curr_p[:, np.newaxis, :] - curr_p[np.newaxis, :, :]
                    dists = np.linalg.norm(diff, axis=-1)
                    # Exclude self-distance (0)
                    np.fill_diagonal(dists, float('inf'))
                    min_global_dist = min(min_global_dist, np.min(dists))

                # Use adaptive step for high stability with safety limits
                try:
                    curr_p, curr_v = algo.rk45_adaptive_step(
                        curr_p,
                        curr_v,
                        masses,
                        dt_frame,
                        G,
                        softening,
                        collision_radii,
                        base_substeps=base_substeps,
                        timeout_s=props.bake_limit_seconds,
                        max_v_safety=props.max_velocity_safety
                    )
                except algo.SimulationError as e:
                    self.report({'ERROR'}, f"Simulation Aborted at frame {frame}: {str(e)}")
                    props.last_simulation_report = (
                        f"ABORTED at frame {frame}. "
                        f"Max Speed: {max_global_speed:.2f}. "
                        f"Min Dist: {min_global_dist:.2f}. "
                        f"Error: {str(e)}"
                    )
                    break
            else:
                # Normal completion
                props.last_simulation_report = (
                    f"COMPLETED. Bodies: {num_bodies}. "
                    f"Frames: {end_f - start_f + 1}. "
                    f"Max Speed: {max_global_speed:.2f}. "
                    f"Min Dist: {min_global_dist:.2f}."
                )

            self.report({'INFO'}, f"Bake completed ({num_bodies} bodies)")
            return {'FINISHED'}
            
        finally:
            props.is_baking = False

class THREEBODY_OT_setup_objects(bpy.types.Operator):
    """Create UV spheres and assign them to the simulation slots, clearing existing ones first"""
    bl_idname = "three_body.setup_objects"
    bl_label = "Setup Objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.three_body_props
        
        # 1. 既存のシミュレーションスロットと関連オブジェクトを一度クリアしてリセット
        # これにより、増減時の不整合（古い名前のオブジェクトが残る等）を防止
        props.bodies.clear()
        
        count = props.setup_body_count
        
        # アルゴリズム: 原点(0)を中心に、X軸上の正・負方向へ交互に5m間隔で配置
        for i in range(count):
            if i == 0:
                x_pos = 0.0
            else:
                multiplier = (i + 1) // 2
                x_pos = multiplier * 5.0 if i % 2 == 1 else -multiplier * 5.0
            
            loc = (x_pos, 0.0, 0.0)
            y_vel = 0.1 if i % 2 == 0 else -0.1
            vel = (0.0, y_vel, 0.0)
            
            # Create UV Sphere
            bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=loc)
            obj = context.active_object
            obj.name = f"Body_{i+1}"
            
            # 新しいスロットを追加して割り当て
            body_prop = props.bodies.add()
            body_prop.obj = obj
            body_prop.initial_location = obj.location
            body_prop.velocity = vel
            
        self.report({'INFO'}, f"Reset and created {count} spheres.")
        return {'FINISHED'}

class THREEBODY_OT_unbake_simulation(bpy.types.Operator):
    """Remove all location keyframes from simulation objects"""
    bl_idname = "three_body.unbake_simulation"
    bl_label = "Unbake Simulation"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = context.scene.three_body_props
        # Enable only if at least one body object has animation data
        for body in props.bodies:
            if body.obj and body.obj.animation_data and body.obj.animation_data.action:
                return True
        return False

    def execute(self, context):
        props = context.scene.three_body_props
        
        objects_cleared = 0
        for body in props.bodies:
            if body.obj and body.obj.animation_data:
                action = body.obj.animation_data.action
                if action:
                    try:
                        fcurves = [fc for fc in action.fcurves if fc.data_path == "location"]
                        for fc in fcurves:
                            action.fcurves.remove(fc)
                    except Exception as e:
                        self.report({'WARNING'}, f"Failed to clear keyframes for {body.obj.name}: {str(e)}")
                    
                    if not hasattr(action, 'fcurves') or not action.fcurves:
                        body.obj.animation_data_clear()
                    
                    objects_cleared += 1
                
                # Reset to initial location
                body.obj.location = body.initial_location

        if objects_cleared > 0:
            self.report({'INFO'}, f"Cleared keyframes for {objects_cleared} objects.")
        else:
            self.report({'INFO'}, "No keyframes found to clear.")
            
        return {'FINISHED'}

class THREEBODY_OT_capture_locations(bpy.types.Operator):
    """Store the current viewport locations of objects as their starting positions"""
    bl_idname = "three_body.capture_locations"
    bl_label = "Capture Current Locations"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.three_body_props
        captured = 0
        for body in props.bodies:
            if body.obj:
                body.initial_location = body.obj.location
                captured += 1
        
        self.report({'INFO'}, f"Captured locations for {captured} objects.")
        return {'FINISHED'}

class THREEBODY_OT_apply_locations(bpy.types.Operator):
    """Move objects in the viewport to their defined initial locations"""
    bl_idname = "three_body.apply_locations"
    bl_label = "Apply Start Locations"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.three_body_props
        applied = 0
        for body in props.bodies:
            if body.obj:
                body.obj.location = body.initial_location
                applied += 1
        
        self.report({'INFO'}, f"Moved {applied} objects to start locations.")
        return {'FINISHED'}

class THREEBODY_OT_batch_apply_properties(bpy.types.Operator):
    """Apply batch properties (Mass, Velocity) to all bodies"""
    bl_idname = "three_body.batch_apply_properties"
    bl_label = "Apply Batch"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.three_body_props
        for body in props.bodies:
            body.mass = props.batch_mass
            body.velocity = props.batch_velocity
            
        self.report({'INFO'}, f"Applied batch properties to {len(props.bodies)} bodies.")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(THREEBODY_OT_bake_simulation)
    bpy.utils.register_class(THREEBODY_OT_unbake_simulation)
    bpy.utils.register_class(THREEBODY_OT_setup_objects)
    bpy.utils.register_class(THREEBODY_OT_capture_locations)
    bpy.utils.register_class(THREEBODY_OT_apply_locations)
    bpy.utils.register_class(THREEBODY_OT_batch_apply_properties)

def unregister():
    bpy.utils.unregister_class(THREEBODY_OT_bake_simulation)
    bpy.utils.unregister_class(THREEBODY_OT_unbake_simulation)
    bpy.utils.unregister_class(THREEBODY_OT_setup_objects)
    bpy.utils.unregister_class(THREEBODY_OT_capture_locations)
    bpy.utils.unregister_class(THREEBODY_OT_apply_locations)
    bpy.utils.unregister_class(THREEBODY_OT_batch_apply_properties)
