"""
Properties for Three Body Problem addon.
This module will contain property definitions for the addon.
"""

import bpy

class ThreeBodyProperties(bpy.types.PropertyGroup):
    simulation_model: bpy.props.EnumProperty(
        name="Simulation Model",
        description="Choose the numerical integration method",
        items=[
            ('RK4', "RK4 (Runge-Kutta 4th)", "Classic 4th order Runge-Kutta"),
            ('VERLET', "Velocity Verlet", "2nd order Symplectic (Verlet)"),
            ('RK45', "RK45 (Adaptive)", "Adaptive RK45 for high precision"),
        ],
        default='RK4'
    )

def register():
    bpy.utils.register_class(ThreeBodyProperties)
    bpy.types.Scene.three_body_props = bpy.props.PointerProperty(type=ThreeBodyProperties)

def unregister():
    del bpy.types.Scene.three_body_props
    bpy.utils.unregister_class(ThreeBodyProperties)
