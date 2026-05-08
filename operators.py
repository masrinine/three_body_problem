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
            if props.integrator_type == 'LEAPFROG':
                # Leapfrog fixed substepping
                dt_sub = self._dt_frame / self._substeps
                for _ in range(self._substeps):
                    self._curr_p, self._curr_v = algo.leapfrog_step(
                        self._curr_p, self._curr_v, self._masses, dt_sub,
                        self._G, self._softening, self._collision_radii
                    )
            else:
                # Default RK45 Adaptive
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

        # Update energy drift
        from .algo import calculate_total_energy
        current_energy = calculate_total_energy(self._curr_p, self._curr_v, self._masses, self._G, self._softening)
        # Hamiltonian drift: abs((E_curr - E_init) / E_init)
        if abs(self._initial_energy) > 1e-10:
            drift = abs((current_energy - self._initial_energy) / self._initial_energy)
        else:
            drift = abs(current_energy - self._initial_energy)
        
        self._max_drift = max(self._max_drift, drift)

    def _get_stats_str(self):
        return f"Max Speed: {self._stats['max_speed']:.2f}. Min Dist: {self._stats['min_dist']:.2f}. Efficiency: {(1.0 - self._max_drift)*100:.2f}%."

    def execute(self, context):
        props = context.scene.three_body_props
        scene = context.scene
            
        # Initialization
        self._start_f = props.frame_start
        self._end_f = props.frame_end
        self._frame = self._start_f
        self._error = None
        
        if (self._end_f - self._start_f) > 100000:
            self.report({'ERROR'}, "Frame range too large!")
            return {'CANCELLED'}

        # --- Phase 2: Input Validation Guard ---
        if not props.bodies:
            self.report({'ERROR'}, "No celestial bodies defined")
            return {'CANCELLED'}
            
        for i, b in enumerate(props.bodies):
            if b.mass <= 0:
                self.report({'ERROR'}, f"Body {i+1} has invalid mass (must be > 0)")
                return {'CANCELLED'}
            if np.any(np.isnan(b.initial_location)) or np.any(np.isinf(b.initial_location)):
                self.report({'ERROR'}, f"Body {i+1} has invalid location")
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

        # --- Phase 1: Spatial Normalization ---
        # 物理学的な整合性: 距離を S 倍にスケールアップした場合、
        # 同じ時間経過で同じ軌道を描くためには G を S^3 倍にする必要があります (ケプラーの第3法則に関連)
        # これにより Simulation Scale を変えても「速さ」の印象が一定に保たれます。
        S = props.simulation_scale
        self._G = G_base * (S ** 3) * props.gravity_strength
        self._softening = soft_base * S * props.softening_multiplier
        
        # 速度もシミュレーション空間（S倍された空間）に合わせてスケーリング
        self._curr_v = self._curr_v * S
        
        # --- Energy Tracking Initialization ---
        from .algo import calculate_total_energy
        self._initial_energy = calculate_total_energy(self._curr_p, self._curr_v, self._masses, self._G, self._softening)
        self._last_energy = self._initial_energy
        self._max_drift = 0.0

        # Collision
        self._collision_radii = None
        if props.use_collision:
            radii = []
            for b in props.bodies:
                r = 0.5
                if props.auto_collision_radius and b.obj and b.obj.type == 'MESH':
                    if hasattr(b.obj.data, "vertices") and len(b.obj.data.vertices) > 0:
                        # オブジェクトのスケールと行列を考慮した正確なワールド半径の計算
                        # 最大頂点距離にオブジェクトのスケールを掛けて、現在の空間スケール(S)に合わせる
                        r = (max([v.co.length for v in b.obj.data.vertices])) * b.obj.scale[0]
                else:
                    r = props.manual_collision_radius / 2.0
                
                # ワールド空間での半径をシミュレーション空間(S倍)のスケールに正規化
                scaled_r = max(r + props.radius_offset/2.0, 0.001)
                radii.append(scaled_r)
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
        props.is_baked = True
        props.energy_drift = self._max_drift
        
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
        return None

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
            body_prop.is_expanded = False
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
        
        props.is_baked = False
        props.energy_drift = 0.0
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

class THREEBODY_OT_sync_collection(bpy.types.Operator):
    """Sync body slots from the selected collection"""
    bl_idname = "three_body.sync_collection"
    bl_label = "Sync from Collection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.three_body_props
        collection = props.sync_collection
        
        if not collection:
            self.report({'ERROR'}, "No collection selected for sync.")
            return {'CANCELLED'}
        
        # Filter for mesh objects in collection
        objects = [obj for obj in collection.objects if obj.type == 'MESH']
        
        if not objects:
            self.report({'WARNING'}, f"No mesh objects found in collection: {collection.name}")
            return {'CANCELLED'}
            
        # Clear existing slots or just append? 
        # Typically sync means "make the list match"
        props.bodies.clear()
        
        for obj in objects:
            body = props.bodies.add()
            body.obj = obj
            body.is_expanded = False
            # Auto-capture current location
            body.initial_location = obj.location
            # Initialize with default mass
            body.mass = 1.0

        self.report({'INFO'}, f"Synced {len(objects)} bodies from '{collection.name}'")
        return {'FINISHED'}

def register():
    classes = (
        THREEBODY_OT_bake_simulation,
        THREEBODY_OT_unbake_simulation,
        THREEBODY_OT_setup_objects,
        THREEBODY_OT_capture_locations,
        THREEBODY_OT_apply_locations,
        THREEBODY_OT_sync_collection,
    )
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass

def unregister():
    classes = (
        THREEBODY_OT_apply_locations,
        THREEBODY_OT_capture_locations,
        THREEBODY_OT_setup_objects,
        THREEBODY_OT_unbake_simulation,
        THREEBODY_OT_bake_simulation,
        THREEBODY_OT_sync_collection,
    )
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
