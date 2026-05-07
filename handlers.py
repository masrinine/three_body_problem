import bpy
from bpy.app.handlers import persistent

from .properties import is_valid_obj

@persistent
def sync_viewport_to_sidebar(scene):
    """
    Sync object locations from viewport to the sidebar properties in real-time.
    Includes aggressive lifecycle management for deleted objects.
    """
    props = scene.three_body_props
    
    if props.is_baking:
        return

    to_remove = []
    for i, body_prop in enumerate(props.bodies):
        if not is_valid_obj(body_prop.obj):
            to_remove.append(i)
            continue

        # 2. 位置の同期 (開始フレームのみ)
        if scene.frame_current == props.frame_start:
            if not props.get("_updating_from_preset", False):
                if (body_prop.obj.location - body_prop.initial_location).length > 0.0001:
                    body_prop.initial_location = body_prop.obj.location

    if to_remove:
        for idx in reversed(to_remove):
            props.bodies.remove(idx)
        
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
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
