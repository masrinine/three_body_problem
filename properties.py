"""
Properties for Three Body Problem addon.
This module will contain property definitions for the addon.
"""

import bpy

def update_custom_on_edit(self, context):
    """If any body property is edited, switch the preset to 'CUSTOM'"""
    props = context.scene.three_body_props
    
    if props.get("_updating_from_preset", False):
        return

    if props.simulation_model != 'CUSTOM':
        props.simulation_model = 'CUSTOM'

def update_location_to_viewport(self, context):
    """When sidebar location is changed, move the object in viewport"""
    if self.obj:
        self.obj.location = self.initial_location
    update_custom_on_edit(self, context)

def update_simulation_scale(self, context):
    """Keep the normalized system shape when Simulation Scale changes.

    Presets are applied as ``position * S`` / ``velocity * S`` and the bake uses
    ``G * S^3``. Rescaling the stored state by the same ratio preserves the
    trajectory shape for both presets and custom systems.
    """
    if self.get("_updating_from_preset", False):
        return

    new_scale = float(self.simulation_scale)
    old_scale = self.get("_last_simulation_scale", None)
    if new_scale <= 0:
        return
    if old_scale is None or old_scale <= 0:
        self["_last_simulation_scale"] = new_scale
        return
    if abs(new_scale - float(old_scale)) < 1e-9:
        return

    ratio = new_scale / float(old_scale)
    self["_updating_from_preset"] = True
    try:
        for body in self.bodies:
            body.initial_location = tuple(float(x) * ratio for x in body.initial_location)
            body.velocity = tuple(float(x) * ratio for x in body.velocity)
    finally:
        self["_updating_from_preset"] = False
    self["_last_simulation_scale"] = new_scale

def _tag_view3d_redraw(self, context):
    """Redraw every 3D Viewport so viewport-only settings apply immediately.

    ``context`` (and ``context.screen``) can be None while a file loads or when
    running headless, in which case there is nothing to redraw.
    """
    if context is None:
        return
    screen = getattr(context, "screen", None)
    if screen is None:
        return
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()

def is_valid_obj(obj):
    """Utility to check if a Blender object is valid and currently in the scene."""
    if not obj:
        return False
    try:
        # Check if the object is still in memory and has a name
        _ = obj.name
        # Check if it's linked to the current scene
        return obj.name in bpy.context.scene.objects
    except (ReferenceError, AttributeError):
        return False

def on_body_obj_update(self, context):
    """When a body object is selected, sync its current location to the property"""
    if self.obj:
        self.initial_location = self.obj.location
    update_custom_on_edit(self, context)
    
    # Force viewport redraw to update gizmos
    if context and hasattr(context, "region") and context.region:
        context.region.tag_redraw()

