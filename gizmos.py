import bpy
from bpy.types import GizmoGroup
from mathutils import Vector, Matrix

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
        return any(getattr(props, f"body{i}").obj for i in range(1, 4))

    def setup(self, context):
        for i in range(1, 4):
            # Use ARROW_3D for high visibility and intuitive direction
            gz = self.gizmos.new("GIZMO_GT_arrow_3d")
            
            # Visual settings
            gz.color = (0.1, 1.0, 1.0) # Cyan
            gz.color_highlight = (1.0, 1.0, 1.0)
            gz.alpha = 0.8
            gz.scale_basis = 1.0 # Base scale for the arrow
            
            gz.use_draw_value = True

    def refresh(self, context):
        props = context.scene.three_body_props
        
        for i, gz in enumerate(self.gizmos):
            body_num = i + 1
            body_prop = getattr(props, f"body{body_num}")
            obj = body_prop.obj
            
            if not obj:
                gz.hide = True
                continue
            
            gz.hide = not props.show_velocity_vectors
            
            loc = Vector(obj.location)
            vel = Vector(body_prop.velocity)
            
            # The matrix_basis for an arrow gizmo:
            # The arrow points along its local Z axis. We need to rotate it to match velocity.
            # And place it at the object's location.
            
            v_len = vel.length
            if v_len > 1e-4:
                # Direction from object to velocity point
                q = Vector((0, 0, 1)).rotation_difference(vel.normalized())
                rotation_mat = q.to_matrix().to_4x4()
                # Scale the arrow based on velocity magnitude
                scale_mat = Matrix.Diagonal((1.0, 1.0, v_len, 1.0))
                gz.matrix_basis = Matrix.Translation(loc) @ rotation_mat @ scale_mat
            else:
                # If velocity is zero, just hide it or point it up
                gz.matrix_basis = Matrix.Translation(loc)
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
                    idx = i + 1
                    break
            
            if idx != -1:
                body_prop = getattr(props, f"body{idx}")
                obj = body_prop.obj
                
                if obj:
                    # Sync gizmo position back to velocity property
                    new_pos = gizmo.matrix_basis.to_translation()
                    body_prop.velocity = Vector(new_pos) - Vector(obj.location)
                    
                    if props.simulation_model != 'CUSTOM':
                        props.simulation_model = 'CUSTOM'
                    
        return {'PASS_THROUGH'}

def register():
    bpy.utils.register_class(THREEBODY_GGT_velocity_gizmo)

def unregister():
    bpy.utils.unregister_class(THREEBODY_GGT_velocity_gizmo)
