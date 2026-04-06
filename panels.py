import bpy

class VIEW3D_PT_three_body_problem(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'three_body_problem'
    bl_label = "Three Body Simulation"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.three_body_props

        # Preset Selection
        layout.label(text="Preset Selection", icon='PRESET')
        layout.prop(props, "simulation_model")
        layout.prop(props, "time_scale")
        layout.prop(props, "simulation_scale")
        layout.prop(props, "softening_multiplier")
        layout.separator()

        # Body selection
        layout.label(text="Celestial Bodies", icon='OBJECT_DATA')
        for i in range(1, 4):
            body_prop = getattr(props, f"body{i}")
            layout.prop(body_prop, "obj", text=f"Body {i}")

        layout.separator()

        # Time Settings
        layout.label(text="Time & FPS", icon='TIME')
        row = layout.row(align=True)
        row.prop(props, "frame_start")
        row.prop(props, "frame_end")
        
        layout.prop(props, "use_scene_fps")
        if not props.use_scene_fps:
            layout.prop(props, "fps_override")

        layout.separator()

        # Simulation Execution
        layout.separator()
        layout.label(text="Collision Settings", icon='PHYSICS')
        box = layout.box()
        box.prop(props, "use_collision")
        if props.use_collision:
            box.prop(props, "auto_collision_radius")
            if not props.auto_collision_radius:
                box.prop(props, "manual_collision_radius")
            box.prop(props, "radius_offset")

        layout.separator()
        layout.label(text="Simulation", icon='PHYSICS')
        layout.operator("three_body.bake_simulation", icon='RENDER_STILL')

def register():
    bpy.utils.register_class(VIEW3D_PT_three_body_problem)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_three_body_problem)
