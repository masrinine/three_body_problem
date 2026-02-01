import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import numpy as np

def draw_velocity_callback(self, context):
    props = context.scene.three_body_props
    if not props.show_velocity_vectors:
        return

    coords = []
    indices = []
    
    for i in range(1, 4):
        body = getattr(props, f"body{i}")
        if not body.obj:
            continue
            
        start = np.array(body.initial_location)
        vel = np.array(body.velocity)
        if np.linalg.norm(vel) < 1e-6:
            continue
            
        end = start + vel
        
        # Line from start to end
        base_idx = len(coords)
        coords.append(start)
        coords.append(end)
        indices.append((base_idx, base_idx + 1))
        
        # Simple arrowhead
        # We can add small lines at the end to make it look like an arrow
        # For simplicity, just a line for now, or a small cross
        v_norm = vel / np.linalg.norm(vel)
        # Find an orthogonal vector for the arrowhead
        ortho = np.array([-v_norm[1], v_norm[0], 0])
        if np.linalg.norm(ortho) < 0.1:
            ortho = np.array([0, -v_norm[2], v_norm[1]])
        ortho = ortho / np.linalg.norm(ortho) * 0.2
        
        coords.append(end - v_norm * 0.3 + ortho)
        coords.append(end)
        coords.append(end - v_norm * 0.3 - ortho)
        coords.append(end)
        indices.append((len(coords)-4, len(coords)-3))
        indices.append((len(coords)-2, len(coords)-1))

    if not coords:
        return

    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINES', {"pos": coords}, indices=indices)
    
    shader.bind()
    shader.uniform_float("color", (0.0, 1.0, 1.0, 1.0)) # Cyan
    batch.draw(shader)

_handle = None

def register():
    global _handle
    _handle = bpy.types.SpaceView3D.draw_handler_add(draw_velocity_callback, (None, None), 'WINDOW', 'POST_VIEW')

def unregister():
    global _handle
    if _handle:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        _handle = None
