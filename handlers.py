import bpy
from bpy.app.handlers import persistent

from .properties import is_valid_obj

@persistent
def sync_viewport_to_sidebar(scene):
    """
    Optimized real-time sync with sparse updates to minimize UI lag.
    """
    if not hasattr(scene, "three_body_props"):
        return
        
    props = scene.three_body_props
    if props.is_baking:
        return

    # Look up names once to speed up O(N) scene checks
    scene_obj_names = {obj.name for obj in scene.objects}
    
    to_remove = []
    has_changes = False
    is_start = (scene.frame_current == props.frame_start)
    skip_sync = props.get("_updating_from_preset", False)

    for i, body_prop in enumerate(props.bodies):
        obj = body_prop.obj
        
        # 1. Validation Logic
        is_invalid = False
        if not obj:
            is_invalid = True
        else:
            try:
                if obj.name not in scene_obj_names:
                    is_invalid = True
            except (ReferenceError, AttributeError):
                is_invalid = True

        if is_invalid:
            to_remove.append(i)
            has_changes = True
            continue

        # 2. Sync Location (Only if significant change on start frame)
        if is_start and not skip_sync:
            # Using length_squared for faster comparison
            if (obj.location - body_prop.initial_location).length_squared > 0.000001:
                body_prop.initial_location = obj.location

    if has_changes:
        for idx in reversed(to_remove):
            props.bodies.remove(idx)
        
        # Targeted redraw for relevant areas
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {'VIEW_3D', 'PROPERTIES'}:
                    area.tag_redraw()

@persistent
def cleanup_on_load(scene):
    """File preservation safety: Reset internal flags"""
    if hasattr(scene, "three_body_props"):
        scene.three_body_props.is_baking = False

def register():
    # Depsgraph handler for real-time sync
    if sync_viewport_to_sidebar not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(sync_viewport_to_sidebar)
    
    # Load handlers for state safety
    if cleanup_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(cleanup_on_load)

def unregister():
    if sync_viewport_to_sidebar in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(sync_viewport_to_sidebar)
    if cleanup_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(cleanup_on_load)
