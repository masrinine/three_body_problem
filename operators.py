import bpy

from . import algo, bake, keyframes


class THREEBODY_OT_bake_simulation(bpy.types.Operator):
    """Bake the simulation to location keyframes"""
    bl_idname = "three_body.bake_simulation"
    bl_label = "Bake Simulation"
    bl_options = {'REGISTER', 'UNDO'}

    # Process several frames per timer tick to keep the UI responsive without
    # freezing on very large frame ranges.
    CHUNK_FRAMES = 4

    _timer = None
    _context = None
    _frames = None
    _last_state = None
    _error = None
    _cancelled = False
    _finished = False

    def modal(self, context, event):
        if self._finished:
            return {'FINISHED'}

        if event.type in {'ESC'}:
            self._cancelled = True
            self._finish(context, status="CANCELLED")
            self.report({'INFO'}, "Bake cancelled by user")
            return {'CANCELLED'}

        if event.type == 'TIMER':
            try:
                done = self._step_chunk(context)
            except algo.SimulationError as exc:
                self._error = str(exc)
                self._finish(context, status="ABORTED")
                self.report({'ERROR'}, f"Physics error: {self._error}")
                return {'CANCELLED'}

            if done:
                self._finish(context, status="COMPLETED")
                self.report({'INFO'}, "Bake completed")
                return {'FINISHED'}
            return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}

    def _step_chunk(self, context):
        """Insert up to CHUNK_FRAMES frames. Returns True when finished."""
        for _ in range(self.CHUNK_FRAMES):
            try:
                state = next(self._frames)
            except StopIteration:
                return True
            bake.apply_frame(self._context.objects, state)
            self._last_state = state

        frame = self._last_state.frame if self._last_state else self._context.start_frame
        context.window_manager.progress_update(frame)
        return False

    def execute(self, context):
        props = context.scene.three_body_props

        try:
            self._context = bake.build_context(context)
        except bake.BakeValidationError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        props.is_baking = True
        self._cancelled = False
        self._finished = False
        self._error = None
        self._last_state = None
        self._frames = bake.simulate(self._context, cancel=lambda: self._cancelled)

        try:
            context.window_manager.progress_begin(
                self._context.start_frame, self._context.end_frame
            )
            self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
            context.window_manager.modal_handler_add(self)
        except Exception:
            props.is_baking = False
            raise
        return {'RUNNING_MODAL'}

    def _finish(self, context, status):
        if self._finished:
            return
        self._finished = True

        if self._timer is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except (RuntimeError, ReferenceError):
                pass
            self._timer = None

        try:
            context.window_manager.progress_end()
        except RuntimeError:
            pass

        props = context.scene.three_body_props
        props.is_baking = False
        if self._context is not None:
            bake.finalize(self._context, self._last_state, status=status, error=self._error)

    def cancel(self, context):
        self._cancelled = True
        self._finish(context, status="CANCELLED")


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
    """Remove location keyframes from the simulation objects"""
    bl_idname = "three_body.unbake_simulation"
    bl_label = "Unbake Simulation"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = context.scene.three_body_props
        if props.is_baked:
            return True
        return any(body.obj and body.obj.animation_data for body in props.bodies)

    def execute(self, context):
        props = context.scene.three_body_props

        objects_cleared = 0
        for body in props.bodies:
            if not body.obj:
                continue
            if keyframes.remove_location_fcurves(body.obj):
                objects_cleared += 1
            body.obj.location = body.initial_location

        props.is_baked = False
        props.energy_drift = 0.0
        if objects_cleared:
            props.last_simulation_report = (
                f"Unbaked. Removed location keys from {objects_cleared} objects."
            )
        else:
            props.last_simulation_report = "Unbaked. No location keys were found."

        self.report({'INFO'}, f"Cleared keyframes for {objects_cleared} objects.")
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
