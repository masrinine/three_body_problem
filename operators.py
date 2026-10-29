import bmesh
import bpy

from . import algo, bake, keyframes, presets
from .properties import (
    apply_preset_to_bodies,
    is_valid_obj,
    reset_simulation_settings,
)


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


class THREEBODY_OT_apply_preset(bpy.types.Operator):
    """Apply the selected preset to the three bodies"""

    bl_idname = "three_body.apply_preset"
    bl_label = "Apply Preset"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = context.scene.three_body_props
        if props.is_baking or props.is_baked:
            return False
        if props.simulation_model == 'CUSTOM':
            return False
        if len(props.bodies) != 3:
            return False
        return all(is_valid_obj(body.obj) for body in props.bodies)

    def execute(self, context):
        props = context.scene.three_body_props
        preset = presets.PRESETS.get(props.simulation_model)
        if preset is None:
            self.report({'ERROR'}, "Select a preset before applying it.")
            return {'CANCELLED'}
        if not apply_preset_to_bodies(props, props.simulation_model):
            self.report(
                {'ERROR'},
                "Applying a preset requires exactly 3 bodies with objects.",
            )
            return {'CANCELLED'}
        self.report({'INFO'}, f"Applied preset: {preset.name}")
        return {'FINISHED'}


class THREEBODY_OT_reset_settings(bpy.types.Operator):
    """Reset simulation and display settings to defaults (keeps bodies and preset)"""

    bl_idname = "three_body.reset_settings"
    bl_label = "Reset Settings"
    # Resetting changes body scale through the simulation_scale callback; leave
    # this out of the undo stack so scale and _last_simulation_scale cannot get
    # out of sync through a partial undo.
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        # Keep this available for scripts so execute/invoke can explain why a
        # baked scene must be unbaked first; the panel disables the button.
        return getattr(context.scene, "three_body_props", None) is not None

    def invoke(self, context, event):
        props = context.scene.three_body_props
        if props.is_baking or props.is_baked:
            self.report({'ERROR'}, "Unbake before resetting settings.")
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=380)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Reset all simulation and display settings?", icon='QUESTION')
        col.label(text="Bodies, their objects, and the selected preset are kept.")
        col.label(text="This cannot be undone.")

    def execute(self, context):
        props = context.scene.three_body_props
        if props.is_baking or props.is_baked:
            self.report({'ERROR'}, "Unbake before resetting settings.")
            return {'CANCELLED'}

        reset_simulation_settings(props)
        self.report(
            {'INFO'},
            "Simulation settings reset to defaults (bodies and preset kept).",
        )
        return {'FINISHED'}


DEMO_SCENE_NAME = "Three Body Demo"
DEMO_BODY_COLORS = (
    ("Body_1", (1.0, 0.30, 0.10)),
    ("Body_2", (0.15, 0.45, 1.0)),
    ("Body_3", (0.10, 0.85, 0.55)),
)


def _demo_material(name, color, *, roughness=0.35, metallic=0.0, emission=0.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (*color, 1.0)
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        rgba = (*color, 1.0)
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if emission > 0.0:
            emission_color = bsdf.inputs.get("Emission Color")
            if emission_color is not None:
                emission_color.default_value = rgba
            emission_strength = bsdf.inputs.get("Emission Strength")
            if emission_strength is not None:
                emission_strength.default_value = emission
    return material


def _demo_sphere_mesh(name, radius=1.0, segments=48, rings=24):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    try:
        bmesh.ops.create_uvsphere(
            bm, u_segments=segments, v_segments=rings, radius=radius
        )
        bm.to_mesh(mesh)
    finally:
        bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return mesh


def _demo_plane_mesh(name, size=100.0):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    try:
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size)
        bm.to_mesh(mesh)
    finally:
        bm.free()
    return mesh


def _link_demo_object(scene, name, data):
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    return obj


def _aim_at_origin(obj):
    obj.rotation_euler = (-obj.location).to_track_quat('-Z', 'Y').to_euler()


