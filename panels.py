import bpy

class VIEW3D_PT_three_body_main(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'three_body_problem'
    bl_label = "Three Body Simulation"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = getattr(scene, "three_body_props", None)
        
        if props is None:
            layout.label(text="Properties not registered properly.")
            return

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
                
                # Accuracy indicator (Hamiltonian Drift)
                if props.is_baked:
                    drift_val = props.energy_drift
                    accuracy = max(0.0, (1.0 - drift_val) * 100.0)
                    acc_col = col.column()
                    acc_col.label(text=f"Physics Accuracy: {accuracy:.4f}%", icon='FUND')
                    if accuracy < 99.0:
                        acc_col.label(text="Warning: Low accuracy. Increase substeps.", icon='ERROR')
                    col.separator()

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
        props = getattr(context.scene, "three_body_props", None)
        if props is None:
            return

        # Setup Section
        box = layout.box()
        box.label(text="Auto Setup & Management", icon='MESH_UVSPHERE')
        
        # Collection Sync Row
        row = box.row(align=True)
        row.prop(props, "sync_collection", text="")
        row.operator("three_body.sync_collection", text="Sync From Collection", icon='FILE_REFRESH')
        
        # Spacer
        box.separator()
        
        row = box.row(align=True)
        row.prop(props, "setup_body_count", text="Quick Count")
        row.operator("three_body.setup_objects", text="Auto Setup")
        
        # Header toolbar for bodies list
        layout.separator()
        
        # --- Reliability Locking ---
        # If baked, lock the body editing to prevent inconsistencies
        body_col = layout.column()
        if props.is_baked:
            msg_box = body_col.box()
            row = msg_box.row()
            row.label(text="Simulation Baked: Inputs Locked", icon='LOCKED')
            body_col.enabled = False
        
        row = body_col.row(align=True)
        row.prop(props, "use_compact_list", text="", icon='PREFERENCES' if props.use_compact_list else 'USER')
        row.label(text="Actions:" if not props.use_compact_list else "")
        row.operator("three_body.capture_locations", icon='COPYDOWN', text="" if props.use_compact_list else "Capture")
        row.operator("three_body.apply_locations", icon='PASTEDOWN', text="" if props.use_compact_list else "Apply")
        row.operator("three_body.add_body", icon='ADD', text="" if props.use_compact_list else "Add Slot")

        body_col.separator()

        # Dynamic List
        for i, body in enumerate(props.bodies):
            # Object check to prevent UI drawing from collapsing incorrectly if object is None
            row_label = f"Body {i+1}"
            if body.obj:
                row_label = body.obj.name

            if props.use_compact_list:
                # Compact One-liner
                row = body_col.row(align=True)
                row.prop(body, "is_expanded", icon='TRIA_DOWN' if body.is_expanded else 'TRIA_RIGHT', text="", emboss=False)
                row.prop(body, "obj", text="")
                row.prop(body, "mass", text="M")
                row.operator("three_body.remove_body", text="", icon='X', emboss=False).index = i
            else:
                # Standard Box View
                box = body_col.box()
                row = box.row()
                row.prop(body, "is_expanded", icon='TRIA_DOWN' if body.is_expanded else 'TRIA_RIGHT', text="", emboss=False)
                row.prop(body, "obj", text=row_label)
                row.operator("three_body.remove_body", text="", icon='X', emboss=False).index = i

            if body.is_expanded:
                # Ensure detailed props are visible if expanded, even in compact mode
                col = (body_col if props.use_compact_list else box).column(align=True)
                if props.use_compact_list: col.separator()
                col.prop(body, "mass")
                col.prop(body, "initial_location")
                col.prop(body, "velocity")

class VIEW3D_PT_three_body_presets(bpy.types.Panel):
    bl_parent_id = "VIEW3D_PT_three_body_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = "3-Body Classic Presets"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = getattr(context.scene, "three_body_props", None)
        if props is None:
            return
        
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
        props = getattr(context.scene, "three_body_props", None)
        if props is None:
            return

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
        box.prop(props, "integrator_type")
        box.prop(props, "simulation_scale")
        box.prop(props, "gravity_strength")
        box.prop(props, "velocity_gizmo_scale")

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
        body = context.scene.three_body_props.bodies.add()
        body.is_expanded = False
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
    classes = (
        VIEW3D_PT_three_body_main,
        VIEW3D_PT_three_body_bodies,
        VIEW3D_PT_three_body_presets,
        VIEW3D_PT_three_body_settings,
        THREEBODY_OT_add_body,
        THREEBODY_OT_remove_body,
    )
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass

def unregister():
    classes = (
        THREEBODY_OT_remove_body,
        THREEBODY_OT_add_body,
        VIEW3D_PT_three_body_settings,
        VIEW3D_PT_three_body_presets,
        VIEW3D_PT_three_body_bodies,
        VIEW3D_PT_three_body_main,
    )
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
