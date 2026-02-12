import bpy
from bpy.app.handlers import persistent

@persistent
def on_animation_start(scene):
    """Sync object locations to initial_location when animation or simulation starts"""
    props = scene.three_body_props
    
    # We only auto-sync if we are at the start frame
    if scene.frame_current == props.frame_start:
        for i in range(1, 4):
            body_prop = getattr(props, f"body{i}")
            if body_prop.obj:
                body_prop.initial_location = body_prop.obj.location

def register():
    # frame_change_pre or animation_playback_pre could be used
    # animation_playback_pre is triggered when hitting play
    if on_animation_start not in bpy.app.handlers.animation_playback_pre:
        bpy.app.handlers.animation_playback_pre.append(on_animation_start)
    # Also sync if frame is manually set to start_frame
    if on_animation_start not in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.append(on_animation_start)

def unregister():
    if on_animation_start in bpy.app.handlers.animation_playback_pre:
        bpy.app.handlers.animation_playback_pre.remove(on_animation_start)
    if on_animation_start in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(on_animation_start)