def _populate_demo_scene(scene):
    """Fill a fresh scene with a playable, self-contained Figure-8 setup."""
    props = scene.three_body_props
    # Assigning body.obj below flips the model to CUSTOM. Start there so the
    # flow is deterministic, then apply the preset explicitly.
    props.simulation_model = 'CUSTOM'
    props.setup_body_count = 3
    props.simulation_scale = 5.0
    props["_last_simulation_scale"] = 5.0
    props.frame_start = 1
    props.frame_end = 250
    props.use_scene_fps = True
    # Keep the pre-baked demo clean; users can switch the arrows back on.
    props.show_velocity_vectors = False

    for name, color in DEMO_BODY_COLORS:
        mesh = _demo_sphere_mesh(f"{name} Mesh")
        obj = _link_demo_object(scene, name, mesh)
        obj.data.materials.append(
            _demo_material(f"{name} Material", color, emission=0.25)
        )
        body = props.bodies.add()
        body.obj = obj
        body.mass = 1.0
        body.initial_location = (0.0, 0.0, 0.0)
        body.velocity = (0.0, 0.0, 0.0)

    if not apply_preset_to_bodies(props, 'FIGURE_8'):
        raise RuntimeError("Could not apply the Figure-8 preset.")
    # The enum is CUSTOM after the assignments above; this re-applies the
    # preset (idempotent) and makes the sidebar show Figure-8.
    props.simulation_model = 'FIGURE_8'

    backdrop = _link_demo_object(
        scene, "Demo Backdrop", _demo_plane_mesh("Demo Backdrop Mesh")
    )
    backdrop.location = (0.0, 0.0, -3.0)
    backdrop.data.materials.append(
        _demo_material(
            "Demo Backdrop Material",
            (0.012, 0.014, 0.022),
            roughness=0.75,
        )
    )

    camera_data = bpy.data.cameras.new("Demo Camera")
    camera = _link_demo_object(scene, "Demo Camera", camera_data)
    camera.location = (0.0, -32.0, 18.0)
    _aim_at_origin(camera)
    camera.data.lens = 50.0
    scene.camera = camera

    sun_data = bpy.data.lights.new("Demo Sun", 'SUN')
    sun_data.energy = 3.0
    sun_data.angle = 0.15
    sun_data.color = (1.0, 0.94, 0.86)
    sun = _link_demo_object(scene, "Demo Sun", sun_data)
    sun.location = (5.0, -6.0, 12.0)
    _aim_at_origin(sun)

    fill_data = bpy.data.lights.new("Demo Fill", 'AREA')
    fill_data.energy = 500.0
    fill_data.size = 10.0
    fill_data.color = (0.45, 0.62, 1.0)
    fill = _link_demo_object(scene, "Demo Fill", fill_data)
    fill.location = (-8.0, -6.0, 7.0)
    _aim_at_origin(fill)

    rim_data = bpy.data.lights.new("Demo Rim", 'AREA')
    rim_data.energy = 350.0
    rim_data.size = 8.0
    rim_data.color = (1.0, 0.55, 0.30)
    rim = _link_demo_object(scene, "Demo Rim", rim_data)
    rim.location = (8.0, 6.0, 8.0)
    _aim_at_origin(rim)

    world = bpy.data.worlds.new("Demo World")
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.004, 0.006, 0.014, 1.0)
        background.inputs["Strength"].default_value = 1.0
    scene.world = world

    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.fps = 24
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.frame_start = 1
    scene.frame_end = 250


class THREEBODY_OT_create_demo_scene(bpy.types.Operator):
    """Create and open a ready-to-play Three Body Demo scene"""

    bl_idname = "three_body.create_demo_scene"
    bl_label = "Create Demo Scene"
    # Creating and switching scenes is not reliably undoable; register without
    # UNDO so the scene selector cannot be left in a half-reverted state.
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        # A modal bake is bound to the active scene; do not switch scenes mid-bake.
        return not context.scene.three_body_props.is_baking

    def execute(self, context):
        window = context.window
        if window is None:
            self.report(
                {'ERROR'},
                "A window is required to create the demo scene.",
            )
            return {'CANCELLED'}

        existing = bpy.data.scenes.get(DEMO_SCENE_NAME)
        if existing is not None:
            window.scene = existing
            self.report({'INFO'}, "Switched to the existing Three Body Demo scene.")
            return {'FINISHED'}

        original = context.scene
        demo = bpy.data.scenes.new(DEMO_SCENE_NAME)
        window.scene = demo
        try:
            _populate_demo_scene(demo)
            _, _, status, error = bake.bake_sync(bpy.context)
            if status != "COMPLETED":
                raise RuntimeError(error or f"Demo bake {status.lower()}.")
        except Exception as exc:  # noqa: BLE001 - report instead of breaking the UI
            window.scene = original
            for obj in list(demo.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.scenes.remove(demo)
            self.report({'ERROR'}, f"Could not create the demo scene: {exc}")
            return {'CANCELLED'}

        demo.frame_set(1)
        self.report(
            {'INFO'},
            "Created the Three Body Demo scene. Press Play to watch it.",
        )
        return {'FINISHED'}


class THREEBODY_OT_setup_objects(bpy.types.Operator):
    """Create UV spheres and assign them to the simulation slots, clearing existing ones first"""
    bl_idname = "three_body.setup_objects"
    bl_label = "Setup Objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.three_body_props
        requested_model = props.simulation_model

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

        message = f"Reset and created {count} spheres."
        if requested_model != 'CUSTOM':
            if count == 3:
                # Assigning body.obj above switches the model to CUSTOM, so
                # this assignment runs update_preset_values and applies the
                # preset that was selected before pressing Setup.
                props.simulation_model = requested_model
                message += f" Applied preset: {props.simulation_model}."
            else:
                self.report(
                    {'WARNING'},
                    "Preset not applied: presets require exactly 3 bodies.",
                )
        self.report({'INFO'}, message)
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
        THREEBODY_OT_apply_preset,
        THREEBODY_OT_reset_settings,
        THREEBODY_OT_create_demo_scene,
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
        THREEBODY_OT_create_demo_scene,
        THREEBODY_OT_apply_preset,
        THREEBODY_OT_reset_settings,
        THREEBODY_OT_unbake_simulation,
        THREEBODY_OT_bake_simulation,
        THREEBODY_OT_sync_collection,
    )
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
