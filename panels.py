import bpy

class VIEW3D_PT_three_body_main(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'three_body_problem'
    bl_label = "Three Body Simulation"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.three_body_props

        # Quick Bake Section
        col = layout.column(align=True)
        col.operator("three_body.bake_simulation", icon='PLAY', text="Bake All")
        col.operator("three_body.unbake_simulation", icon='X', text="Unbake All")
        
        # Report Section
        if props.last_simulation_report:
            box = layout.box()
            row = box.row()
            # 折りたたみ用トグル
            icon = 'TRIA_DOWN' if props.show_report else 'TRIA_RIGHT'
            row.prop(props, "show_report", icon=icon, text="Latest Report", emboss=False)
            
            if props.show_report:
                # Split long text if necessary
                col = box.column()
                col.scale_y = 0.8
                words = props.last_simulation_report.split('. ')
                for word in words:
                    col.label(text=word.strip())

class VIEW3D_PT_three_body_bodies(bpy.types.Panel):
    bl_parent_id = "VIEW3D_PT_three_body_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "Celestial Bodies (N-Body)"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.three_body_props

        # Setup Section
        box = layout.box()
        box.label(text="Auto Setup", icon='MESH_UVSPHERE')
        row = box.row(align=True)
        row.prop(props, "setup_body_count", text="Count")
        row.operator("three_body.setup_objects", text="Setup")
        
        # New synchronization buttons
        layout.separator()
        col = layout.column(align=True)
        col.operator("three_body.capture_locations", icon='COPYDOWN')
        col.operator("three_body.apply_locations", icon='PASTEDOWN')

        layout.separator()

        # Dynamic List (N+1 implementation)
        # We show all current bodies, plus an "Add" button at the end
        for i, body in enumerate(props.bodies):
            box = layout.box()
            row = box.row()
            # Collapsible header
            icon = 'TRIA_DOWN' if body.is_expanded else 'TRIA_RIGHT'
            row.prop(body, "is_expanded", icon=icon, text="", emboss=False)
            row.prop(body, "obj", text=f"Body {i+1}")
            
            # Remove button
            op = row.operator("three_body.remove_body", text="", icon='X', emboss=False)
            op.index = i

            if body.is_expanded:
                col = box.column(align=True)
                col.prop(body, "mass")
                col.prop(body, "initial_location")
                col.prop(body, "velocity")

        # The "+1" part: Always show a way to add a new slot
        layout.operator("three_body.add_body", icon='ADD', text="Add Body Slot")

class VIEW3D_PT_three_body_presets(bpy.types.Panel):
    bl_parent_id = "VIEW3D_PT_three_body_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "3-Body Classic Presets"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.three_body_props
        
        # Check if we have exactly 3 bodies (or close)
        if len(props.bodies) != 3:
            layout.label(text="Presets require exactly 3 bodies", icon='ERROR')
            # Gray out the selector if not 3
            layout.enabled = False
        
        layout.prop(props, "simulation_model")
        
class VIEW3D_PT_three_body_settings(bpy.types.Panel):
    bl_parent_id = "VIEW3D_PT_three_body_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "Simulation Settings"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.three_body_props

        # Time Settings
        box = layout.box()
        box.label(text="Time & Resolution", icon='TIME')
        row = box.row(align=True)
        row.prop(props, "frame_start")
        row.prop(props, "frame_end")
        
        box.prop(props, "time_scale")
        box.prop(props, "use_scene_fps")
        if not props.use_scene_fps:
            box.prop(props, "fps_override")

        # Global Physical Constants
        box = layout.box()
        box.label(text="Global Physics", icon='WORLD')
        box.prop(props, "simulation_scale")
        box.prop(props, "gravity_strength")

        # Physics/Collision
        box = layout.box()
        box.label(text="Physics & Collision", icon='PHYSICS')
        box.prop(props, "softening_multiplier")
        
        box.separator()
        box.prop(props, "use_collision")
        if props.use_collision:
            col = box.column()
            col.prop(props, "auto_collision_radius")
            if not props.auto_collision_radius:
                col.prop(props, "manual_collision_radius")
            col.prop(props, "radius_offset")

class THREEBODY_OT_add_body(bpy.types.Operator):
    """Add a new body slot"""
    bl_idname = "three_body.add_body"
    bl_label = "Add Body"
    
    def execute(self, context):
        context.scene.three_body_props.bodies.add()
        return {'FINISHED'}

class THREEBODY_OT_remove_body(bpy.types.Operator):
    """Remove this body slot from the list (does NOT delete the object from scene)"""
    bl_idname = "three_body.remove_body"
    bl_label = "Remove Body Slot"
    bl_options = {'REGISTER', 'UNDO'}
    
    index: bpy.props.IntProperty() # type: ignore
    
    def execute(self, context):
        props = context.scene.three_body_props
        if self.index < len(props.bodies):
            # スロットをリストから削除するだけで、オブジェクトそのものは残す
            props.bodies.remove(self.index)
            
            # ギズモやUIの更新を促す
            context.area.tag_redraw()
            
        return {'FINISHED'}

def register():
    bpy.utils.register_class(VIEW3D_PT_three_body_main)
    bpy.utils.register_class(VIEW3D_PT_three_body_bodies)
    bpy.utils.register_class(VIEW3D_PT_three_body_presets)
    bpy.utils.register_class(VIEW3D_PT_three_body_settings)
    bpy.utils.register_class(THREEBODY_OT_add_body)
    bpy.utils.register_class(THREEBODY_OT_remove_body)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_three_body_main)
    bpy.utils.unregister_class(VIEW3D_PT_three_body_bodies)
    bpy.utils.unregister_class(VIEW3D_PT_three_body_presets)
    bpy.utils.unregister_class(VIEW3D_PT_three_body_settings)
    bpy.utils.unregister_class(THREEBODY_OT_add_body)
    bpy.utils.unregister_class(THREEBODY_OT_remove_body)
