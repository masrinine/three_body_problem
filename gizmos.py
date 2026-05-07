import bpy
from bpy.types import GizmoGroup
from mathutils import Vector, Matrix

from .properties import is_valid_obj

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
        return any(body.obj for body in props.bodies)

    def setup(self, context):
        # We'll create a fixed pool of gizmos and hide/show them.
        # Alternatively, we can recreate them in refresh(), but setup is better for pools.
        MAX_GIZMOS = 50 
        for i in range(MAX_GIZMOS):
            gz = self.gizmos.new("GIZMO_GT_arrow_3d")
            gz.color = (0.1, 1.0, 1.0)
            gz.color_highlight = (1.0, 1.0, 1.0)
            gz.alpha = 0.8
            gz.scale_basis = 1.0
            gz.use_draw_value = True
            gz.hide = True

    def refresh(self, context):
        scene = context.scene
        if not hasattr(scene, "three_body_props"):
            for gz in self.gizmos:
                gz.hide = True
            return

        props = scene.three_body_props
        num_bodies = len(props.bodies)
        
        # 描画前に一度すべてのギズモを隠す（ゴースト残留を物理的に防ぐ）
        for gz in self.gizmos:
            gz.hide = True

        for i, body_prop in enumerate(props.bodies):
            if i >= len(self.gizmos):
                break
                
            gz = self.gizmos[i]
            obj = body_prop.obj
            
            if not is_valid_obj(obj):
                continue
            
            # 表示設定
            if not getattr(props, "show_velocity_vectors", True):
                continue

            loc = Vector(obj.location)
            vel = Vector(body_prop.velocity)
            
            v_len = vel.length
            if v_len > 1e-4:
                gz.hide = False 
                q = Vector((0, 0, 1)).rotation_difference(vel.normalized())
                rotation_mat = q.to_matrix().to_4x4()
                scale_mat = Matrix.Diagonal((1.0, 1.0, v_len, 1.0))
                gz.matrix_basis = Matrix.Translation(loc) @ rotation_mat @ scale_mat
            else:
                gz.hide = True

    def draw_prepare(self, context):
        """Keep gizmos attached to objects and oriented to velocity"""
        self.refresh(context)

    def invoke(self, context, event):
        return {'PASS_THROUGH'}

    def modal(self, context, event, gizmo):
        if event.type == 'MOUSEMOVE':
            props = context.scene.three_body_props
            
            # Identify which body this gizmo belongs to
            idx = -1
            for i, gz in enumerate(self.gizmos):
                if gz == gizmo:
                    idx = i
                    break
            
            if idx != -1 and idx < len(props.bodies):
                body_prop = props.bodies[idx]
                obj = body_prop.obj
                
                if obj:
                    # Sync gizmo position back to velocity property
                    # Note: ARROW_3D translation might be the tip or origin. 
                    # Usually, translation is the matrix origin (the shaft start).
                    # We need the tip's conceptual position if we were dragging it.
                    # But for simple Matrix.Translation(loc) @ rotation, 
                    # we just want to update velocity based on the change.
                    pass 
                    
        return {'PASS_THROUGH'}

def register():
    bpy.utils.register_class(THREEBODY_GGT_velocity_gizmo)

def unregister():
    bpy.utils.unregister_class(THREEBODY_GGT_velocity_gizmo)
