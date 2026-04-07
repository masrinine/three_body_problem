import bpy
from bpy.app.handlers import persistent

@persistent
def sync_viewport_to_sidebar(scene):
    """
    Sync object locations from viewport to the sidebar properties in real-time.
    This allows dragging the object to update the 'initial_location' value.
    """
    props = scene.three_body_props
    
    # We only sync if we are at the start frame (the 'initial state')
    if scene.frame_current == props.frame_start:
        # Avoid syncing while the preset itself is being applied
        if props.get("_updating_from_preset", False):
            return

        for i in range(1, 4):
            body_prop = getattr(props, f"body{i}")
            if body_prop.obj:
                # If viewport location differs from stored property, update property
                # and trigger CUSTOM mode switch via the update callback
                if (body_prop.obj.location - body_prop.initial_location).length > 0.0001:
                    # Setting the property directly bypasses some update logic but
                    # we want the 'CUSTOM' switch. 
                    # Note: props.simulation_model = 'CUSTOM' is handled in the property update
                    body_prop.initial_location = body_prop.obj.location

def register():
    # depsgraph_update_post is triggered whenever the scene changes (e.g. object moved)
    if sync_viewport_to_sidebar not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(sync_viewport_to_sidebar)

def unregister():
    if sync_viewport_to_sidebar in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(sync_viewport_to_sidebar)
