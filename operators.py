import bpy
import numpy as np
from . import algo
from . import presets

class THREEBODY_OT_bake_simulation(bpy.types.Operator):
    """Bake the preset simulation to keyframes with cancellation support"""
    bl_idname = "three_body.bake_simulation"
    bl_label = "Bake Simulation"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    _frame = 0
    _curr_p = None
    _curr_v = None
    _masses = None
    _objs = None
    _collision_radii = None
    _stats = None

    def modal(self, context, event):
        props = context.scene.three_body_props
        
        if event.type in {'ESC'}:
            self.cancel(context)
            self.report({'INFO'}, "Bake Cancelled by user")
            props.last_simulation_report = f"CANCELLED at frame {self._frame}. " + self._get_stats_str()
            return {'CANCELLED'}

        if event.type == 'TIMER':
            # Run one frame or a small chunk here
            # For responsiveness, we do 1 frame per timer tick
            if self._frame <= self._end_f:
                self._step_simulation(context)
                self._frame += 1
                context.window_manager.progress_update(self._frame)
                return {'RUNNING_MODAL'}
            else:
                self.finish(context)
                return {'FINISHED'}

        return {'PASS_THROUGH'}

    def _step_simulation(self, context):
        props = context.scene.three_body_props
        
        # Record
        for i, obj in enumerate(self._objs):
            obj.location = self._curr_p[i]
            obj.keyframe_insert(data_path="location", frame=self._frame)
        
        # Stats
        current_speeds = np.linalg.norm(self._curr_v, axis=1)
        self._stats['max_speed'] = max(self._stats['max_speed'], np.max(current_speeds))
        
        if len(self._objs) > 1:
            diff = self._curr_p[:, np.newaxis, :] - self._curr_p[np.newaxis, :, :]
            dists = np.linalg.norm(diff, axis=-1)
            np.fill_diagonal(dists, float('inf'))
            self._stats['min_dist'] = min(self._stats['min_dist'], np.min(dists))

        # Physics
        try:
            self._curr_p, self._curr_v = algo.rk45_adaptive_step(
                self._curr_p, self._curr_v, self._masses, self._dt_frame,
                self._G, self._softening, self._collision_radii,
                base_substeps=self._substeps,
                timeout_s=props.bake_limit_seconds,
                max_v_safety=props.max_velocity_safety
            )
        except algo.SimulationError as e:
            self.report({'ERROR'}, f"Physics Error: {str(e)}")
            self._error = str(e)
            self._frame = self._end_f + 1 # Force end

    def _get_stats_str(self):
        return f"Max Speed: {self._stats['max_speed']:.2f}. Min Dist: {self._stats['min_dist']:.2f}."

    def execute(self, context):
        props = context.scene.three_body_props
        scene = context.scene

        if props.is_baking:
            return {'CANCELLED'}
            
        # Initialization
        self._start_f = props.frame_start
        self._end_f = props.frame_end
        self._frame = self._start_f
        self._error = None
        
        if (self._end_f - self._start_f) > 100000:
            self.report({'ERROR'}, "Frame range too large!")
            return {'CANCELLED'}

        # Prepare physics data
        preset_key = props.simulation_model
        p = presets.PRESETS.get(preset_key)
        num_bodies = len(props.bodies)
        
        self._masses = np.array([b.mass for b in props.bodies])
        self._curr_p = np.array([list(b.initial_location) for b in props.bodies])
        self._curr_v = np.array([list(b.velocity) for b in props.bodies])
        
        if p and num_bodies >= 3:
            G_base, soft_base, self._substeps = p.G, p.softening, p.steps_per_frame
        else:
            G_base, soft_base, self._substeps = 1.0, 0.02, 10

        self._G = G_base * (props.simulation_scale ** 3) * props.gravity_strength
        self._softening = soft_base * props.simulation_scale * props.softening_multiplier
        
        # Collision
        self._collision_radii = None
        if props.use_collision:
            radii = []
            for b in props.bodies:
                r = 0.5
                if props.auto_collision_radius and b.obj and b.obj.type == 'MESH':
                    if hasattr(b.obj.data, "vertices") and len(b.obj.data.vertices) > 0:
                        r = (max([v.co.length for v in b.obj.data.vertices])) * b.obj.scale[0]
                else:
                    r = props.manual_collision_radius / 2.0
                radii.append(max(r + props.radius_offset/2.0, 0.001))
            self._collision_radii = np.array(radii)

        from .properties import is_valid_obj
        self._objs = []
        for b in props.bodies:
            if not is_valid_obj(b.obj):
                self.report({'ERROR'}, "Invalid object in list")
                return {'CANCELLED'}
            self._objs.append(b.obj)

        fps = scene.render.fps if props.use_scene_fps else props.fps_override
        self._dt_frame = (1.0 / fps) * props.time_scale
        self._stats = {'max_speed': 0.0, 'min_dist': float('inf')}

        props.is_baking = True
        context.window_manager.progress_begin(self._start_f, self._end_f)
        
        # Start modal loop
        self._timer = context.window_manager.event_timer_add(0.001, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def finish(self, context):
        props = context.scene.three_body_props
        context.window_manager.event_timer_remove(self._timer)
        context.window_manager.progress_end()
        props.is_baking = False
        
        if self._error:
            props.last_simulation_report = f"ABORTED. {self._get_stats_str()} Error: {self._error}"
        else:
            props.last_simulation_report = f"COMPLETED. {self._get_stats_str()}"
        self.report({'INFO'}, "Bake Completed")

    def cancel(self, context):
        props = context.scene.three_body_props
        context.window_manager.event_timer_remove(self._timer)
        context.window_manager.progress_end()
        props.is_baking = False

class THREEBODY_OT_setup_objects(bpy.types.Operator):
    """Create UV spheres and assign them to the simulation slots, clearing existing ones first"""
    bl_idname = "three_body.setup_objects"
    bl_label = "Setup Objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.three_body_props
        
        # 不要な削除を避け、リストをクリアするだけに留める
        # (ユーザーが配置したオブジェクトを破壊しないため)
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

def register():
    bpy.utils.register_class(THREEBODY_OT_bake_simulation)
    bpy.utils.register_class(THREEBODY_OT_unbake_simulation)
    bpy.utils.register_class(THREEBODY_OT_setup_objects)
    bpy.utils.register_class(THREEBODY_OT_capture_locations)
    bpy.utils.register_class(THREEBODY_OT_apply_locations)

def unregister():
    bpy.utils.unregister_class(THREEBODY_OT_bake_simulation)
    bpy.utils.unregister_class(THREEBODY_OT_unbake_simulation)
    bpy.utils.unregister_class(THREEBODY_OT_setup_objects)
    bpy.utils.unregister_class(THREEBODY_OT_capture_locations)
    bpy.utils.unregister_class(THREEBODY_OT_apply_locations)
