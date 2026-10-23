"""Bake pipeline shared by the modal operator and headless tests.

The numerical work lives in :mod:`algo`; this module only translates Blender
properties into a simulation configuration, applies keyframes, and finalizes
the scene. ``bake_sync`` makes the whole flow testable in ``--background``.
"""
import math
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

import bpy
import numpy as np

from . import algo, keyframes, presets
from .properties import is_valid_obj


class BakeValidationError(Exception):
    """Raised when the scene cannot be baked with the current settings."""


@dataclass
class BakeContext:
    scene: bpy.types.Scene
    props: object
    objects: list
    masses: np.ndarray
    positions: np.ndarray
    velocities: np.ndarray
    G: float
    softening: float
    collision_radii: Optional[np.ndarray]
    integrator: str
    substeps: int
    fps: int
    time_scale: float
    timeout_s: float
    max_v_safety: float
    start_frame: int
    end_frame: int


def _collision_radii(props, bodies) -> Optional[np.ndarray]:
    """Return world-space collision radii (not diameters)."""
    if not props.use_collision:
        return None

    radii = []
    for body in bodies:
        if (props.auto_collision_radius
                and body.obj.type == 'MESH'
                and len(body.obj.data.vertices) > 0):
            # Include object rotation/scale/parents, but not translation.
            matrix = body.obj.matrix_world.to_3x3()
            radius = max((matrix @ vertex.co).length for vertex in body.obj.data.vertices)
        else:
            radius = props.manual_collision_radius
        radii.append(max(float(radius) + props.radius_offset, 0.001))
    return np.array(radii, dtype=float)


def build_context(context) -> BakeContext:
    """Validate the scene and turn add-on properties into a BakeContext."""
    scene = context.scene
    props = scene.three_body_props

    if props.is_baking:
        raise BakeValidationError("A bake is already running.")
    if props.is_baked:
        raise BakeValidationError("Unbake the current simulation before baking again.")

    bodies = list(props.bodies)
    if not bodies:
        raise BakeValidationError("No celestial bodies defined.")

    preset = presets.PRESETS.get(props.simulation_model)
    if preset is not None and len(bodies) != 3:
        raise BakeValidationError("Presets require exactly 3 bodies.")

    for index, body in enumerate(bodies, start=1):
        if not is_valid_obj(body.obj):
            raise BakeValidationError(f"Body {index} has an invalid object.")
        if not math.isfinite(body.mass) or body.mass <= 0:
            raise BakeValidationError(f"Body {index} has an invalid mass (must be > 0).")
        if not np.all(np.isfinite(body.initial_location)):
            raise BakeValidationError(f"Body {index} has an invalid location.")
        if not np.all(np.isfinite(body.velocity)):
            raise BakeValidationError(f"Body {index} has an invalid velocity.")

    start_frame = int(props.frame_start)
    end_frame = int(props.frame_end)
    if end_frame < start_frame:
        raise BakeValidationError("End frame must be greater than or equal to start frame.")
    if end_frame - start_frame > 100_000:
        raise BakeValidationError("Frame range is too large (maximum 100000 frames).")

    fps = int(scene.render.fps if props.use_scene_fps else props.fps_override)
    if fps <= 0:
        raise BakeValidationError("FPS must be greater than zero.")

    scale = float(props.simulation_scale)
    if scale <= 0:
        raise BakeValidationError("Simulation scale must be greater than zero.")

    if preset is not None:
        G_base = preset.G
        softening_base = preset.softening
        substeps = preset.steps_per_frame
    else:
        G_base = 1.0
        softening_base = 0.02
        substeps = 10

    # Kepler-style scaling: positions/velocities are world-space and are
    # multiplied by S when a preset is applied, so G must grow by S^3.
    G = G_base * (scale ** 3) * props.gravity_strength
    softening = softening_base * scale * props.softening_multiplier

    masses = np.array([body.mass for body in bodies], dtype=float)
    positions = np.array([list(body.initial_location) for body in bodies], dtype=float)
    velocities = np.array([list(body.velocity) for body in bodies], dtype=float)

    return BakeContext(
        scene=scene,
        props=props,
        objects=[body.obj for body in bodies],
        masses=masses,
        positions=positions,
        velocities=velocities,
        G=G,
        softening=softening,
        collision_radii=_collision_radii(props, bodies),
        integrator=props.integrator_type,
        substeps=int(substeps),
        fps=fps,
        time_scale=float(props.time_scale),
        timeout_s=float(props.bake_limit_seconds),
        max_v_safety=float(props.max_velocity_safety),
        start_frame=start_frame,
        end_frame=end_frame,
    )


