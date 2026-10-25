"""
Three Body Problem - Blender Addon
Calculate three-body-problem in Blender.
"""

import bpy

bl_info = {
    "name": "Three Body Problem",
    "author": "masrinine",
    "version": (1, 1, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > Three Body",
    "description": "Calculate three-body-problem in Blender",
    "category": "Physics",
}


from . import properties
from . import panels
from . import operators
from . import gizmos
from . import handlers

def register():
    """Register addon classes and properties."""
    if bpy.app.version < tuple(bl_info["blender"]):
        raise RuntimeError(
            "Three Body Problem requires Blender 5.2 or newer "
            f"(running Blender {bpy.app.version_string})."
        )

    properties.register()
    operators.register()
    gizmos.register()
    panels.register()
    handlers.register()


def unregister():
    """Unregister addon classes and properties."""
    handlers.unregister()
    panels.unregister()
    gizmos.unregister()
    operators.unregister()
    properties.unregister()


if __name__ == "__main__":
    register()
