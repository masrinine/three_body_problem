import bpy
from bpy.types import GizmoGroup
from mathutils import Vector, Matrix

from .properties import is_valid_obj

# A body whose initial velocity is at or below this length gets no arrow. The
# viewport-only display is meant to show a direction, and a zero-length arrow
# has none (it used to be drawn as a small blob, which read as noise).
ZERO_VELOCITY_EPSILON = 1e-6

# Fixed pool of arrow gizmos. ``add_body`` has no upper limit, so keep the pool
# well above the largest realistic system (``setup_body_count`` caps at 50).
# Bodies beyond the pool are simply not drawn.
MAX_GIZMOS = 128


def velocity_gizmo_matrix(obj, velocity, display_scale=1.0):
    """Build the world-space matrix for one body's velocity arrow.

    The stored ``velocity`` is world-space, so the arrow starts at the object's
    world translation (``matrix_world.translation``) rather than ``obj.location``,
    which is parent space. Returns ``None`` when no arrow should be drawn.
    """
    vel = Vector(velocity)
    v_len = vel.length
    if v_len <= ZERO_VELOCITY_EPSILON:
        return None

    loc = obj.matrix_world.translation.copy()
    direction = vel.normalized()
    rotation_mat = Vector((0.0, 0.0, 1.0)).rotation_difference(direction).to_matrix().to_4x4()
    scale_mat = Matrix.Diagonal(
        (display_scale, display_scale, v_len * display_scale, 1.0)
    )
    return Matrix.Translation(loc) @ rotation_mat @ scale_mat


class THREEBODY_GGT_velocity_gizmo(GizmoGroup):
    bl_label = "Velocity Gizmo Group"
    bl_idname = "THREEBODY_GGT_velocity_gizmo"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    @classmethod
    def poll(cls, context):
        if not hasattr(context.scene, "three_body_props"):
            return False
        props = context.scene.three_body_props
        if not props.show_velocity_vectors:
            return False
        return any(is_valid_obj(body.obj) for body in props.bodies)

    def setup(self, context):
        # Fixed pool of gizmos that is hidden/shown from refresh() instead of
        # being recreated, which is cheaper and avoids GUI lifetime issues.
        for _ in range(MAX_GIZMOS):
            gz = self.gizmos.new("GIZMO_GT_arrow_3d")
            gz.color = (0.1, 1.0, 1.0)
            gz.color_highlight = (1.0, 1.0, 1.0)
            gz.alpha = 0.8
            gz.scale_basis = 1.0
            gz.use_draw_value = False
            gz.hide = True

    def refresh(self, context):
        scene = context.scene
        if not hasattr(scene, "three_body_props"):
            for gz in self.gizmos:
                gz.hide = True
            return

        props = scene.three_body_props

        # Hide everything first so stale arrows cannot linger on screen.
        for gz in self.gizmos:
            gz.hide = True

        if not props.show_velocity_vectors:
            return

        display_scale = props.velocity_gizmo_scale

        for i, body_prop in enumerate(props.bodies):
            if i >= len(self.gizmos):
                break

            obj = body_prop.obj
            if not is_valid_obj(obj):
                continue
            # Hidden viewport objects and objects in excluded collections are
            # not visible; mirror that for their arrows.
            if not obj.visible_get():
                continue

            matrix = velocity_gizmo_matrix(obj, body_prop.velocity, display_scale)
            if matrix is None:
                continue

            gz = self.gizmos[i]
            gz.matrix_basis = matrix
            gz.hide = False

    def draw_prepare(self, context):
        """Re-read object positions every draw so arrows follow the bodies."""
        self.refresh(context)

    def invoke(self, context, event):
        return {'PASS_THROUGH'}

    def modal(self, context, event, gizmo):
        # Reading-only overlay: the arrows do not drive the simulation state
        # (dead code is cleaned up in P2-15).
        return {'PASS_THROUGH'}


def register():
    try:
        bpy.utils.register_class(THREEBODY_GGT_velocity_gizmo)
    except ValueError:
        pass


def unregister():
    try:
        bpy.utils.unregister_class(THREEBODY_GGT_velocity_gizmo)
    except RuntimeError:
        pass
