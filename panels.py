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

        col = layout.column()
        col.prop(props, "simulation_model")

def register():
    bpy.utils.register_class(VIEW3D_PT_three_body_problem)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_three_body_problem)
