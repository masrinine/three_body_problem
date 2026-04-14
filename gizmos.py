import bpy
from bpy.types import GizmoGroup

class THREEBODY_GGT_velocity_gizmo(GizmoGroup):
    bl_label = "Velocity Gizmo Group"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    @classmethod
    def poll(cls, context):
        props = context.scene.three_body_props
        return any(getattr(props, f"body{i}").obj for i in range(1, 4))

    def setup(self, context):
        props = context.scene.three_body_props
        
        for i in range(1, 4):
            # Create a move gizmo for each body
            gz = self.gizmos.new("GIZMO_GT_move_3d")
            
            # Use a custom property to store the index
            gz.body_index = i
            
            # Visual settings
            gz.color = (0.1, 0.5, 1.0) # Blue-ish
            gz.color_highlight = (0.4, 0.7, 1.0)
            gz.alpha = 0.5
            gz.scale_basis = 0.2
            
            # Hide the default line
            gz.use_draw_value = True
            gz.draw_options = {'DRAW_LINE'}

    def refresh(self, context):
        props = context.scene.three_body_props
        
        for gz in self.gizmos:
            i = gz.body_index
            body_prop = getattr(props, f"body{i}")
            obj = body_prop.obj
            
            if not obj:
                gz.hide = True
                continue
            
            gz.hide = not props.show_velocity_vectors
            
            # Target property to link
            # We want to link the gizmo's offset to the velocity property
            # However, 3d move gizmo usually works on a matrix.
            # We will manually sync in draw/refresh or use target_set_prop
            
            # Set the's matrix to the object's location
            # The gizmo itself will represent the velocity VECTOR starting from the object
            
            # Position the gizmo at the end of the velocity vector
            vel = body_prop.velocity
            loc = obj.location
            
            # Matrix for the gizmo position
            from mathutils import Matrix
            gz.matrix_basis = Matrix.Translation(loc + vel)

            # Link the gizmo to the velocity property
            # For "GIZMO_GT_move_3d", it expects a 'offset' or similar
            # Since we want bidirectional sync with the 'velocity' property (which is loc_relative),
            # we use target_set_handler to update the velocity when dragged.
            
    def draw_prepare(self, context):
        """Update gizmo positions every frame/draw call"""
        props = context.scene.three_body_props
        
        for gz in self.gizmos:
            i = gz.body_index
            body_prop = getattr(props, f"body{i}")
            obj = body_prop.obj
            if obj and not gz.hide:
                from mathutils import Matrix
                # Keep it at object + velocity
                gz.matrix_basis = Matrix.Translation(obj.location + body_prop.velocity)

    def invoke(self, context, event):
        # This allows clicking and dragging
        return {'PASS_THROUGH'}

    def modal(self, context, event, gizmo):
        # Handle the drag event
        if event.type == 'MOUSEMOVE':
            props = context.scene.three_body_props
            i = gizmo.body_index
            body_prop = getattr(props, f"body{i}")
            obj = body_prop.obj
            
            if obj:
                # Update velocity based on gizmo position relative to object
                new_pos = gizmo.matrix_basis.to_translation()
                body_prop.velocity = new_pos - obj.location
                
                # Switch to CUSTOM if modified
                if props.simulation_model != 'CUSTOM':
                    props.simulation_model = 'CUSTOM'
                    
        return {'PASS_THROUGH'}

def register():
    bpy.utils.register_class(THREEBODY_GGT_velocity_gizmo)

def unregister():
    bpy.utils.unregister_class(THREEBODY_GGT_velocity_gizmo)
