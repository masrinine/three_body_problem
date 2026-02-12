"""
Properties for Three Body Problem addon.
This module will contain property definitions for the addon.
"""

import bpy

class BodyProperties(bpy.types.PropertyGroup):
    obj: bpy.props.PointerProperty(
        name="Object",
        type=bpy.types.Object,
        description="Select a celestial body"
    )
    mass: bpy.props.FloatProperty(
        name="Mass",
        description="Mass of the body",
        default=1.0,
        min=0.001
    )
    initial_location: bpy.props.FloatVectorProperty(
        name="Initial Location",
        description="Initial location of the body",
        subtype='TRANSLATION',
        precision=3
    )
    velocity: bpy.props.FloatVectorProperty(
        name="Initial Velocity",
        description="Initial velocity of the body",
        subtype='XYZ',
        precision=3
    )

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

    body1: bpy.props.PointerProperty(type=BodyProperties)
    body2: bpy.props.PointerProperty(type=BodyProperties)
    body3: bpy.props.PointerProperty(type=BodyProperties)

    frame_start: bpy.props.IntProperty(
        name="Start Frame",
        description="Frame to start simulation",
        default=1,
        min=1
    )
    frame_end: bpy.props.IntProperty(
        name="End Frame",
        description="Frame to end simulation",
        default=250,
        min=1
    )

    use_scene_fps: bpy.props.BoolProperty(
        name="Use Scene FPS",
        description="Use the current scene's FPS for calculation",
        default=True
    )
    fps_override: bpy.props.IntProperty(
        name="FPS Override",
        description="FPS for calculation if Use Scene FPS is off",
        default=24,
        min=1
    )

    time_scale: bpy.props.FloatProperty(
        name="Time Scale",
        description="Simulation speed (1.0 is normal speed)",
        default=1.0,
        min=0.0
    )

    gravitational_constant: bpy.props.FloatProperty(
        name="Gravitational Constant (G)",
        description="Newton's gravitational constant",
        default=1.0,
        min=0.0
    )

    sim_method: bpy.props.EnumProperty(
        name="Simulation Method",
        description="Choose how to calculate the simulation",
        items=[
            ('REALTIME', "Real-time", "Simulate while playing back"),
            ('BAKE', "Bake to Cache", "Pre-calculate and save to files"),
        ],
        default='REALTIME'
    )

    cache_path: bpy.props.StringProperty(
        name="Cache Path",
        description="Folder to store simulation cache",
        default="/tmp/",
        subtype='DIR_PATH'
    )

    show_velocity_vectors: bpy.props.BoolProperty(
        name="Show Velocity Vectors",
        description="Visualize initial velocity vectors in the viewport",
        default=True
    )

def register():
    bpy.utils.register_class(BodyProperties)
    bpy.utils.register_class(ThreeBodyProperties)
    bpy.types.Scene.three_body_props = bpy.props.PointerProperty(type=ThreeBodyProperties)

def unregister():
    del bpy.types.Scene.three_body_props
    bpy.utils.unregister_class(ThreeBodyProperties)
    bpy.utils.unregister_class(BodyProperties)
