"""
Properties for Three Body Problem addon.
This module will contain property definitions for the addon.
"""

import bpy

def update_custom_on_edit(self, context):
    """If any body property is edited, switch the preset to 'CUSTOM'"""
    # Find the parent property group to check the flag
    # Using a slightly safer way to find the props
    props = context.scene.three_body_props
    
    # Check if we are currently mid-preset-update
    # We use a primitive data property to store this state reliably
    if props.get("_updating_from_preset", False):
        return

    if props.simulation_model != 'CUSTOM':
        props.simulation_model = 'CUSTOM'

def update_location_to_viewport(self, context):
    """When sidebar location is changed, move the object in viewport"""
    if self.obj:
        self.obj.location = self.initial_location
    update_custom_on_edit(self, context)

def on_body_obj_update(self, context):
    """When a body object is selected, sync its current location to the property"""
    if self.obj:
        self.initial_location = self.obj.location
    update_custom_on_edit(self, context)

class BodyProperties(bpy.types.PropertyGroup):
    obj: bpy.props.PointerProperty(
        name="Object",
        type=bpy.types.Object,
        description="Select a celestial body",
        update=on_body_obj_update
    )
    mass: bpy.props.FloatProperty(
        name="Mass",
        description="Mass of the body",
        unit='NONE', # Generic mass unit
        default=1.0,
        min=0.001,
        update=update_custom_on_edit
    )
    initial_location: bpy.props.FloatVectorProperty(
        name="Initial Location",
        description="Initial location of the body",
        subtype='TRANSLATION',
        unit='LENGTH',
        precision=3,
        default=(0.0, 0.0, 0.0),
        update=update_location_to_viewport
    )
    velocity: bpy.props.FloatVectorProperty(
        name="Initial Velocity",
        description="Initial velocity of the body",
        subtype='XYZ',
        unit='VELOCITY',
        precision=3,
        default=(0.0, 0.0, 0.0),
        update=update_custom_on_edit
    )
    
    # Internal property to store calculated collision radius
    collision_radius: bpy.props.FloatProperty(
        name="Collision Radius",
        default=0.0
    )

def update_preset_values(self, context):
    """When preset is changed, apply its values to the body properties"""
    if self.simulation_model == 'CUSTOM':
        return
        
    from . import presets
    p = presets.PRESETS.get(self.simulation_model)
    if not p:
        return
        
    # Prevent the update callbacks from switching back to CUSTOM
    self["_updating_from_preset"] = True
    
    try:
        # Scale constants
        S = self.simulation_scale
        
        for i in range(1, 4):
            body = getattr(self, f"body{i}")
            body.mass = p.masses[i-1]
            body.initial_location = p.positions[i-1] * S
            body.velocity = p.velocities[i-1]
            
            # Also move the objects in the viewport if they exist
            if body.obj:
                body.obj.location = body.initial_location
    finally:
        self["_updating_from_preset"] = False

class ThreeBodyProperties(bpy.types.PropertyGroup):
    simulation_model: bpy.props.EnumProperty(
        name="Preset Model",
        description="Choose the preset three-body system",
        items=[
            ('CUSTOM', "Custom (Modified)", "User-defined parameters"),
            ('FIGURE_8', "Figure-Eight (Stable Orbit)", "Three equal masses in a figure-eight orbit"),
            ('LAGRANGE_L4', "Lagrangian Points (Stable)", "Small mass at L4 of a two-body system"),
            ('PYTHAGOREAN', "Pythagorean (Chaotic)", "Classic restricted problem (Burrau's problem)"),
            ('DRAGON', "The Dragon (3D Loop)", "Complex 3D interweaving pattern"),
            ('BUTTERFLY_3D', "Butterfly 3D (Hill's)", "Butterfly-type oscillation in 3D"),
            ('YARN', "The Yarn (Chaos Sphere)", "Spherical 3D movement similar to a ball of yarn"),
            ('CHAOTIC_3D_CLOVER', "Chaotic Clover 3D", "Interweaving 3D clover pattern"),
            ('CHAOTIC_3D_DOUBLE_HEX', "Double Hex 3D", "Non-periodic hexagonal-like 3D orbit"),
            ('PYTHAGOREAN_3D', "Pythagorean 3D", "Extreme chaos version of the Pythagorean problem"),
        ],
        default='FIGURE_8',
        update=update_preset_values
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
        default=500,
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

    softening_multiplier: bpy.props.FloatProperty(
        name="Softening Multiplier",
        description="Increases 'softening' to prevent particles from flying away (0 = accuracy, high = stability)",
        default=3.0,
        min=0.0,
        max=10.0
    )

    simulation_scale: bpy.props.FloatProperty(
        name="Simulation Scale",
        description="Physical scale multiplier for the simulation (default: 5.0)",
        default=5.0,
        min=0.001
    )

    gravitational_constant: bpy.props.FloatProperty(
        name="Gravitational Constant (G)",
        description="Newton's gravitational constant",
        default=1.0,
        min=0.0
    )

    # Collision Settings
    use_collision: bpy.props.BoolProperty(
        name="Enable Collision",
        description="Enable elastic collision between bodies",
        default=False
    )
    auto_collision_radius: bpy.props.BoolProperty(
        name="Auto Radius",
        description="Calculate collision radius automatically from mesh size",
        default=True
    )
    manual_collision_radius: bpy.props.FloatProperty(
        name="Manual Radius",
        description="Manual distance for collision detection",
        default=0.5,
        min=0.001
    )
    radius_offset: bpy.props.FloatProperty(
        name="Radius Offset",
        description="Fine-tuning for collision radius (Applied to both auto and manual)",
        default=0.0,
        precision=3
    )

    gravity_strength: bpy.props.FloatProperty(
        name="Gravity Strength",
        description="Global multiplier for the gravitational force to make interactions more visible",
        default=5.0,
        min=0.0
    )

    softening: bpy.props.FloatProperty(
        name="Softening",
        description="Prevents infinite force at zero distance and smooths close encounters",
        default=0.02,
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
