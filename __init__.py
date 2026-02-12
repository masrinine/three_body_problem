"""
Three Body Problem - Blender Addon
Calculate three-body-problem in Blender.
"""

bl_info = {
    "name": "Three Body Problem",
    "author": "masrinine",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Three Body",
    "description": "Calculate three-body-problem in Blender",
    "category": "Physics",
}


from . import properties
from . import panels
from . import operators
from . import visualization
from . import handlers

def register():
    """Register addon classes and properties."""
    properties.register()
    operators.register()
    visualization.register()
    handlers.register()
    panels.register()


def unregister():
    """Unregister addon classes and properties."""
    panels.unregister()
    handlers.unregister()
    visualization.unregister()
    operators.unregister()
    properties.unregister()


if __name__ == "__main__":
    register()