def apply_body_preset(body_prop, mass, location, velocity):
    """Apply one preset body state to the property group."""
    body_prop.mass = mass
    body_prop.initial_location = location
    body_prop.velocity = velocity
    if body_prop.obj:
        body_prop.obj.location = location

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
        unit='NONE',
        default=1.0,
        min=0.001,
        update=update_custom_on_edit
    )
    initial_location: bpy.props.FloatVectorProperty(
        name="Initial Location",
        description="Initial location in world units (scaled by Simulation Scale when a preset is applied)",
        subtype='TRANSLATION',
        unit='LENGTH',
        precision=3,
        default=(0.0, 0.0, 0.0),
        update=update_location_to_viewport
    )
    velocity: bpy.props.FloatVectorProperty(
        name="Initial Velocity",
        description="Initial velocity in world units (scaled by Simulation Scale when a preset is applied)",
        subtype='XYZ',
        unit='VELOCITY',
        precision=3,
        default=(0.0, 0.0, 0.0),
        update=update_custom_on_edit
    )
    
    # Internal flag to identify expanded state in UI
    is_expanded: bpy.props.BoolProperty(
        name="Expanded",
        default=False
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
        
        # Ensure we have at least 3 bodies for the preset
        while len(self.bodies) < 3:
            self.bodies.add()
            
        for i in range(3):
            body = self.bodies[i]
            apply_body_preset(body, p.masses[i], p.positions[i] * S, p.velocities[i] * S)

        self["_last_simulation_scale"] = S
        # If there are more than 3 bodies, we don't necessarily remove them 
        # but the preset only applies to the first 3.
    finally:
        self["_updating_from_preset"] = False

class ThreeBodyProperties(bpy.types.PropertyGroup):
    use_compact_list: bpy.props.BoolProperty(
        name="Compact List",
        description="Show a more compact view of bodies in the side panel",
        default=False
    )

    velocity_gizmo_scale: bpy.props.FloatProperty(
        name="Gizmo Drawing Scale",
        description="Scale of the velocity vectors in the viewport (visual only)",
        default=1.0,
        min=0.01,
        max=50.0,
        update=_tag_view3d_redraw
    )

    last_simulation_report: bpy.props.StringProperty(
        name="Last Simulation Report",
        default="No simulation baked yet."
    )
    
    show_report: bpy.props.BoolProperty(
        name="Show Report",
        description="Show or hide the last simulation report",
        default=True
    )

    simulation_model: bpy.props.EnumProperty(
        name="Preset Model",
        description="Choose the preset three-body system (Calculated for first 3 bodies)",
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

    bodies: bpy.props.CollectionProperty(type=BodyProperties) # type: ignore
    
    setup_body_count: bpy.props.IntProperty(
        name="Setup Count",
        description="Number of objects to create when clicking Setup",
        default=3,
        min=1,
        max=50
    )

    is_baking: bpy.props.BoolProperty(
        name="Is Baking",
        default=False,
        description="Internal flag to prevent concurrent bakes or UI edits during bake"
    )

    is_baked: bpy.props.BoolProperty(
        name="Is Baked",
        default=False,
        description="Flag set when simulation data is baked. Locks initial values to prevent inconsistencies"
    )

    energy_drift: bpy.props.FloatProperty(
        name="Energy Drift (%)",
        description="The percentage change in total system energy (Hamiltonian drift) during simulation. Lower is more accurate",
        default=0.0,
        precision=6
    )

    sync_collection: bpy.props.PointerProperty(
        name="Sync Collection",
        type=bpy.types.Collection,
        description="Collection to sync mesh objects from"
    )

    bake_limit_seconds: bpy.props.FloatProperty(
        name="Bake Timeout (s)",
        description="Stop simulation if it takes longer than this per frame (safety)",
        default=5.0,
        min=0.1,
        max=60.0
    )
    
    max_velocity_safety: bpy.props.FloatProperty(
        name="Speed Limit",
        description="If any body exceeds this velocity, stop simulation (prevents 'fly-away' numerical issues)",
        default=1000.0,
        min=1.0
    )

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

    softening_multiplier: bpy.props.FloatProperty(
        name="Softening Multiplier",
        description="Multiplies the preset softening length (which is already scaled by Simulation Scale)",
        default=3.0,
        min=0.0,
        max=10.0
    )

    simulation_scale: bpy.props.FloatProperty(
        name="Simulation Scale",
        description="Multiplies initial positions/velocities (G scales with the cube of this value)",
        default=5.0,
        min=0.001,
        update=update_simulation_scale
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
        description="World-space collision radius (not diameter)",
        default=0.5,
        min=0.001
    )
    radius_offset: bpy.props.FloatProperty(
        name="Radius Offset",
        description="Added to the collision radius in world units",
        default=0.0,
        precision=3
    )

    gravity_strength: bpy.props.FloatProperty(
        name="Gravity Strength",
        description="Global multiplier for the gravitational force",
        default=1.0,
        min=0.0
    )

    integrator_type: bpy.props.EnumProperty(
        name="Integrator",
        description="Mathematical method to calculate physics steps",
        items=[
            ('RK45', "RK45 (Adaptive)", "Runge-Kutta adaptive step. Very accurate but can be slow if objects collide."),
            ('LEAPFROG', "Leapfrog (Stable)", "Symplectic integrator. Maintains energy conservation over long periods. Best for circular orbits."),
        ],
        default='RK45'
    )

    show_velocity_vectors: bpy.props.BoolProperty(
        name="Show Velocity Vectors",
        description="Show each body's initial velocity as an arrow in the viewport",
        default=True,
        update=_tag_view3d_redraw
    )

def register():
    try:
        bpy.utils.register_class(BodyProperties)
    except ValueError:
        pass
    
    try:
        bpy.utils.register_class(ThreeBodyProperties)
    except ValueError:
        pass
    
    if not hasattr(bpy.types.Scene, "three_body_props"):
        bpy.types.Scene.three_body_props = bpy.props.PointerProperty(type=ThreeBodyProperties)

    for scene in bpy.data.scenes:
        props = getattr(scene, "three_body_props", None)
        if props is not None and "_last_simulation_scale" not in props:
            props["_last_simulation_scale"] = props.simulation_scale

def unregister():
    if hasattr(bpy.types.Scene, "three_body_props"):
        del bpy.types.Scene.three_body_props
    
    try:
        bpy.utils.unregister_class(ThreeBodyProperties)
    except RuntimeError:
        pass
        
    try:
        bpy.utils.unregister_class(BodyProperties)
    except RuntimeError:
        pass

