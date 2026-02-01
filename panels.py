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

        # Model Selection
        layout.label(text="Model Settings", icon='SETTINGS')
        layout.prop(props, "simulation_model")
        layout.prop(props, "time_scale")
        layout.prop(props, "gravitational_constant")
        layout.prop(props, "show_velocity_vectors")
        layout.separator()

        # Body selection
        layout.label(text="Celestial Bodies", icon='OBJECT_DATA')
        row = layout.row(align=True)
        row.operator("three_body.set_initial_state", icon='RESTRICT_SELECT_OFF')
        row.operator("three_body.reset_to_initial", icon='LOOP_BACK')
        
        for i in range(1, 4):
            box = layout.box()
            body_prop = getattr(props, f"body{i}")
            box.label(text=f"Body {i}")
            box.prop(body_prop, "obj", text="Object")
            box.prop(body_prop, "mass", text="Mass")
            box.prop(body_prop, "initial_location", text="Start Pos")
            box.prop(body_prop, "velocity", text="Initial Vel")

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

        # Simulation Method
        layout.label(text="Simulation Method", icon='PHYSICS')
        layout.prop(props, "sim_method", expand=True)
        
        if props.sim_method == 'BAKE':
            layout.prop(props, "cache_path")
            layout.operator("three_body.bake_simulation", icon='RENDER_STILL')

def register():
    bpy.utils.register_class(VIEW3D_PT_three_body_problem)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_three_body_problem)