def simulate(ctx: BakeContext, cancel: Optional[Callable[[], bool]] = None
             ) -> Iterator[algo.FrameState]:
    """Yield simulated frames for *ctx*."""
    yield from algo.simulate_frames(
        masses=ctx.masses,
        positions=ctx.positions,
        velocities=ctx.velocities,
        start_frame=ctx.start_frame,
        end_frame=ctx.end_frame,
        fps=ctx.fps,
        time_scale=ctx.time_scale,
        G=ctx.G,
        softening=ctx.softening,
        collision_radii=ctx.collision_radii,
        integrator=ctx.integrator,
        substeps=ctx.substeps,
        timeout_s=ctx.timeout_s,
        max_v_safety=ctx.max_v_safety,
        cancel=cancel,
    )


def apply_frame(objects, state: algo.FrameState) -> None:
    """Write one simulated frame to object locations and keyframes."""
    for obj, position in zip(objects, state.positions):
        obj.location = position
        obj.keyframe_insert(data_path="location", frame=state.frame)


def format_report(status: str, state: Optional[algo.FrameState],
                  error: Optional[str] = None) -> str:
    if state is None:
        text = f"{status}. No frames baked."
    else:
        min_dist = "inf" if math.isinf(state.min_dist) else f"{state.min_dist:.3f}"
        accuracy = max(0.0, (1.0 - state.max_energy_drift) * 100.0)
        text = (
            f"{status}. Last frame: {state.frame}. "
            f"Max Speed: {state.max_speed:.3f}. Min Dist: {min_dist}. "
            f"Accuracy: {accuracy:.4f}%."
        )
    if error:
        text += f" Error: {error}"
    return text


def finalize(ctx: BakeContext, last_state: Optional[algo.FrameState], *,
             status: str = "COMPLETED", error: Optional[str] = None) -> bool:
    """Apply bake-wide settings and update the report. Returns is_baked."""
    scene = ctx.scene
    props = ctx.props

    scene.frame_start = ctx.start_frame
    scene.frame_end = ctx.end_frame

    for obj in ctx.objects:
        keyframes.set_location_interpolation(obj, "LINEAR")

    has_keys = any(keyframes.count_location_fcurves(obj) > 0 for obj in ctx.objects)
    props.is_baked = has_keys
    props.energy_drift = last_state.max_energy_drift if last_state else 0.0
    props.last_simulation_report = format_report(status, last_state, error)
    return has_keys


def bake_sync(context, cancel: Optional[Callable[[], bool]] = None):
    """Run a complete bake without the modal event loop (tests/tools).

    Returns ``(context, last_state, status, error)``.
    """
    ctx = build_context(context)
    props = ctx.props
    last_state = None
    status = "COMPLETED"
    error = None

    props.is_baking = True
    try:
        for state in simulate(ctx, cancel):
            apply_frame(ctx.objects, state)
            last_state = state
        if cancel is not None and cancel():
            status = "CANCELLED"
    except algo.SimulationError as exc:
        status = "ABORTED"
        error = str(exc)
    finally:
        props.is_baking = False
        finalize(ctx, last_state, status=status, error=error)

    return ctx, last_state, status, error
