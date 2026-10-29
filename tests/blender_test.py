"""Headless Blender integration tests for the Three Body Problem add-on.

Run with:

    & 'C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe' ^
        --background --factory-startup --python-exit-code 1 ^
        --python tests/blender_test.py

Covers registration, the synchronous bake path (``bake.bake_sync``), keyframe
interpolation, safe unbake (slotted actions), and input validation.
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]

# Import the package by path so the checkout directory does not have to be named
# exactly "three_body_problem" (GitHub Actions checkout folder names can vary).
_spec = importlib.util.spec_from_file_location(
    "three_body_problem",
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
assert _spec is not None and _spec.loader is not None
tbp = importlib.util.module_from_spec(_spec)
sys.modules["three_body_problem"] = tbp
_spec.loader.exec_module(tbp)

from three_body_problem import bake, gizmos, keyframes, presets, properties  # noqa: E402


def reset_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)

    props = bpy.context.scene.three_body_props
    props.bodies.clear()
    props.is_baked = False
    props.is_baking = False
    props.energy_drift = 0.0
    props.simulation_model = 'CUSTOM'
    props.use_collision = False
    props.frame_start = 1
    props.frame_end = 10
    props.simulation_scale = 5.0
    props["_last_simulation_scale"] = 5.0
    props.show_velocity_vectors = True
    props.velocity_gizmo_scale = 1.0


def setup_three_bodies():
    props = bpy.context.scene.three_body_props
    props.setup_body_count = 3
    bpy.ops.three_body.setup_objects()
    props.simulation_model = 'FIGURE_8'
    return props


def assert_matches_preset(props, model):
    """Check body state and object locations against a preset times scale."""
    preset = presets.PRESETS[model]
    scale = props.simulation_scale
    assert props.simulation_model == model, props.simulation_model
    assert len(props.bodies) == 3
    for i, body in enumerate(props.bodies):
        assert body.obj is not None
        expected_loc = tuple(float(x) * scale for x in preset.positions[i])
        expected_vel = tuple(float(x) * scale for x in preset.velocities[i])
        for actual, expected in zip(body.initial_location, expected_loc):
            assert abs(actual - expected) < 1e-4, (
                i,
                tuple(body.initial_location),
                expected_loc,
            )
        for actual, expected in zip(body.velocity, expected_vel):
            assert abs(actual - expected) < 1e-4, (
                i,
                tuple(body.velocity),
                expected_vel,
            )
        for actual, expected in zip(body.obj.location, expected_loc):
            assert abs(actual - expected) < 1e-4, (
                i,
                body.obj.name,
                tuple(body.obj.location),
                expected_loc,
            )


def test_register():
    assert hasattr(bpy.ops.three_body, "bake_simulation")
    assert hasattr(bpy.ops.three_body, "unbake_simulation")
    # The velocity arrows are drawn by the gizmo group only (visualization.py
    # was removed in P1-10). GizmoGroup subclasses are not exposed on bpy.types,
    # so prove registration by checking that a second one is rejected.
    group = gizmos.THREEBODY_GGT_velocity_gizmo
    assert issubclass(group, bpy.types.GizmoGroup)
    try:
        bpy.utils.register_class(group)
    except ValueError:
        pass
    else:
        raise AssertionError("velocity gizmo group is not registered")
    assert hasattr(bpy.types, "VIEW3D_PT_three_body_display")


def test_velocity_display_properties():
    reset_scene()
    props = bpy.context.scene.three_body_props

    assert props.show_velocity_vectors is True
    assert abs(props.velocity_gizmo_scale - 1.0) < 1e-9

    props.show_velocity_vectors = False
    assert props.show_velocity_vectors is False
    props.show_velocity_vectors = True
    assert props.show_velocity_vectors is True

    props.velocity_gizmo_scale = 3.0
    assert abs(props.velocity_gizmo_scale - 3.0) < 1e-9
    props.velocity_gizmo_scale = 1.0


def test_velocity_gizmo_group_poll():
    reset_scene()
    props = bpy.context.scene.three_body_props
    group = gizmos.THREEBODY_GGT_velocity_gizmo

    assert group.poll(bpy.context) is False, "no bodies yet"

    setup_three_bodies()
    assert group.poll(bpy.context) is True

    props.show_velocity_vectors = False
    assert group.poll(bpy.context) is False
    props.show_velocity_vectors = True
    assert group.poll(bpy.context) is True


def test_velocity_gizmo_matrix_is_world_space():
    from mathutils import Vector

    reset_scene()
    empty = bpy.data.objects.new("ParentEmpty", None)
    bpy.context.scene.collection.objects.link(empty)
    empty.location = (5.0, 0.0, 0.0)

    mesh = bpy.data.meshes.new("BodyMesh")
    obj = bpy.data.objects.new("Body", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = empty
    # Parent space: world position must be (6, 0, 0).
    obj.location = (1.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    matrix = gizmos.velocity_gizmo_matrix(obj, (0.0, 0.0, 2.0), 1.0)
    assert matrix is not None
    assert tuple(round(v, 6) for v in matrix.translation) == (6.0, 0.0, 0.0), matrix.translation
    assert abs(matrix.to_scale().z - 2.0) < 1e-6, matrix.to_scale()

    # Direction follows the world-space velocity (Z axis -> +X).
    matrix_x = gizmos.velocity_gizmo_matrix(obj, (2.0, 0.0, 0.0), 1.0)
    assert matrix_x is not None
    tip = (matrix_x.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    assert tuple(round(v, 6) for v in tip) == (1.0, 0.0, 0.0), tip

    # Zero velocity draws nothing.
    assert gizmos.velocity_gizmo_matrix(obj, (0.0, 0.0, 0.0), 1.0) is None

    # Hidden objects are skipped by refresh(); visible_get() is the gate.
    obj.hide_set(True)
    bpy.context.view_layer.update()
    assert obj.visible_get() is False
    obj.hide_set(False)
    bpy.context.view_layer.update()
    assert obj.visible_get() is True


def test_setup_and_preset():
    reset_scene()
    props = setup_three_bodies()
    assert len(props.bodies) == 3
    # Figure-8 has one body at the origin, so only require that the system as a
    # whole is placed away from the origin.
    assert any(
        abs(value) > 1e-9
        for body in props.bodies
        for value in body.initial_location
    )


def test_auto_setup_applies_selected_preset():
    reset_scene()
    props = bpy.context.scene.three_body_props
    props.simulation_model = 'FIGURE_8'  # selected before Setup
    props.setup_body_count = 3
    props.simulation_scale = 5.0
    props["_last_simulation_scale"] = 5.0

    bpy.ops.three_body.setup_objects()

    # Previously this ended as CUSTOM with a collinear row of spheres.
    assert_matches_preset(props, 'FIGURE_8')
    assert abs(props["_last_simulation_scale"] - 5.0) < 1e-9

    # Presets need exactly 3 bodies, so a 4-body setup stays CUSTOM.
    reset_scene()
    props = bpy.context.scene.three_body_props
    props.simulation_model = 'FIGURE_8'
    props.setup_body_count = 4
    bpy.ops.three_body.setup_objects()
    assert props.simulation_model == 'CUSTOM'


def test_selecting_preset_after_edit_reapplies():
    reset_scene()
    props = setup_three_bodies()
    props.bodies[0].velocity = (9.0, 9.0, 9.0)
    assert props.simulation_model == 'CUSTOM'

    # Re-selecting the preset must overwrite the edited state.
    props.simulation_model = 'FIGURE_8'
    assert_matches_preset(props, 'FIGURE_8')


def test_apply_preset_operator_reapplies():
    reset_scene()
    props = setup_three_bodies()
    assert bpy.ops.three_body.apply_preset.poll() is True

    # Corrupt a value without letting the edit callback switch to CUSTOM, so the
    # operator has something to restore while the preset is still selected.
    props["_updating_from_preset"] = True
    try:
        props.bodies[0].velocity = (9.0, 9.0, 9.0)
    finally:
        props["_updating_from_preset"] = False
    assert props.simulation_model == 'FIGURE_8'

    result = bpy.ops.three_body.apply_preset()
    assert result == {'FINISHED'}, result
    assert_matches_preset(props, 'FIGURE_8')


def test_apply_preset_refusals():
    reset_scene()
    props = setup_three_bodies()

    # CUSTOM is not a preset.
    props.bodies[0].velocity = (9.0, 9.0, 9.0)
    assert props.simulation_model == 'CUSTOM'
    assert bpy.ops.three_body.apply_preset.poll() is False
    assert properties.apply_preset_to_bodies(props, 'CUSTOM') is False

    # Baked state.
    props.simulation_model = 'FIGURE_8'
    props.is_baked = True
    assert bpy.ops.three_body.apply_preset.poll() is False
    props.is_baked = False

    # Missing object while the preset is still selected.
    props["_updating_from_preset"] = True
    try:
        props.bodies[2].obj = None
    finally:
        props["_updating_from_preset"] = False
    assert props.simulation_model == 'FIGURE_8'
    assert bpy.ops.three_body.apply_preset.poll() is False
    assert properties.apply_preset_to_bodies(props, 'FIGURE_8') is False

    # Wrong body count.
    props.bodies.remove(0)
    assert bpy.ops.three_body.apply_preset.poll() is False


def test_demo_scene_created_once():
    reset_scene()
    original = bpy.context.scene
    original_objects = set(original.objects)
    original_model = original.three_body_props.simulation_model
    original_baked = original.three_body_props.is_baked
    scene_count = len(bpy.data.scenes)
    try:
        result = bpy.ops.three_body.create_demo_scene()
        assert result == {'FINISHED'}, result

        demo = bpy.data.scenes.get("Three Body Demo")
        assert demo is not None
        assert bpy.context.window.scene == demo
        assert len(bpy.data.scenes) == scene_count + 1

        props = demo.three_body_props
        assert props.is_baked is True
        assert props.simulation_model == 'FIGURE_8'
        assert len(props.bodies) == 3
        assert demo.frame_start == 1
        assert demo.frame_end == 250
        assert demo.render.fps == 24
        assert demo.render.engine == 'BLENDER_EEVEE'
        assert demo.camera is not None
        assert any(obj.type == 'LIGHT' for obj in demo.objects)
        assert bpy.data.objects.get("Demo Backdrop") is not None

        preset = presets.PRESETS['FIGURE_8']
        for i, body in enumerate(props.bodies):
            assert body.obj is not None
            assert body.obj.name in demo.objects
            assert body.obj.data.materials
            expected_velocity = [
                float(x) * props.simulation_scale
                for x in preset.velocities[i]
            ]
            for actual, expected in zip(body.velocity, expected_velocity):
                assert abs(actual - expected) < 1e-4
            assert keyframes.count_location_fcurves(body.obj) > 0

        # The pre-baked demo must move when the timeline advances.
        demo.frame_set(1)
        start = [
            tuple(body.obj.matrix_world.translation) for body in props.bodies
        ]
        demo.frame_set(40)
        later = [
            tuple(body.obj.matrix_world.translation) for body in props.bodies
        ]
        assert any(
            abs(a - b) > 1e-4
            for start_pos, later_pos in zip(start, later)
            for a, b in zip(start_pos, later_pos)
        )

        # A second click reuses the scene instead of duplicating it.
        result = bpy.ops.three_body.create_demo_scene()
        assert result == {'FINISHED'}, result
        assert len(bpy.data.scenes) == scene_count + 1
        assert bpy.context.window.scene is demo

        # The scene that was active before the operator is untouched.
        assert set(original.objects) == original_objects
        assert original.three_body_props.simulation_model == original_model
        assert original.three_body_props.is_baked == original_baked
    finally:
        window = bpy.context.window
        if window is not None:
            window.scene = original
        demo = bpy.data.scenes.get("Three Body Demo")
        if demo is not None:
            for obj in list(demo.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.scenes.remove(demo)


def test_sync_bake_and_linear_keys():
    reset_scene()
    props = setup_three_bodies()
    scene = bpy.context.scene

    ctx, last, status, error = bake.bake_sync(bpy.context)
    assert status == "COMPLETED", (status, error)
    assert props.is_baked, props.last_simulation_report
    assert scene.frame_start == 1 and scene.frame_end == 10
    assert last is not None and math.isfinite(last.max_energy_drift)
    assert 0.0 <= last.max_energy_drift < 0.01

    for body in props.bodies:
        location_fcurves = keyframes.location_fcurves(body.obj)
        assert len(location_fcurves) == 3, len(location_fcurves)
        assert keyframes.count_location_fcurves(body.obj) == 3
        for fcurve in location_fcurves:
            assert len(fcurve.keyframe_points) == 10, len(fcurve.keyframe_points)
            for keyframe in fcurve.keyframe_points:
                assert keyframe.interpolation == 'LINEAR', keyframe.interpolation


def test_rebake_blocked_while_baked():
    reset_scene()
    setup_three_bodies()
    bake.bake_sync(bpy.context)
    try:
        bake.build_context(bpy.context)
    except bake.BakeValidationError:
        return
    raise AssertionError("build_context should reject a second bake while baked")


def test_unbake_preserves_other_animation():
    reset_scene()
    props = bpy.context.scene.three_body_props

    bpy.ops.mesh.primitive_cube_add(location=(1.0, 2.0, 3.0))
    obj = bpy.context.active_object
    body = props.bodies.add()
    body.obj = obj
    body.initial_location = (1.0, 2.0, 3.0)

    obj.location = (1.0, 2.0, 3.0)
    obj.keyframe_insert(data_path="location", frame=1)
    obj.location = (2.0, 2.0, 3.0)
    obj.keyframe_insert(data_path="location", frame=5)
    obj.rotation_euler = (0.25, 0.0, 0.0)
    obj.keyframe_insert(data_path="rotation_euler", frame=1)
    obj.scale = (2.0, 2.0, 2.0)
    obj.keyframe_insert(data_path="scale", frame=1)

    # At the start frame the depsgraph handler treats the viewport location as
    # the initial state, so move off the start frame and set it explicitly.
    bpy.context.scene.frame_current = 5
    body.initial_location = (1.0, 2.0, 3.0)

    props.is_baked = True
    result = bpy.ops.three_body.unbake_simulation()
    assert result == {'FINISHED'}, result

    assert keyframes.count_location_fcurves(obj) == 0
    remaining = list(keyframes.iter_action_fcurves(obj))
    assert remaining, "rotation/scale animation must survive unbake"
    assert obj.animation_data is not None
    assert not props.is_baked
    assert tuple(round(value, 5) for value in obj.location) == (1.0, 2.0, 3.0)


def test_invalid_frame_range_is_rejected():
    reset_scene()
    props = setup_three_bodies()
    props.frame_start = 10
    props.frame_end = 5
    try:
        bake.build_context(bpy.context)
    except bake.BakeValidationError:
        return
    raise AssertionError("build_context should reject end < start")


def test_scale_change_rescales_stored_state():
    reset_scene()
    props = setup_three_bodies()
    original_locations = [tuple(body.initial_location) for body in props.bodies]
    original_velocities = [tuple(body.velocity) for body in props.bodies]

    props.simulation_scale = 10.0
    for body, location in zip(props.bodies, original_locations):
        for actual, expected in zip(body.initial_location, location):
            assert abs(actual - expected * 2.0) < 1e-5, (actual, expected)
    for body, velocity in zip(props.bodies, original_velocities):
        for actual, expected in zip(body.velocity, velocity):
            assert abs(actual - expected * 2.0) < 1e-5, (actual, expected)

    props.simulation_scale = 5.0
    for body, location in zip(props.bodies, original_locations):
        for actual, expected in zip(body.initial_location, location):
            assert abs(actual - expected) < 1e-5, (actual, expected)


def test_reset_settings():
    reset_scene()
    props = setup_three_bodies()
    model_before = props.simulation_model
    objects_before = [body.obj for body in props.bodies]
    masses_before = [body.mass for body in props.bodies]
    locations_before = [tuple(body.initial_location) for body in props.bodies]
    velocities_before = [tuple(body.velocity) for body in props.bodies]

    props.setup_body_count = 7
    props.frame_start = 10
    props.frame_end = 99
    props.use_scene_fps = False
    props.fps_override = 60
    props.time_scale = 2.5
    props.softening_multiplier = 1.25
    props.simulation_scale = 10.0
    props.use_collision = True
    props.auto_collision_radius = False
    props.manual_collision_radius = 1.5
    props.radius_offset = 0.4
    props.gravity_strength = 2.0
    props.integrator_type = 'LEAPFROG'
    props.bake_limit_seconds = 20.0
    props.max_velocity_safety = 50.0
    props.use_compact_list = True
    props.show_velocity_vectors = False
    props.velocity_gizmo_scale = 3.0
    props.show_report = False
    props.energy_drift = 1.25
    props.last_simulation_report = "dirty"

    result = bpy.ops.three_body.reset_settings('EXEC_DEFAULT')
    assert result == {'FINISHED'}, result

    assert props.setup_body_count == 3
    assert props.frame_start == 1
    assert props.frame_end == 250
    assert props.use_scene_fps is True
    assert props.fps_override == 24
    assert abs(props.time_scale - 1.0) < 1e-9
    assert abs(props.softening_multiplier - 3.0) < 1e-9
    assert abs(props.simulation_scale - 5.0) < 1e-9
    assert props.use_collision is False
    assert props.auto_collision_radius is True
    assert abs(props.manual_collision_radius - 0.5) < 1e-9
    assert abs(props.radius_offset) < 1e-9
    assert abs(props.gravity_strength - 1.0) < 1e-9
    assert props.integrator_type == 'RK45'
    assert abs(props.bake_limit_seconds - 5.0) < 1e-9
    assert abs(props.max_velocity_safety - 1000.0) < 1e-9
    assert props.use_compact_list is False
    assert props.show_velocity_vectors is True
    assert abs(props.velocity_gizmo_scale - 1.0) < 1e-9
    assert props.show_report is True
    assert abs(props.energy_drift) < 1e-9
    assert props.last_simulation_report == ""
    assert abs(props["_last_simulation_scale"] - 5.0) < 1e-9

    # Bodies and the selected preset are intentionally untouched. The scale
    # callback only rescaled the stored state back to the default scale.
    assert props.simulation_model == model_before == 'FIGURE_8'
    assert len(props.bodies) == 3
    for body, obj, mass, location, velocity in zip(
        props.bodies,
        objects_before,
        masses_before,
        locations_before,
        velocities_before,
    ):
        assert body.obj == obj
        assert abs(body.mass - mass) < 1e-9
        for actual, expected in zip(body.initial_location, location):
            assert abs(actual - expected) < 1e-5, (actual, expected)
        for actual, expected in zip(body.velocity, velocity):
            assert abs(actual - expected) < 1e-5, (actual, expected)

    # Reset is refused while a bake is running or after a bake.
    props.frame_end = 99
    for flag in ("is_baked", "is_baking"):
        setattr(props, flag, True)
        try:
            # The operator stays callable from scripts (the panel disables the
            # button) so execute() can report the reason instead of failing
            # with a generic poll error.
            assert bpy.ops.three_body.reset_settings.poll() is True
            try:
                result = bpy.ops.three_body.reset_settings('EXEC_DEFAULT')
            except RuntimeError as exc:
                assert "Unbake before resetting settings" in str(exc), exc
            else:
                assert result == {'CANCELLED'}, result
            assert props.frame_end == 99
        finally:
            setattr(props, flag, False)


def test_simulate_frame_count():
    reset_scene()
    props = setup_three_bodies()
    ctx = bake.build_context(bpy.context)
    states = list(bake.simulate(ctx))
    assert [state.frame for state in states] == list(range(1, 11)), [s.frame for s in states]


TESTS = [
    test_register,
    test_velocity_display_properties,
    test_velocity_gizmo_group_poll,
    test_velocity_gizmo_matrix_is_world_space,
    test_setup_and_preset,
    test_auto_setup_applies_selected_preset,
    test_selecting_preset_after_edit_reapplies,
    test_apply_preset_operator_reapplies,
    test_apply_preset_refusals,
    test_demo_scene_created_once,
    test_sync_bake_and_linear_keys,
    test_rebake_blocked_while_baked,
    test_unbake_preserves_other_animation,
    test_invalid_frame_range_is_rejected,
    test_scale_change_rescales_stored_state,
    test_reset_settings,
    test_simulate_frame_count,
]


def main():
    tbp.register()
    try:
        failures = []
        for test in TESTS:
            try:
                test()
                print(f"PASS {test.__name__}")
            except Exception as exc:  # noqa: BLE001 - report every failure
                failures.append((test.__name__, exc))
                print(f"FAIL {test.__name__}: {exc!r}")
        if failures:
            raise AssertionError(f"{len(failures)} test(s) failed: {failures}")
        print("BLENDER_TESTS_OK")
    finally:
        tbp.unregister()


main()
