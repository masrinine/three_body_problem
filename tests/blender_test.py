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

from three_body_problem import bake, gizmos, keyframes  # noqa: E402


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
    test_sync_bake_and_linear_keys,
    test_rebake_blocked_while_baked,
    test_unbake_preserves_other_animation,
    test_invalid_frame_range_is_rejected,
    test_scale_change_rescales_stored_state,
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
